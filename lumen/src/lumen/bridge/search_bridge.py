"""Qt list model and worker pool for YouTube text search.

Threading contract (CLAUDE.md muc 4): the network calls must never run on the
Qt main thread. Same shape as ``bridge/download_bridge.py``: a ``QRunnable``
does the I/O and every signal back is ``QueuedConnection``, so the model is
only ever touched from the main thread.

Hai pha: tìm kiếm (~2s, có lượt xem) hiện kết quả ngay; lấy lượt like (~3.4s)
chạy sau rồi xếp lại theo tỉ lệ like/view. Xem ``_LikesWorker``.

Bộ đếm thế hệ chặn cuộc đua kinh điển của ô tìm kiếm: người dùng gõ "abc" rồi
sửa thành "abd" trước khi "abc" về. Kết quả "abc" về sau PHẢI bị bỏ, nếu không
ô tìm sẽ nháy kết quả cũ đè lên thứ người dùng đang hỏi. Mỗi ``run()`` tăng
``self._generation``; worker mang theo thế hệ của nó và chỉ được áp dụng nếu
thế hệ đó vẫn còn là hiện tại.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    QRunnable,
    QThreadPool,
    Qt,
    Property,
    Signal,
    Slot,
)

from lumen.core.errors import LumenError
from lumen.core.formatting import format_duration
from lumen.core.youtube_search import SearchResult, fetch_likes, rank, search

log = logging.getLogger(__name__)

# Enough results to fill a picker list without waiting long on a slow link.
_RESULT_LIMIT = 12
# Chỉ lấy lượt like cho nhóm đầu: mỗi video tốn ~1.6s, lấy hết 12 là quá lâu.
_LIKES_LIMIT = 8


class _WorkerSignals(QObject):
    """Signal carrier for a QRunnable (QRunnable itself is not a QObject)."""

    finished = Signal(int, object)  # (generation, list[SearchResult])
    failed = Signal(int, str)  # (generation, user_message)
    liked = Signal(int, object)  # (generation, dict[video_id, like_count])


class _LikesWorker(QRunnable):
    """PHA HAI: lấy lượt like cho các kết quả đã hiện (xem docstring đầu file)."""

    def __init__(self, generation: int, video_ids: list[str]) -> None:
        super().__init__()
        self._generation = generation
        self._video_ids = video_ids
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            likes = fetch_likes(self._video_ids)
        except Exception:
            log.exception("Cannot fetch like counts")
            return  # thiếu điểm không phải lỗi người dùng cần biết
        self.signals.liked.emit(self._generation, likes)


class _SearchWorker(QRunnable):
    """Run one text search off the main thread, same shape as download_bridge."""

    def __init__(self, generation: int, query: str) -> None:
        super().__init__()
        self._generation = generation
        self._query = query
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            results = search(self._query, limit=_RESULT_LIMIT)
        except LumenError as exc:
            log.warning("Search failed for %r: %s", self._query, exc)
            self.signals.failed.emit(self._generation, exc.user_message or "Tìm kiếm thất bại.")
        except Exception as exc:  # noqa: BLE001 - a worker must never die silently
            log.exception("Unexpected search failure for %r", self._query)
            self.signals.failed.emit(self._generation, f"Lỗi không lường trước: {exc}")
        else:
            self.signals.finished.emit(self._generation, results)


class SearchBridge(QAbstractListModel):
    """Expose YouTube text search results to QML as a list model."""

    VideoIdRole = Qt.ItemDataRole.UserRole + 1
    TitleRole = Qt.ItemDataRole.UserRole + 2
    UploaderRole = Qt.ItemDataRole.UserRole + 3
    DurationTextRole = Qt.ItemDataRole.UserRole + 4
    UrlRole = Qt.ItemDataRole.UserRole + 5
    ThumbnailRole = Qt.ItemDataRole.UserRole + 6

    countChanged = Signal()
    queryChanged = Signal()
    busyChanged = Signal()
    errorOccurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._results: list[SearchResult] = []
        self._query = ""
        self._busy = False
        # Bumped on every run()/clear(); a worker's result is only applied
        # when its generation still matches -- see module docstring.
        self._generation = 0
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(2)
        # generation -> worker đang chạy; xem chú thích trong run().
        self._alive: dict[int, _SearchWorker] = {}

    def roleNames(self) -> dict[int, QByteArray]:
        return {
            self.VideoIdRole: QByteArray(b"videoId"),
            self.TitleRole: QByteArray(b"title"),
            self.UploaderRole: QByteArray(b"uploader"),
            self.DurationTextRole: QByteArray(b"durationText"),
            self.UrlRole: QByteArray(b"url"),
            self.ThumbnailRole: QByteArray(b"thumbnail"),
        }

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._results)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._results)):
            return None
        item = self._results[index.row()]
        match role:
            case self.VideoIdRole:
                return item.video_id
            case self.TitleRole:
                return item.title
            case self.UploaderRole:
                return item.uploader
            case self.DurationTextRole:
                return format_duration(item.duration_ms)
            case self.UrlRole:
                return item.url
            case self.ThumbnailRole:
                return item.thumbnail
        return None

    @Slot(str)
    def run(self, query: str) -> None:
        """Search YouTube for `query`. A still-running older search is superseded, not stopped."""
        text = query.strip()
        # Tăng trước, vô điều kiện: đó là thứ khiến kết quả cũ bị bỏ.
        self._generation += 1
        generation = self._generation

        if text != self._query:
            self._query = text
            self.queryChanged.emit()

        if not text:
            # Mirrors core.search(): empty/whitespace query, no network call.
            self._set_busy(False)
            self._set_results([])
            return

        self._set_busy(True)

        runnable = _SearchWorker(generation, text)
        # Giữ tham chiếu Python tới worker: lớp bọc Python (và đối tượng mang
        # signal) có thể bị thu gom trước lúc emit — đã thấy một lần
        # "RuntimeError: Signal source has been deleted" từ luồng worker.
        self._alive[generation] = runnable
        # Queued: bắn từ luồng worker, phải về luồng chính mới chạm model.
        runnable.signals.finished.connect(self._on_finished, Qt.ConnectionType.QueuedConnection)
        runnable.signals.failed.connect(self._on_failed, Qt.ConnectionType.QueuedConnection)
        self._pool.start(runnable)

    @Slot()
    def clear(self) -> None:
        """Discard results, reset the query, and drop any in-flight search."""
        self._generation += 1  # any in-flight search is now stale
        self._set_busy(False)
        self._set_results([])
        if self._query:
            self._query = ""
            self.queryChanged.emit()

    @Slot(int, object)
    def _on_finished(self, generation: int, results: list[SearchResult]) -> None:
        self._alive.pop(generation, None)
        if generation != self._generation:
            return  # a newer search (or a clear()) has already superseded this one
        self._set_busy(False)
        self._set_results(rank(results))
        self._start_likes(generation, results)

    @Slot(int, str)
    def _on_failed(self, generation: int, user_message: str) -> None:
        self._alive.pop(generation, None)
        if generation != self._generation:
            return
        self._set_busy(False)
        self._set_results([])
        self.errorOccurred.emit(user_message)

    def _start_likes(self, generation: int, results: list[SearchResult]) -> None:
        """Chạy pha hai cho các kết quả đầu bảng."""
        ids = [r.video_id for r in results[:_LIKES_LIMIT]]
        if not ids:
            return
        worker = _LikesWorker(generation, ids)
        self._alive[-generation] = worker      # khoá âm: không đụng khoá pha một
        worker.signals.liked.connect(self._on_liked, Qt.ConnectionType.QueuedConnection)
        self._pool.start(worker)

    @Slot(int, object)
    def _on_liked(self, generation: int, likes: dict[str, int]) -> None:
        self._alive.pop(-generation, None)
        if generation != self._generation or not likes:
            return
        self._set_results(rank(self._results, likes))

    def _set_results(self, results: list[SearchResult]) -> None:
        self.beginResetModel()
        self._results = results
        self.endResetModel()
        self.countChanged.emit()

    def _set_busy(self, value: bool) -> None:
        if value == self._busy:
            return
        self._busy = value
        self.busyChanged.emit()

    count = Property(int, lambda self: len(self._results), notify=countChanged)
    query = Property(str, lambda self: self._query, notify=queryChanged)
    busy = Property(bool, lambda self: self._busy, notify=busyChanged)
    # "đã tìm hay chưa" đổi đúng lúc query đổi giữa rỗng và không rỗng, nên
    # on queryChanged rather than needing its own bookkeeping.
    hasSearched = Property(bool, lambda self: bool(self._query), notify=queryChanged)
