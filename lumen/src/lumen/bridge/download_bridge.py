"""Qt model and worker pool for YouTube downloads.

Threading contract (CLAUDE.md muc 4), the part that matters most in this file:

* Downloads run on a QThreadPool worker. Workers do network and disk I/O only.
* Workers NEVER touch SQLite and never call into the model directly. They report
  back exclusively through signals on a per-job QObject, delivered queued, so
  every state change and every database write happens on the Qt main thread.
* Cancellation is a threading.Event the worker polls through yt-dlp's progress
  hook, because that hook is the only place yt-dlp gives us to interrupt.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, QObject, Qt, QThreadPool, QTimer, Property, Signal, Slot

from lumen.core import sync_clock
from lumen.core.downloader import DownloadResult, Downloader
from lumen.core.download_plan import ACTION_COPY, plan_for
from lumen.bridge import download_refill, download_rows
from lumen.bridge.download_worker import (
    STATE_CANCELLED,
    STATE_DONE,
    STATE_FAILED,
    STATE_QUEUED,
    STATE_RUNNING,
    _DownloadRunnable,
    _Job,
)
from lumen.core.errors import LumenError
from lumen.core.history import DownloadHistoryRepository
from lumen.core.library_files import copy_into
from lumen.core.models import Track
from lumen.core.paths import track_dir
from lumen.core.repository import PlaylistRepository
from lumen.core.youtube import is_youtube_url, parse_url, watch_url

log = logging.getLogger(__name__)

# Kết của một lần lấp dòng chỗ trống: chép từ đĩa, xếp hàng tải, hay không làm
# được gì. Chuỗi rỗng là cái thứ ba — nơi gọi chỉ cần phân biệt ba trạng thái.
_REFILL_COPIED = "copied"
_REFILL_QUEUED = "queued"
# Dòng này không tự tải: một việc tải CÙNG BÀI đang chạy rồi, nó chờ chép theo
# sau. Hai lần tải cùng một video rơi vào cùng một tên file, mà `file_path` là
# UNIQUE — dòng thứ hai lấp hụt và nằm câm vĩnh viễn.
_REFILL_WAITING = "waiting"

# Finished jobs disappear on their own so the strip does not turn into a log.
_DONE_LINGER_MS = 2500


class DownloadBridge(QAbstractListModel):
    """Expose the download queue to QML and turn finished downloads into tracks."""

    JobIdRole = Qt.ItemDataRole.UserRole + 1
    UrlRole = Qt.ItemDataRole.UserRole + 2
    TitleRole = Qt.ItemDataRole.UserRole + 3
    ProgressRole = Qt.ItemDataRole.UserRole + 4
    StageRole = Qt.ItemDataRole.UserRole + 5
    DetailRole = Qt.ItemDataRole.UserRole + 6
    StateRole = Qt.ItemDataRole.UserRole + 7
    ErrorRole = Qt.ItemDataRole.UserRole + 8
    PlaylistIdRole = Qt.ItemDataRole.UserRole + 9
    VideoIdRole = Qt.ItemDataRole.UserRole + 10

    countChanged = Signal()
    errorOccurred = Signal(str)
    noticeOccurred = Signal(str)
    trackAdded = Signal(int)
    # Bắn sau khi thành viên của MỘT track đổi. Không có nó thì dòng đã vào
    # database nhưng model đang mở vẫn hiện số cũ — bug thật đã gặp: chép bài
    # vào track xong, đĩa và DB đều đúng, mà lưới vẫn trống.
    playlistContentsChanged = Signal(int)
    historyChanged = Signal()
    # Bắn mỗi khi danh sách việc đang tải đổi (thêm/xong/tiến độ). QML dùng
    # nó để vẽ lại các hàng "đang tải" của ĐÚNG track đang mở.
    pendingChanged = Signal()
    # Số bài có dòng mà chưa có file. Đổi khi tải lại xong, và khi vòng đồng bộ
    # vừa mang thêm bài lạ về. Là Property chứ không phải Slot: binding QML gọi
    # Slot thì không bao giờ tính lại (CB-019).
    missingChanged = Signal()

    def __init__(
        self,
        downloader: Downloader,
        library: Any,
        playlist_repository: PlaylistRepository,
        history: DownloadHistoryRepository | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._downloader = downloader
        self._library = library
        self._playlist_repository = playlist_repository
        # Optional so the existing tests can build a bridge without a ledger.
        self._history = history
        self._jobs: list[_Job] = []
        self._missing_count = 0
        self._next_job_id = 1
        self._pool = QThreadPool(self)
        self._alive: dict[int, _DownloadRunnable] = {}
        # Two at a time: enough to feel parallel, few enough to stay polite to
        # YouTube and to keep ffmpeg from fighting itself for CPU.
        self._pool.setMaxThreadCount(2)

    # -- QAbstractListModel ---------------------------------------------------

    def roleNames(self) -> dict[int, QByteArray]:
        return {
            self.JobIdRole: QByteArray(b"jobId"),
            self.UrlRole: QByteArray(b"url"),
            self.TitleRole: QByteArray(b"title"),
            self.ProgressRole: QByteArray(b"progress"),
            self.StageRole: QByteArray(b"stage"),
            self.DetailRole: QByteArray(b"detail"),
            self.StateRole: QByteArray(b"state"),
            self.ErrorRole: QByteArray(b"error"),
            self.PlaylistIdRole: QByteArray(b"playlistId"),
            self.VideoIdRole: QByteArray(b"videoId"),
        }

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._jobs)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._jobs)):
            return None
        job = self._jobs[index.row()]
        match role:
            case self.JobIdRole:
                return job.job_id
            case self.UrlRole:
                return job.url
            case self.TitleRole:
                return job.title or job.url
            case self.ProgressRole:
                return job.fraction
            case self.StageRole:
                return job.stage
            case self.DetailRole:
                return job.detail
            case self.StateRole:
                return job.state
            case self.ErrorRole:
                return job.error
            case self.PlaylistIdRole:
                return -1 if job.playlist_id is None else job.playlist_id
            case self.VideoIdRole:
                return job.video_id
        return None

    # -- Job bookkeeping ------------------------------------------------------

    def _row_of(self, job_id: int) -> int:
        for row, job in enumerate(self._jobs):
            if job.job_id == job_id:
                return row
        return -1

    def _emit_row_changed(self, row: int) -> None:
        idx = self.index(row, 0)
        self.dataChanged.emit(idx, idx)
        self.pendingChanged.emit()

    @Slot(int, result="QVariantList")
    def pendingIdsFor(self, playlist_id: int) -> list:
        """Job ids downloading into this track — see download_rows.active_ids_for."""
        return download_rows.active_ids_for(self._jobs, playlist_id)

    @Slot(int, result="QVariantMap")
    def jobForTrack(self, track_id: int) -> dict:
        """The download filling THIS library row right now, or an empty map.

        Bài về theo đường đồng bộ đã có sẵn một dòng trong track trước khi mp3
        chạm đĩa (cái vỏ đi trước, file đi sau), nên nó KHÔNG mọc thêm một hàng
        "đang tải" ở cuối danh sách như bài dán link — hàng của nó đã ở đó rồi.
        Muốn nó nói được là đang cài thì phải hỏi ngược: dòng số này có việc tải
        nào đang chạy không. Khoá là `track_id`, không phải mã video: từ CB-036
        một bài nằm trong hai track là hai dòng, và mỗi dòng chờ riêng.
        """
        for job in self._jobs:
            if job.track_id == track_id and download_rows.is_active(job):
                return download_rows.info_of(job)
        return {}

    @Slot(int, result="QVariantMap")
    def jobInfo(self, job_id: int) -> dict:
        """Current state of one job, so a row can update itself without being rebuilt."""
        row = self._row_of(job_id)
        return download_rows.info_of(self._jobs[row]) if row >= 0 else {}

    @Slot(int, result="QVariantList")
    def pendingFor(self, playlist_id: int) -> list:
        """Jobs downloading into this track, as objects for QML."""
        return download_rows.active_for(self._jobs, playlist_id)

    @Slot(int, result=bool)
    def isDownloadingInto(self, playlist_id: int) -> bool:
        """Whether this track has anything downloading."""
        return download_rows.any_active_for(self._jobs, playlist_id)

    # -- Public slots ---------------------------------------------------------

    @Slot(str, result=bool)
    def looksLikeUrl(self, text: str) -> bool:
        """True when the text is a YouTube link, so the UI knows to download rather than search."""
        return is_youtube_url(text)

    @Slot(str)
    def add(self, raw_url: str) -> None:
        """Validate a pasted URL and queue it for download."""
        try:
            ref = parse_url(raw_url)
        except LumenError as exc:
            self.errorOccurred.emit(exc.user_message)
            return

        if any(job.video_id == ref.video_id and job.state in (STATE_QUEUED, STATE_RUNNING)
               for job in self._jobs):
            self.errorOccurred.emit("Bài này đang được tải rồi.")
            return

        if self._library.has_source(ref.video_id):
            self.errorOccurred.emit("Bài này đã có trong thư viện.")
            return

        job = _Job(job_id=self._next_job_id, url=ref.canonical_url, video_id=ref.video_id)
        self._next_job_id += 1

        self.beginInsertRows(QModelIndex(), len(self._jobs), len(self._jobs))
        self._jobs.append(job)
        self.endInsertRows()
        self.countChanged.emit()
        self.pendingChanged.emit()

        self._start(job)

    @Slot(str, int)
    @Slot(str, int, "QVariantMap")
    def addToPlaylist(self, raw_url: str, playlist_id: int, hint: dict | None = None) -> None:
        """Validate a pasted URL and get it into one track: download, or copy if already owned."""
        try:
            ref = parse_url(raw_url)
        except LumenError as exc:
            self.errorOccurred.emit(exc.user_message)
            return

        # Bridge chỉ đi hỏi sự thật; luật nằm ở core/download_plan.py.
        playlist = self._playlist_repository.get(playlist_id)
        existing = self._library.get_by_source(ref.video_id)
        decision = plan_for(
            already_downloading=any(
                job.video_id == ref.video_id
                and job.playlist_id == playlist_id
                and job.state in (STATE_QUEUED, STATE_RUNNING)
                for job in self._jobs
            ),
            already_in_track=any(
                track.source_id == ref.video_id
                for track in self._playlist_repository.tracks(playlist_id)
            ),
            track_exists=playlist is not None,
            already_in_library=existing is not None,
        )
        if decision.refused:
            self.errorOccurred.emit(decision.message)
            return

        dest_dir = track_dir(playlist.name)
        if decision.action == ACTION_COPY:
            self._copy_existing_into_playlist(existing, dest_dir, playlist_id)
            return

        facts = hint or {}
        job = _Job(
            job_id=self._next_job_id,
            url=ref.canonical_url,
            video_id=ref.video_id,
            playlist_id=playlist_id,
            target_dir=dest_dir,
            hint_title=str(facts.get("title", "")),
            hint_artist=str(facts.get("artist", "")),
            hint_duration_text=str(facts.get("durationText", "")),
            hint_thumbnail=str(facts.get("thumbnail", "")),
        )
        self._next_job_id += 1

        self.beginInsertRows(QModelIndex(), len(self._jobs), len(self._jobs))
        self._jobs.append(job)
        self.endInsertRows()
        self.countChanged.emit()
        self.pendingChanged.emit()

        self._start(job)

    # -- Tải lại bài đồng bộ về -----------------------------------------------

    @Slot()
    def refreshMissing(self) -> None:
        """Re-count the songs that have a row here but no file, and tell QML."""
        try:
            self._missing_count = len(self._library.tracks_needing_file())
        except LumenError as exc:
            log.warning("Không đếm được bài thiếu file: %s", exc)
            return
        self.missingChanged.emit()

    @Slot()
    def redownloadMissing(self) -> None:
        """Queue every synced-but-not-downloaded song, oldest first."""
        try:
            waiting = self._library.tracks_needing_file()
        except LumenError as exc:
            self.errorOccurred.emit(exc.user_message)
            return
        results = [self._refill(track) for track in waiting]
        copied = results.count(_REFILL_COPIED)
        # Dòng đang CHỜ một việc tải cùng bài cũng là "đang được lấy về" theo
        # mắt người dùng — nó chỉ đi ké, không phải bị bỏ quên.
        queued = results.count(_REFILL_QUEUED) + results.count(_REFILL_WAITING)
        self.refreshMissing()
        if copied == 0 and queued == 0:
            self.noticeOccurred.emit("Không có bài nào cần tải lại.")
            return
        if queued == 0:
            self.noticeOccurred.emit(f"Đã lấy lại {copied} bài từ bản có sẵn trên máy.")
            return
        if copied == 0:
            self.noticeOccurred.emit(f"Đang tải lại {queued} bài.")
            return
        self.noticeOccurred.emit(
            f"Đã lấy lại {copied} bài từ bản có sẵn, đang tải {queued} bài."
        )

    @Slot(int)
    def redownload(self, track_id: int) -> None:
        """Queue one file-less row so its song comes back from the original link."""
        track = self._library.track_for(track_id)
        if track is None:
            self.errorOccurred.emit("Bài này không còn trong thư viện.")
            return
        if track.file_path:
            self.errorOccurred.emit("Bài này đã có file trên máy.")
            return
        outcome = self._refill(track)
        if outcome == _REFILL_COPIED:
            self.refreshMissing()
            self.noticeOccurred.emit("Đã lấy lại từ bản có sẵn trên máy, không cần tải.")
            return
        if outcome == _REFILL_WAITING:
            self.noticeOccurred.emit("Bài này đang tải cho một track khác, xong sẽ chép sang.")
            return
        if outcome != _REFILL_QUEUED:
            self.errorOccurred.emit("Bài này đang được tải rồi.")

    def _refill(self, track: Track) -> str:
        """Get one file-less row its file: from this disk if we have it, else from the link.

        Thứ tự là cả quyết định (CB-036, chủ dự án chốt 2026-08-27): bản mp3 của
        đúng bài đó có thể đang nằm ngay trên đĩa, thuộc về một track khác. Chép
        thì xong ngay, không tốn lượt, và không dính lỗi 403 của yt-dlp. Link là
        đường lui, không phải đường đầu.
        """
        stored = download_refill.fill_from_disk(
            self._library, track, self._downloader.music_dir
        )
        if stored is not None:
            self._announce_filled(stored.id or -1)
            return _REFILL_COPIED
        # Cùng một bài, hai track, cả hai dòng đều trống: một lần tải là đủ cho
        # cả hai. Dòng sau chờ, rồi `_fill_siblings_from_disk` chép cho nó ngay
        # khi bản kia chạm đĩa.
        if self._fetching(track.source_id or ""):
            return _REFILL_WAITING
        return _REFILL_QUEUED if self._queue_refill(track) else ""

    def _fetching(self, video_id: str) -> bool:
        """True khi đã có một việc tải bài này đang chờ hoặc đang chạy."""
        return bool(video_id) and any(
            job.video_id == video_id and job.state in (STATE_QUEUED, STATE_RUNNING)
            for job in self._jobs
        )

    def _fill_siblings_from_disk(self, source_id: str) -> None:
        """Bài vừa chạm đĩa: mọi dòng khác đang chờ đúng bài đó chép ngay, khỏi tải lại.

        Đây là nửa sau của luật "một bài tải một lần" — nửa đầu là `_REFILL_WAITING`.
        Chạy sau MỌI lần tải xong, không riêng lần tải lại: người dùng dán tay
        một link mà máy đang có dòng chờ cùng bài thì cũng đáng được lấp.
        """
        if not source_id:
            return
        try:
            waiting = [
                row for row in self._library.tracks_needing_file()
                if row.source_id == source_id
            ]
        except LumenError:
            log.exception("Không đọc được danh sách dòng còn chờ %s", source_id)
            return
        filled_any = False
        for row in waiting:
            stored = download_refill.fill_from_disk(
                self._library, row, self._downloader.music_dir
            )
            if stored is not None:
                self._announce_filled(stored.id or -1)
                filled_any = True
        if filled_any:
            self.refreshMissing()

    def _announce_filled(self, track_id: int) -> None:
        """Tell every track holding this row that it just stopped being a silent song.

        `playlistContentsChanged` chỉ được nghe bởi ĐÚNG track mang số đó, nên
        phải bắn từng track một — không bắn thì bài câm tới lần mở app sau
        (CB-029).
        """
        for owner_id in self._playlist_repository.playlists_of(track_id):
            self.playlistContentsChanged.emit(owner_id)

    def _queue_refill(self, track: Track) -> bool:
        """Put one file-less row in the queue; False when there is nothing to queue.

        KHÔNG hỏi hạn mức. Đây là nhạc người dùng đã có ở máy khác, không phải
        một lần tải mới — chặn ở đây là bắt người ta trả hai lần cho một bài.
        Ba chỗ nữa cùng luật này: `_on_finished` không cộng sổ, `add()` không
        còn coi dòng chỗ trống là "đã có trong thư viện", và nhánh CHÉP không
        vớ phải đường dẫn rỗng.
        """
        video_id = track.source_id or ""
        if not video_id or track.id is None:
            return False
        # Chống trùng theo DÒNG, không theo mã video. Từ CB-036 mỗi track giữ
        # dòng riêng, nên hai dòng chỗ trống cùng một bài đứng chờ là chuyện
        # thường — chặn theo mã video thì dòng thứ hai không bao giờ tới lượt.
        if any(job.track_id == track.id and job.state in (STATE_QUEUED, STATE_RUNNING)
               for job in self._jobs):
            return False

        # `target_dir` vẫn để trống, tức thư mục nhạc chung: dòng chỗ trống có
        # thể đang nằm trong nhiều track (database dựng trước bản vá CB-036),
        # và chép mỗi track một bản là quay lại đúng cái lỗi việc này sinh ra
        # để chặn. Đường CHÉP ở `_refill` nhắm cùng thư mục đó.
        job = _Job(
            job_id=self._next_job_id,
            url=track.source_url or watch_url(video_id),
            video_id=video_id,
            hint_title=track.title,
            hint_artist=track.artist,
            refill=True,
            track_id=track.id,
        )
        self._next_job_id += 1

        self.beginInsertRows(QModelIndex(), len(self._jobs), len(self._jobs))
        self._jobs.append(job)
        self.endInsertRows()
        self.countChanged.emit()
        self.pendingChanged.emit()

        self._start(job)
        return True

    def _copy_existing_into_playlist(self, existing: Track, dest_dir: Path, playlist_id: int) -> None:
        """Reuse an already-downloaded file for a new track instead of downloading it again."""
        copied_path = copy_into(Path(existing.file_path), dest_dir)

        # File đích có thể ĐÃ có một dòng trỏ vào (bản sót từ lần xoá cũ, hoặc
        # người dùng tự chép vào thư mục track). `file_path` là UNIQUE nên tạo
        # dòng mới sẽ nổ và báo "bài đã có" — trong khi việc đúng là dùng lại
        # chính dòng đó và chỉ thêm nó vào track.
        owner = self._library.get_by_path(str(copied_path))
        if owner is not None and owner.id is not None:
            if self._playlist_repository.add_track(playlist_id, owner.id):
                self.playlistContentsChanged.emit(playlist_id)
                self.noticeOccurred.emit(f"Đã thêm: {owner.title}")
            else:
                self.errorOccurred.emit("Bài này đã có trong track.")
            return
        # Chép một bài sang track khác là DÒNG MỚI, độc lập (QĐ-019). Nó mang
        # theo cả tên riêng người dùng đã đặt — chép cuốn băng thì chép luôn cái
        # nhãn — nhưng từ giây phút này hai nhãn rời nhau: sửa bên nào bên ấy
        # đổi. Mốc là BÂY GIỜ, vì dòng này vừa ra đời ở máy này.
        track = Track(
            source_id=existing.source_id,
            source_url=existing.source_url,
            real_name=existing.real_name,
            display_name=existing.display_name,
            display_name_updated_at=(
                sync_clock.now() if existing.display_name else 0
            ),
            artist=existing.artist,
            duration_ms=existing.duration_ms,
            file_path=str(copied_path),
            cover_path=existing.cover_path,
        )
        try:
            stored = self._library.add_track(track)
            if stored.id is not None:
                self._playlist_repository.add_track(playlist_id, stored.id)
                self.playlistContentsChanged.emit(playlist_id)
        except LumenError as exc:
            self.errorOccurred.emit(exc.user_message)
            return
        self.noticeOccurred.emit("Đã thêm từ thư viện, không cần tải lại.")
        self.trackAdded.emit(stored.id or -1)

    def _start(self, job: _Job) -> None:
        job.state = STATE_RUNNING
        job.error = ""
        job.cancel_event.clear()
        runnable = _DownloadRunnable(job, self._downloader)
        # Xem chú thích cùng nội dung trong search_bridge.py: không giữ tham
        # chiếu thì lớp bọc Python (và đối tượng mang signal) có thể bị thu gom
        # trước khi worker emit, và kết quả im lặng không bao giờ về.
        self._alive[job.job_id] = runnable
        # Queued on purpose: these fire from a worker thread and must land on
        # the main thread before touching the model or the database.
        runnable.signals.progress.connect(self._on_progress, Qt.ConnectionType.QueuedConnection)
        runnable.signals.finished.connect(self._on_finished, Qt.ConnectionType.QueuedConnection)
        runnable.signals.failed.connect(self._on_failed, Qt.ConnectionType.QueuedConnection)
        self._pool.start(runnable)

    @Slot(int)
    def cancel(self, job_id: int) -> None:
        """Ask a running job to stop at its next progress callback."""
        row = self._row_of(job_id)
        if row < 0:
            return
        self._jobs[row].cancel_event.set()

    @Slot(int)
    def retry(self, job_id: int) -> None:
        """Re-run a failed job."""
        row = self._row_of(job_id)
        if row < 0 or self._jobs[row].state not in (STATE_FAILED, STATE_CANCELLED):
            return
        job = self._jobs[row]
        job.fraction = -1.0
        job.stage = ""
        job.detail = ""
        self._start(job)
        self._emit_row_changed(row)

    @Slot(int)
    def dismiss(self, job_id: int) -> None:
        """Remove a finished or failed job from the strip."""
        row = self._row_of(job_id)
        if row < 0:
            return
        self.beginRemoveRows(QModelIndex(), row, row)
        del self._jobs[row]
        self.endRemoveRows()
        self.countChanged.emit()
        self.pendingChanged.emit()

    # -- Worker callbacks (main thread) ---------------------------------------

    @Slot(int, str, float, str)
    def _on_progress(self, job_id: int, stage: str, fraction: float, detail: str) -> None:
        row = self._row_of(job_id)
        if row < 0:
            return
        job = self._jobs[row]
        job.stage = stage
        job.fraction = fraction
        job.detail = detail
        self._emit_row_changed(row)

    @Slot(int, object)
    def _on_finished(self, job_id: int, result: DownloadResult) -> None:
        self._alive.pop(job_id, None)
        row = self._row_of(job_id)
        if row < 0:
            return
        job = self._jobs[row]
        job.title = result.title
        job.state = STATE_DONE
        job.fraction = 1.0
        job.detail = "Hoàn tất."

        # Vừa tải xong: tên này là tên YouTube nói. Tên riêng để trống — dòng
        # chỗ trống nếu có sẵn thì `attach_file` lấp vào chứ không đi qua đây.
        track = Track(
            source_id=result.video_id,
            source_url=result.source_url,
            real_name=result.title,
            artist=result.artist,
            duration_ms=result.duration_ms,
            file_path=str(result.file_path),
            cover_path=str(result.cover_path) if result.cover_path else None,
        )
        try:
            # LẤP dòng chỗ trống nếu bài này đã có một dòng chờ sẵn, chỉ thiếu
            # file. `add_track()` thẳng tay ở đây là đẻ ra dòng thứ hai và bỏ
            # dòng đang nằm trong track lại, câm vĩnh viễn — QĐ-016.
            stored, filled = download_refill.store(self._library, track, job.track_id)
            if job.playlist_id is not None and stored.id is not None:
                self._playlist_repository.add_track(job.playlist_id, stored.id)
                self.playlistContentsChanged.emit(job.playlist_id)
        except LumenError as exc:
            job.state = STATE_FAILED
            job.error = exc.user_message
            self._emit_row_changed(row)
            self.errorOccurred.emit(exc.user_message)
            return

        # Ghi sổ SAU khi bài đã vào thư viện: sổ ghi "đã từng tải", nên chỉ
        # đúng khi việc tải thật sự thành công. Ghi hụt sổ không được phép làm
        # hỏng một lần tải vốn đã tốt (repository tự nuốt lỗi).
        if self._history is not None:
            self._history.record(
                url=result.source_url,
                source_id=result.video_id,
                title=result.title,
                artist=result.artist,
                uploader=result.uploader,
            )
            self.historyChanged.emit()

        if filled:
            # Dòng vừa được lấp đã nằm sẵn trong track nào đó, và lưới đang mở
            # vẫn hiện nó như một bài câm.
            self.refreshMissing()
            self._announce_filled(stored.id or -1)

        # File đã nằm trên đĩa rồi: dòng nào của track khác còn chờ đúng bài này
        # thì chép cho xong, đừng bắt nó đi tải một lần nữa (CB-036).
        self._fill_siblings_from_disk(result.video_id)

        self._emit_row_changed(row)
        self.noticeOccurred.emit(f"Đã thêm: {result.title}")
        self.trackAdded.emit(stored.id or -1)
        QTimer.singleShot(_DONE_LINGER_MS, lambda: self.dismiss(job_id))

    @Slot(int, str)
    def _on_failed(self, job_id: int, user_message: str) -> None:
        row = self._row_of(job_id)
        if row < 0:
            return
        job = self._jobs[row]
        if not user_message:  # cancelled by the user, not an error
            job.state = STATE_CANCELLED
            job.detail = "Đã huỷ."
            self._emit_row_changed(row)
            QTimer.singleShot(_DONE_LINGER_MS, lambda: self.dismiss(job_id))
            return
        job.state = STATE_FAILED
        job.error = user_message
        self._emit_row_changed(row)
        self.errorOccurred.emit(user_message)

    count = Property(int, lambda self: len(self._jobs), notify=countChanged)
    #: Số bài có dòng ở máy này mà chưa có file — hàng đợi "tải lại từ link gốc".
    missingCount = Property(int, lambda self: self._missing_count, notify=missingChanged)
