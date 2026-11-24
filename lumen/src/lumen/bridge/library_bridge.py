"""Qt list model over the track library.

Threading contract (CLAUDE.md muc 4): every method here runs on the Qt main
thread and is the ONLY place allowed to touch TrackRepository. Download workers
never write to the database themselves -- they hand their result back through a
queued signal and this model performs the write.

Sorting is done in Python, not SQL, on purpose: later ultra tasks sort by things
SQL does not know (recommendation score), and one code path beats two.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, Property, Qt, Signal, Slot

from lumen.core.formatting import format_duration, format_relative_date
from lumen.core.models import Track, one_row_per_song
from lumen.core.repository import TrackRepository

log = logging.getLogger(__name__)

_SORT_KEYS = ("index", "title", "artist", "duration", "added")


class LibraryBridge(QAbstractListModel):
    """Expose the track library to QML as a sortable, searchable list model."""

    TrackIdRole = Qt.ItemDataRole.UserRole + 1
    TitleRole = Qt.ItemDataRole.UserRole + 2
    ArtistRole = Qt.ItemDataRole.UserRole + 3
    DurationTextRole = Qt.ItemDataRole.UserRole + 4
    DurationMsRole = Qt.ItemDataRole.UserRole + 5
    CoverPathRole = Qt.ItemDataRole.UserRole + 6
    AddedTextRole = Qt.ItemDataRole.UserRole + 7
    PlayCountRole = Qt.ItemDataRole.UserRole + 8
    IsPlayingRole = Qt.ItemDataRole.UserRole + 9

    countChanged = Signal()
    sortChanged = Signal()
    searchChanged = Signal()
    errorOccurred = Signal(str)
    trackRemoved = Signal(int)

    def __init__(self, repository: TrackRepository, parent: Any = None) -> None:
        super().__init__(parent)
        self._repository = repository
        self._tracks: list[Track] = []
        self._search = ""
        self._sort_key = "added"
        self._sort_descending = True
        self._playing_track_id = -1
        self.refresh()

    def roleNames(self) -> dict[int, QByteArray]:
        return {
            self.TrackIdRole: QByteArray(b"trackId"),
            self.TitleRole: QByteArray(b"title"),
            self.ArtistRole: QByteArray(b"artist"),
            self.DurationTextRole: QByteArray(b"durationText"),
            self.DurationMsRole: QByteArray(b"durationMs"),
            self.CoverPathRole: QByteArray(b"coverPath"),
            self.AddedTextRole: QByteArray(b"addedText"),
            self.PlayCountRole: QByteArray(b"playCount"),
            self.IsPlayingRole: QByteArray(b"isPlaying"),
        }

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._tracks)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._tracks)):
            return None
        track = self._tracks[index.row()]
        match role:
            case self.TrackIdRole:
                return track.id or -1
            case self.TitleRole:
                return track.title
            case self.ArtistRole:
                return track.artist
            case self.DurationTextRole:
                return format_duration(track.duration_ms)
            case self.DurationMsRole:
                return track.duration_ms
            case self.CoverPathRole:
                return track.cover_path or ""
            case self.AddedTextRole:
                return format_relative_date(track.added_at)
            case self.PlayCountRole:
                return track.play_count
            case self.IsPlayingRole:
                return track.id == self._playing_track_id
        return None

    def _sorted(self, tracks: list[Track]) -> list[Track]:
        """Order tracks by the active sort key."""
        match self._sort_key:
            case "title":
                keyed = sorted(tracks, key=lambda t: t.title.casefold())
            case "artist":
                keyed = sorted(tracks, key=lambda t: (t.artist.casefold(), t.title.casefold()))
            case "duration":
                keyed = sorted(tracks, key=lambda t: t.duration_ms)
            case _:
                keyed = sorted(tracks, key=lambda t: (t.added_at, t.id or 0))
        return list(reversed(keyed)) if self._sort_descending else keyed

    @Slot()
    def refresh(self) -> None:
        """Reload the whole model from the database."""
        try:
            tracks = self._repository.list_all(search=self._search or None)
        except Exception as exc:  # repository already wraps sqlite errors
            log.exception("Cannot load library")
            self.errorOccurred.emit(getattr(exc, "user_message", "Không đọc được thư viện."))
            return
        self.beginResetModel()
        self._tracks = self._sorted(one_row_per_song(tracks))
        self.endResetModel()
        self.countChanged.emit()

    # -- Slots for QML --------------------------------------------------------

    @Slot(str)
    def setSearch(self, text: str) -> None:
        """Filter the library by a case-insensitive substring of title or artist."""
        text = (text or "").strip()
        if text == self._search:
            return
        self._search = text
        self.searchChanged.emit()
        self.refresh()

    @Slot(str)
    def toggleSort(self, key: str) -> None:
        """Sort by key, flipping direction when the same column is clicked twice."""
        if key not in _SORT_KEYS:
            log.warning("Ignoring unknown sort key %r", key)
            return
        key = "added" if key == "index" else key
        if key == self._sort_key:
            self._sort_descending = not self._sort_descending
        else:
            self._sort_key = key
            # Dates read best newest-first; text reads best A-Z.
            self._sort_descending = key == "added"
        self.sortChanged.emit()
        self.refresh()

    @Slot(int, result=bool)
    def removeTrack(self, track_id: int) -> bool:
        """Delete a track row from the database and drop it from the model."""
        try:
            removed = self._repository.delete(track_id)
        except Exception as exc:
            log.exception("Cannot delete track %s", track_id)
            self.errorOccurred.emit(getattr(exc, "user_message", "Không xoá được bài này."))
            return False
        if removed:
            # Before the reload, so the player drops it from the queue first.
            self.trackRemoved.emit(track_id)
            self.refresh()
        return removed

    def track_for(self, track_id: int) -> Track | None:
        """Return one track by id, or None when it is no longer in the library."""
        try:
            return self._repository.get(track_id)
        except Exception:
            log.exception("Cannot read track %s", track_id)
            return None

    def ordered_track_ids(self) -> list[int]:
        """Track ids in exactly the order the library is showing them.

        The play queue is built from this, so playback follows what is on screen.
        """
        return [t.id for t in self._tracks if t.id is not None]

    def record_play(self, track_id: int) -> None:
        """Count one listen. Feeds the recommendation engine."""
        try:
            self._repository.record_play(track_id)
        except Exception:
            # A missed play count must never interrupt playback.
            log.exception("Cannot record play for track %s", track_id)
            return
        # NOT refresh(): a full reset mid-song throws away scroll + hover state.
        # One counter changed on one row, so say exactly that.
        for row, track in enumerate(self._tracks):
            if track.id == track_id:
                track.play_count += 1
                cell = self.index(row, 0)
                self.dataChanged.emit(cell, cell, [self.PlayCountRole])
                return

    def has_source(self, source_id: str) -> bool:
        """True when a track from this YouTube video is already DOWNLOADED here."""
        # "Có dòng" không còn bằng "có bài": từ v9 một bài đồng bộ về có dòng
        # chỗ trống, không có file. Trả True ở đó là từ chối đúng cái link mà
        # người dùng đang dán để lấy lại bài mình đã mất — QĐ-016.
        return self.get_by_source(source_id) is not None

    def get_by_path(self, file_path: str) -> Track | None:
        """Dòng đang giữ đúng file này — xem TrackRepository.get_by_file_path."""
        return self._repository.get_by_file_path(file_path)

    def get_by_source(self, source_id: str) -> Track | None:
        """Return one DOWNLOADED track from this YouTube video, if any."""
        # `get_by_source_id` xếp bản có file lên trước, nên bản trả về mà rỗng
        # thì cả thư viện không có bản nào có file. Người gọi hỏi câu này để
        # CHÉP file sang track khác: đưa dòng chỗ trống ra là chép hư không.
        track = self._repository.get_by_source_id(source_id)
        return track if track is not None and track.file_path else None

    def placeholder_for(self, source_id: str) -> Track | None:
        """Return the file-less row waiting for this video, if that is all we have."""
        track = self._repository.get_by_source_id(source_id)
        return track if track is not None and not track.file_path else None

    def tracks_needing_file(self) -> list[Track]:
        """Return every row synced here but never downloaded — the re-download worklist."""
        return self._repository.list_needing_file()

    def attach_file(self, track_id: int, downloaded: Track) -> Track | None:
        """Fill a file-less row with a finished download. Main thread only."""
        stored = self._repository.attach_file(track_id, downloaded)
        if stored is not None:
            self.refresh()
        return stored

    def add_track(self, track: Track) -> Track:
        """Insert a freshly downloaded track. Main thread only -- see module docstring."""
        stored = self._repository.add(track)
        self.refresh()
        return stored

    # -- Properties -----------------------------------------------------------

    count = Property(int, lambda self: len(self._tracks), notify=countChanged)
    searchText = Property(str, lambda self: self._search, notify=searchChanged)
    sortKey = Property(str, lambda self: self._sort_key, notify=sortChanged)
    sortDescending = Property(bool, lambda self: self._sort_descending, notify=sortChanged)
