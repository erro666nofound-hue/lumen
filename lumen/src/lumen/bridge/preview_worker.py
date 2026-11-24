"""Resolve a YouTube audio stream off the Qt main thread.

Threading contract (CLAUDE.md muc 4): resolving blocks on the network for a
few seconds, so it runs in a QRunnable and comes back over QueuedConnection.
It lives in its own module to keep PlayerBridge readable -- the bridge only
has to say "resolve this, call me back".

Bộ đếm thế hệ giống SearchBridge: bấm nghe thử bài B khi bài A còn đang bóc
thì kết quả của A về sau PHẢI bị bỏ, nếu không loa sẽ nhảy sang bài người dùng
đã đổi ý.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal

from lumen.core.errors import LumenError
from lumen.core.models import Track
from lumen.core.stream import StreamInfo, resolve

log = logging.getLogger(__name__)

# Đủ để YouTube nguôi, chưa đủ để người dùng thấy treo.
_RETRY_DELAY_S = 1.5


class _Signals(QObject):
    """Signal carrier for a QRunnable (QRunnable itself is not a QObject)."""

    resolved = Signal(int, object)   # (generation, StreamInfo)
    failed = Signal(int, str)        # (generation, user_message)


class _Worker(QRunnable):
    def __init__(self, generation: int, video_id: str) -> None:
        super().__init__()
        self.signals = _Signals()
        self._generation = generation
        self._video_id = video_id

    def run(self) -> None:
        try:
            info = _resolve_with_retry(self._video_id)
        except LumenError as exc:
            self.signals.failed.emit(self._generation, exc.user_message)
        except Exception:
            log.exception("Unexpected error resolving %s", self._video_id)
            self.signals.failed.emit(self._generation, "Không nghe thử được bài này.")
        else:
            self.signals.resolved.emit(self._generation, info)


def _resolve_with_retry(video_id: str) -> StreamInfo:
    """Thử lại một lần sau khi nghỉ ngắn.

    YouTube bật kiểm tra chống bot ("Sign in to confirm you're not a bot") khi
    thấy nhiều lần bóc dồn dập từ cùng một IP — đã đo được thật: hai lần bóc
    chạy song song thì một lần trượt. Xếp hàng một luồng (xem PreviewResolver)
    lo phần "song song"; lần thử lại này lo phần "dồn dập", ví dụ khi trang
    khám phá vừa chạy xong đã bấm nghe thử ngay.
    """
    try:
        return resolve(video_id)
    except LumenError:
        time.sleep(_RETRY_DELAY_S)
        return resolve(video_id)


class PreviewResolver(QObject):
    """Turn video ids into playable stream URLs, one at a time, newest wins."""

    resolved = Signal(object)        # StreamInfo
    failed = Signal(str)
    busyChanged = Signal()

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        # Hồ riêng, MỘT luồng: hai lần bóc chạy cùng lúc là bị YouTube chặn
        # chống bot. Yêu cầu mới xếp hàng sau yêu cầu cũ, và kết quả của yêu
        # cầu cũ vẫn bị bộ đếm thế hệ loại bỏ như thường.
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._generation = 0
        self._busy = False
        # Strong refs: a QRunnable's signal carrier is garbage collected the
        # moment nothing holds it, and the callback silently never arrives.
        self._alive: dict[int, _Worker] = {}

    @property
    def busy(self) -> bool:
        return self._busy

    def cancel(self) -> None:
        """Forget any in-flight request; a late answer will be discarded."""
        self._generation += 1
        self._alive.clear()
        self._set_busy(False)

    def start(self, video_id: str) -> None:
        """Begin resolving; emits resolved() or failed() on the main thread."""
        self._generation += 1
        generation = self._generation
        worker = _Worker(generation, video_id)
        worker.signals.resolved.connect(self._on_resolved, Qt.ConnectionType.QueuedConnection)
        worker.signals.failed.connect(self._on_failed, Qt.ConnectionType.QueuedConnection)
        self._alive[generation] = worker
        self._set_busy(True)
        self._pool.start(worker)

    def _retire(self, generation: int) -> bool:
        """Drop the worker and say whether its answer is still wanted."""
        self._alive.pop(generation, None)
        return generation == self._generation

    def _on_resolved(self, generation: int, info: StreamInfo) -> None:
        if not self._retire(generation):
            return
        self._set_busy(False)
        self.resolved.emit(info)

    def _on_failed(self, generation: int, message: str) -> None:
        if not self._retire(generation):
            return
        self._set_busy(False)
        self.failed.emit(message)

    def _set_busy(self, value: bool) -> None:
        if value != self._busy:
            self._busy = value
            self.busyChanged.emit()


# -- Cầu nối sang PlayerBridge ------------------------------------------------
# Bốn hàm này là phần "nghe thử" của PlayerBridge, để rời ra đây cho file kia
# nằm trong hạn mức dòng. Chúng đọc/ghi thẳng vào bridge nên chỉ dùng được với
# PlayerBridge -- đừng gọi từ nơi khác.


def start_preview(bridge: Any, video_id: str) -> None:
    """Bấm lại chính bài đang nghe thử = dừng, giống nút phát ở mọi chỗ khác."""
    if video_id and video_id == bridge._preview_id:
        bridge.toggle()
        return
    bridge._preview_id = video_id
    bridge._preview.start(video_id)
    bridge.previewChanged.emit()


def stop_preview(bridge: Any) -> None:
    """Bỏ dở việc nghe thử -- dù đang bóc dở hay đã phát."""
    bridge._preview.cancel()
    if bridge._preview_id:
        bridge._preview_id = ""
        bridge.stop()
    bridge.previewChanged.emit()


def on_preview_resolved(bridge: Any, info: StreamInfo) -> None:
    """Luồng đã bóc xong: cho mpv mở URL y như mở một file trên đĩa.

    Bài nghe thử KHÔNG có dòng trong thư viện: id để None, nên
    take_listen_credit() bỏ qua nó và không màn hình track nào khớp được với nó.
    """
    track = Track(
        id=None,
        real_name=info.title,
        artist=info.uploader,
        duration_ms=info.duration_ms,
        file_path=info.url,
        cover_path=info.thumbnail,
    )
    bridge._scope_id = -1
    bridge._controller.set_queue([])
    try:
        bridge._controller.start(track)
    except LumenError as exc:
        log.exception("Cannot start preview")
        bridge._preview_id = ""
        bridge.errorOccurred.emit(exc.user_message)
        return
    bridge._ticker.start()
    bridge._emitAll()


def on_preview_failed(bridge: Any, message: str) -> None:
    bridge._preview_id = ""
    bridge.previewChanged.emit()
    bridge.errorOccurred.emit(message)
