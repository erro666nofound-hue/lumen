"""Một việc tải nhạc: mô tả nó, và chạy nó ngoài luồng chính.

Tách khỏi DownloadBridge vì bridge đã phải lo model cho QML, hàng đợi, và bốn
loại callback; gộp thêm phần worker vào là một file không ai đọc hết được.

Luật luồng: `run()` chạy ở luồng của QThreadPool, nên nó KHÔNG được chạm vào
database hay bất cứ thứ gì của Qt ngoài việc phát signal — mọi thứ khác đi về
luồng chính qua signal (CLAUDE.md mục 4).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal

from lumen.core.downloader import DownloadCancelled, Downloader, Progress
from lumen.core.errors import LumenError

log = logging.getLogger(__name__)

STATE_QUEUED = "queued"
STATE_RUNNING = "running"
STATE_DONE = "done"
STATE_FAILED = "failed"
STATE_CANCELLED = "cancelled"


@dataclass(slots=True)
class _Job:
    """One download, as the UI sees it."""

    job_id: int
    url: str
    video_id: str
    playlist_id: int | None = None
    target_dir: Path | None = None
    title: str = ""
    fraction: float = -1.0
    stage: str = ""
    detail: str = ""
    state: str = STATE_QUEUED
    error: str = ""
    # Thông tin nơi gọi ĐÃ BIẾT sẵn (thẻ vừa bấm có đủ tên/tác giả/thời lượng/
    # ảnh). Nếu chờ downloader dò xong mới biết thì hàng "đang tải" phải hiện
    # một dòng trống suốt mấy giây đầu — mà giao diện thì có sẵn từ đầu.
    hint_title: str = ""
    hint_artist: str = ""
    hint_duration_text: str = ""
    hint_thumbnail: str = ""
    # Việc này là TẢI LẠI một bài đồng bộ về, không phải tải mới: nó đi vòng
    # hạn mức của gói và không cộng sổ. Xem `bridge/download_refill.py`.
    refill: bool = False
    # Việc tải lại nhắm vào ĐÚNG MỘT dòng, không phải "một dòng nào đó mang mã
    # video này". Từ CB-036, cùng một bài có thể có nhiều dòng chỗ trống đứng
    # chờ — mỗi track một dòng — nên thiếu số này thì bài tải xong lấp bừa vào
    # dòng đầu tiên và những dòng còn lại chờ mãi.
    track_id: int | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event)


class _WorkerSignals(QObject):
    """Signal carrier for a QRunnable (QRunnable itself is not a QObject)."""

    progress = Signal(int, str, float, str)
    finished = Signal(int, object)
    failed = Signal(int, str)


class _DownloadRunnable(QRunnable):
    """Run one download off the main thread."""

    def __init__(self, job: _Job, downloader: Downloader) -> None:
        super().__init__()
        self._job = job
        self._downloader = downloader
        self.signals = _WorkerSignals()

    def run(self) -> None:
        job = self._job

        def on_progress(progress: Progress) -> None:
            self.signals.progress.emit(job.job_id, progress.stage, progress.fraction, progress.detail)

        try:
            result = self._downloader.download(
                job.url,
                target_dir=job.target_dir,
                on_progress=on_progress,
                should_cancel=job.cancel_event.is_set,
            )
        except DownloadCancelled:
            self.signals.failed.emit(job.job_id, "")
        except LumenError as exc:
            log.warning("Download failed for %s: %s", job.url, exc)
            self.signals.failed.emit(job.job_id, exc.user_message or "Tải thất bại.")
        except Exception as exc:  # noqa: BLE001 - a worker must never die silently
            log.exception("Unexpected download failure for %s", job.url)
            self.signals.failed.emit(job.job_id, f"Lỗi không lường trước: {exc}")
        else:
            self.signals.finished.emit(job.job_id, result)
