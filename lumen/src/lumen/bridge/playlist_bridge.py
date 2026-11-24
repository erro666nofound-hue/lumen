"""Qt list model over the user-created playlists ("track" trong tiếng Việt của app).

Threading contract (CLAUDE.md muc 4): every method here runs on the Qt main
thread and is the ONLY place allowed to touch PlaylistRepository, exactly like
LibraryBridge does for TrackRepository.

Naming note: in this codebase "Playlist" (core/models.py, core/repository.py)
is the thing the UI and this file's own docstrings call a "track" -- a
user-made collection of songs. Individual songs are "Track" in core/models.py
but "bài" (song) everywhere in the UI. See TrackSongsBridge for the model that
lists the songs inside one of these.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, Property, Qt, Signal, Slot

from lumen.core.errors import DuplicatePlaylistNameError
from lumen.core.library_files import remove_dir_if_empty, remove_files
from lumen.core.paths import track_dir
from lumen.core.repository import PlaylistRepository

log = logging.getLogger(__name__)


class PlaylistsBridge(QAbstractListModel):
    """Expose the sidebar's list of playlists to QML, with create/rename/delete."""

    PlaylistIdRole = Qt.ItemDataRole.UserRole + 1
    NameRole = Qt.ItemDataRole.UserRole + 2
    IconRole = Qt.ItemDataRole.UserRole + 3
    TrackCountRole = Qt.ItemDataRole.UserRole + 4

    countChanged = Signal()
    errorOccurred = Signal(str)
    playlistCreated = Signal(int)
    contentsChanged = Signal(int)

    def __init__(self, repository: PlaylistRepository, parent: Any = None) -> None:
        super().__init__(parent)
        self._repository = repository
        self._playlists: list = []
        self.refresh()

    # -- QAbstractListModel ---------------------------------------------------

    def roleNames(self) -> dict[int, QByteArray]:
        return {
            self.PlaylistIdRole: QByteArray(b"playlistId"),
            self.NameRole: QByteArray(b"name"),
            self.IconRole: QByteArray(b"icon"),
            self.TrackCountRole: QByteArray(b"trackCount"),
        }

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._playlists)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._playlists)):
            return None
        playlist = self._playlists[index.row()]
        match role:
            case self.PlaylistIdRole:
                return playlist.id or -1
            case self.NameRole:
                return playlist.name
            case self.IconRole:
                return playlist.icon
            case self.TrackCountRole:
                return playlist.track_count
        return None

    # -- Data loading ---------------------------------------------------------

    @Slot()
    def refresh(self) -> None:
        """Reload the whole model from the database."""
        try:
            playlists = self._repository.list_all()
        except Exception as exc:
            log.exception("Cannot load playlists")
            self.errorOccurred.emit(getattr(exc, "user_message", "Không đọc được danh sách track."))
            return
        self.beginResetModel()
        self._playlists = playlists
        self.endResetModel()
        self.countChanged.emit()

    # -- Slots for QML --------------------------------------------------------

    @Slot(str, result=int)
    def create(self, name: str) -> int:
        """Create a playlist and return its id, or -1 when the name is blank, taken, or it fails."""
        name = (name or "").strip()
        if not name:
            self.errorOccurred.emit("Tên track không được để trống.")
            return -1
        try:
            playlist = self._repository.create(name)
        except DuplicatePlaylistNameError as exc:
            # Người dùng gõ trùng tên là chuyện thường, không phải sự cố: bắt
            # riêng để log khỏi có traceback, và Popup ở Sidebar giữ nguyên chữ
            # họ vừa gõ (nó chỉ đóng khi id trả về >= 0).
            log.info("Refused duplicate playlist name %r", name)
            self.errorOccurred.emit(exc.user_message)
            return -1
        except Exception as exc:
            log.exception("Cannot create playlist %r", name)
            self.errorOccurred.emit(getattr(exc, "user_message", "Không tạo được track."))
            return -1
        self.refresh()
        new_id = playlist.id if playlist.id is not None else -1
        self.playlistCreated.emit(new_id)
        return new_id

    @Slot(int, str, result=bool)
    def rename(self, playlist_id: int, name: str) -> bool:
        """Rename a playlist; False when the name is blank, taken, or the playlist is gone."""
        name = (name or "").strip()
        if not name:
            self.errorOccurred.emit("Tên track không được để trống.")
            return False
        try:
            existing = self._repository.get(playlist_id)
            if existing is None:
                return False
            self._repository.rename(playlist_id, name)
        except DuplicatePlaylistNameError as exc:
            log.info("Refused duplicate playlist name %r", name)
            self.errorOccurred.emit(exc.user_message)
            return False
        except Exception as exc:
            log.exception("Cannot rename playlist %s", playlist_id)
            self.errorOccurred.emit(getattr(exc, "user_message", "Không đổi được tên track."))
            return False
        self.refresh()
        return True

    @Slot(int, result=bool)
    def remove(self, playlist_id: int) -> bool:
        """Delete a track: its rows, its mp3 files, and its folder.

        Until now this only dropped the playlist row, so every song inside kept
        its database row and its file on disk forever -- invisible, unplayable,
        eating space. The name has to be read BEFORE the delete: the folder is
        derived from it.
        """
        name = self.nameFor(playlist_id)
        if not name:
            return False                      # no such track: nothing to delete
        try:
            orphans = self._repository.delete_with_songs(playlist_id)
        except Exception as exc:
            log.exception("Cannot delete playlist %s", playlist_id)
            self.errorOccurred.emit(getattr(exc, "user_message", "Không xoá được track."))
            return False
        # mp3 only, NOT covers: copying a song into a second track reuses the
        # very same cover file (see DownloadBridge._copy_existing_into_playlist),
        # so deleting it here would blank the artwork of a track we never touched.
        remove_files([Path(t.file_path) for t in orphans if t.file_path])
        remove_dir_if_empty(track_dir(name))

        self.refresh()
        return True

    @Slot(int, result="QVariantList")
    def orderedIds(self, playlist_id: int) -> list:
        """Song ids of one playlist, in playlist order.

        The sidebar needs a track's queue without opening the track, so it
        cannot go through TrackSongsBridge (which only holds the open one).
        """
        try:
            return [t.id for t in self._repository.tracks(playlist_id) if t.id is not None]
        except Exception:
            log.exception("Cannot read song order for playlist %s", playlist_id)
            return []

    @Slot(result=int)
    def firstPlayable(self) -> int:
        """Id of the first track in sidebar order that has songs, or -1 (Space with nothing loaded)."""
        try:
            for playlist in self._repository.list_all():
                if playlist.track_count > 0 and playlist.id is not None:
                    return playlist.id
        except Exception:
            log.exception("Cannot list playlists")
        return -1

    @Slot(result="QVariantList")
    def simpleList(self) -> list:
        """Every track as {id, name}, in sidebar order (for small pickers)."""
        try:
            return [{"id": p.id, "name": p.name} for p in self._repository.list_all()]
        except Exception:
            log.exception("Cannot list playlists")
            return []

    @Slot(result="QVariantMap")
    def libraryStats(self) -> dict:
        """Return the library header line: track count, song count, total length in ms."""
        tracks = songs = total = 0
        try:
            for playlist in self._repository.list_all():
                tracks += 1
                rows = self._repository.tracks(playlist.id)
                songs += len(rows)
                total += sum(t.duration_ms for t in rows)
        except Exception:
            log.exception("Cannot read library stats")
        return {"tracks": tracks, "songs": songs, "totalMs": total}

    @Slot(int, result="QVariantMap")
    def cardFor(self, playlist_id: int) -> dict:
        """Return what a track card shows: up to four covers and the total length in ms."""
        try:
            tracks = self._repository.tracks(playlist_id)
        except Exception:
            log.exception("Cannot read songs of playlist %s", playlist_id)
            return {"covers": [], "totalMs": 0}
        return {"covers": [t.cover_path for t in tracks if t.cover_path][:4],
                "totalMs": sum(t.duration_ms for t in tracks)}

    @Slot(int, result=str)
    def nameFor(self, playlist_id: int) -> str:
        """Return the playlist's name, or an empty string when it does not exist."""
        try:
            playlist = self._repository.get(playlist_id)
        except Exception:
            log.exception("Cannot read playlist %s", playlist_id)
            return ""
        return playlist.name if playlist else ""

    @Slot(int, int, result=bool)
    def addSong(self, playlist_id: int, track_id: int) -> bool:
        """Add a song to a playlist; returns False (not an error) when it is already a member."""
        try:
            added = self._repository.add_track(playlist_id, track_id)
        except Exception as exc:
            log.exception("Cannot add track %s to playlist %s", track_id, playlist_id)
            self.errorOccurred.emit(getattr(exc, "user_message", "Không thêm được bài vào track."))
            return False
        if added:
            self.refresh()
            self.contentsChanged.emit(playlist_id)
        return added

    # -- Properties -------------------------------------------------------------

    count = Property(int, lambda self: len(self._playlists), notify=countChanged)
