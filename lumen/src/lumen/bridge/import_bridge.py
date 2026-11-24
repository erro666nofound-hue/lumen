"""The door an mp3 already on this machine walks through to become a track.

Đối lại với `download_bridge.py`: cùng đích (một dòng `tracks` nằm trong một
track), khác hẳn đường đi. Không mạng, không yt-dlp, không hạn mức gói — chép
một file của chính người dùng vào thư mục của app thì không tiêu băng thông
của ai (QĐ-010: Free là máy nghe nhạc trọn vẹn).

Luật luồng (CLAUDE.md mục 4), chỗ quan trọng nhất ở file này:

* Chép file và đọc thẻ ID3 chạy trên worker của QThreadPool. Chọn 200 bài một
  lúc là 200 lần đọc đĩa; làm ở luồng chính là app đứng hình.
* Worker KHÔNG chạm SQLite và không chạm model. Nó chỉ phát signal, giao
  hàng kiểu queued, nên mọi cú ghi database xảy ra trên luồng chính.

Dòng sinh ra ở đây KHÔNG có `source_id` — chủ ý, xem `core/mp3_import.py`. Nó
CÓ `content_hash`, băm ngay trên worker cùng lúc chép file (QĐ-027): đó là thứ
cho nó một danh tính để đi vào bản kê, và là địa chỉ của nó trong kho R2.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QUrl, Property, Signal, Slot

from lumen.core import mp3_import
from lumen.core.errors import LumenError
from lumen.core.library_files import duplicate_into
from lumen.core.models import Track
from lumen.core.mp3_import import ImportedSong
from lumen.core.paths import covers_dir, track_dir
from lumen.core.repository import PlaylistRepository

log = logging.getLogger(__name__)


class _ImportSignals(QObject):
    """Signals for one batch, owned by the runnable so nothing dies mid-flight."""

    #: `(ImportedSong, đường dẫn đã chép, sha256 của bản đã chép)`.
    ready = Signal(object, str, str)
    failed = Signal(str)
    done = Signal()


class _ImportRunnable(QRunnable):
    """Copy each picked mp3 into the track's folder and read its tags. Worker thread."""

    def __init__(self, paths: list[Path], dest_dir: Path) -> None:
        super().__init__()
        self._paths = paths
        self._dest_dir = dest_dir
        self.signals = _ImportSignals()

    def run(self) -> None:
        for path in self._paths:
            try:
                song = mp3_import.read_song(path)
                # `duplicate_into` chứ không phải `copy_into`: gặp một file y
                # hệt nằm sẵn ở đích, `copy_into` trả về CHÍNH file đó, mà
                # `tracks.file_path` là UNIQUE — dòng mới lấp hụt và nằm câm
                # (CB-036). Nhập hai lần cùng một bài là hai bản băng riêng.
                copied = duplicate_into(path, self._dest_dir)
                # Băm BẢN ĐÃ CHÉP, không băm file gốc. Cột `content_hash` là
                # địa chỉ của dòng này trong kho R2, và máy chủ băm lại thân
                # yêu cầu trước khi nhận — hash của một file khác thì cú đẩy
                # chết ở tận đầu kia với "bytes không khớp địa chỉ".
                #
                # Chạy ở worker: một file 30 MiB băm mất một nhịp thấy được,
                # và một đợt nhập có thể là 200 file liên tiếp.
                digest = mp3_import.file_digest(copied)
            except LumenError as exc:
                self.signals.failed.emit(exc.user_message or str(exc))
                continue
            except OSError as exc:
                log.warning("Failed to copy %s: %s", path, exc)
                self.signals.failed.emit(f"Không chép được {path.name} vào track.")
                continue
            self.signals.ready.emit(song, str(copied), digest)
        self.signals.done.emit()


class ImportBridge(QObject):
    """Expose "bring an mp3 in from the disk" to QML."""

    errorOccurred = Signal(str)
    noticeOccurred = Signal(str)
    trackAdded = Signal(int)
    playlistContentsChanged = Signal(int)
    busyChanged = Signal()

    def __init__(
        self,
        library: object,
        playlist_repository: PlaylistRepository,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._library = library
        self._playlist_repository = playlist_repository
        self._pool = QThreadPool.globalInstance()
        # Giữ tham chiếu tới runnable đang chạy: buông ra thì lớp bọc Python
        # (và cái QObject mang signal) có thể bị thu gom trước lúc worker emit,
        # và kết quả im lặng không bao giờ về. Cùng lý do với `download_bridge`.
        self._alive: dict[int, _ImportRunnable] = {}
        self._next_batch_id = 1
        self._added = 0
        self._playlist_id = -1

    @Slot("QVariantList", int)
    @Slot(str, int)
    def importFiles(self, raw_paths: object, playlist_id: int) -> None:
        """Copy the picked mp3s into this track and give each one a row."""
        playlist = self._playlist_repository.get(playlist_id)
        if playlist is None:
            self.errorOccurred.emit("Track này không còn nữa.")
            return

        paths = self._resolve(raw_paths)
        if not paths:
            self.errorOccurred.emit("Chưa chọn file nào.")
            return
        if self._alive:
            self.errorOccurred.emit("Đang nhập một đợt rồi, đợi xong đã.")
            return

        self._added = 0
        self._playlist_id = playlist_id
        batch_id = self._next_batch_id
        self._next_batch_id += 1

        runnable = _ImportRunnable(paths, track_dir(playlist.name))
        self._alive[batch_id] = runnable
        # Queued: ba signal này phát từ luồng worker và phải hạ cánh ở luồng
        # chính TRƯỚC khi ai đó chạm vào database.
        runnable.signals.ready.connect(self._on_ready, Qt.ConnectionType.QueuedConnection)
        runnable.signals.failed.connect(self.errorOccurred, Qt.ConnectionType.QueuedConnection)
        runnable.signals.done.connect(
            lambda: self._on_done(batch_id), Qt.ConnectionType.QueuedConnection
        )
        self.busyChanged.emit()
        self._pool.start(runnable)

    def _resolve(self, raw_paths: object) -> list[Path]:
        """Turn whatever QML handed over — one string, or a list of QUrl — into paths."""
        items = [raw_paths] if isinstance(raw_paths, (str, QUrl)) else list(raw_paths or [])
        texts = []
        for item in items:
            # `FileDialog.selectedFiles` trả về QUrl, không phải chuỗi. `str()`
            # lên một QUrl ra `PySide6.QtCore.QUrl(...)` — nuốt cả cái đó vào
            # thì mọi đường dẫn đều sai mà không ai kêu.
            texts.append(item.toLocalFile() if isinstance(item, QUrl) else str(item))
        return [mp3_import.local_path(text) for text in texts if text.strip()]

    @Slot(object, str, str)
    def _on_ready(self, song: ImportedSong, copied_path: str, digest: str) -> None:
        """One file is on disk and read: give it a row. Main thread only."""
        destination = Path(copied_path)
        cover = mp3_import.save_cover(song, covers_dir(), destination)
        # `source_id`/`source_url` để NGUYÊN None. Chuỗi rỗng cũng "không có
        # link", nhưng `sync_state.NO_LINK` phải nhận ra nó và `get_by_source`
        # thì không được vớ phải nó — một dạng rỗng, không phải hai.
        #
        # `content_hash` thì CÓ: dòng này có danh tính, nên nó vào được bản kê
        # (`HAS_IDENTITY`). `NO_LINK` vẫn đúng — nhập từ đĩa thì mãi mãi không
        # có link để tải lại; mất file thì kéo về từ kho R2 (QĐ-027).
        track = Track(
            source_id=None,
            source_url=None,
            content_hash=digest,
            real_name=song.title,
            # Tag TPE1 KHÔNG được cất vào DB: file lạ rất hay ghi tên bài vào ô
            # tác giả, cất vào là sắp xếp theo nghệ sĩ hoá loạn. Cột tác giả của
            # bài custom do `Track.artist_label` nói — QĐ-025.
            artist="",
            duration_ms=song.duration_ms,
            file_path=str(destination),
            cover_path=str(cover) if cover else None,
        )
        try:
            stored = self._library.add_track(track)
        except LumenError as exc:
            self.errorOccurred.emit(exc.user_message)
            return
        if stored.id is not None and self._playlist_id >= 0:
            self._playlist_repository.add_track(self._playlist_id, stored.id)
        self._added += 1
        self.trackAdded.emit(stored.id or -1)

    def _on_done(self, batch_id: int) -> None:
        """The batch is finished: tell the track to redraw, once. Main thread only."""
        self._alive.pop(batch_id, None)
        if self._added > 0 and self._playlist_id >= 0:
            self.playlistContentsChanged.emit(self._playlist_id)
            # Câu này đổi nghĩa từ QĐ-027 và phải đổi theo, đúng từng chữ:
            # danh sách ĐÃ đi được (dòng có hash ⇒ có trong bản kê), còn cục
            # bytes thì chỉ vào kho khi có người đẩy nó lên. Giữ câu cũ
            # ("KHÔNG được sao lưu") là doạ thừa; nói thẳng "đã sao lưu" là
            # hứa thừa — file vẫn đang nằm mỗi ở máy này.
            self.noticeOccurred.emit(
                f"Đã nhập {self._added} bài từ máy. Tên và thứ tự đi theo đồng bộ; "
                "file nhạc chỉ lên kho khi bạn sao lưu."
            )
        self.busyChanged.emit()

    #: Đang có một đợt nhập chạy dở. QML khoá nút bằng cái này.
    busy = Property(bool, lambda self: bool(self._alive), notify=busyChanged)
