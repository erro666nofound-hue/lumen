"""Qt list model over the songs inside the currently open playlist ("track").

Threading contract (CLAUDE.md muc 4): main thread only. removeTrack() and
removeSelected() only edit playlist membership -- LibraryBridge has a
same-named removeTrack that really deletes, see their docstrings.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, Property, Qt, QUrl, Signal, Slot

from lumen.core.formatting import format_duration, format_relative_date
from lumen.core import artwork, mp3_import, sorting
from lumen.core.errors import LumenError
from lumen.core.paths import covers_dir
from lumen.core.models import Track
from lumen.core.library_files import remove_files
from lumen.core.repository import PlaylistRepository, TrackRepository

log = logging.getLogger(__name__)


class TrackSongsBridge(QAbstractListModel):
    """Expose the open playlist's songs to QML, with in-track search and multi-select."""

    TrackIdRole, TitleRole = Qt.ItemDataRole.UserRole + 1, Qt.ItemDataRole.UserRole + 2
    ArtistRole, DurationTextRole = Qt.ItemDataRole.UserRole + 3, Qt.ItemDataRole.UserRole + 4
    DurationMsRole, CoverPathRole = Qt.ItemDataRole.UserRole + 5, Qt.ItemDataRole.UserRole + 6
    AddedTextRole, PlayCountRole = Qt.ItemDataRole.UserRole + 7, Qt.ItemDataRole.UserRole + 8
    IsPlayingRole, SelectedRole = Qt.ItemDataRole.UserRole + 9, Qt.ItemDataRole.UserRole + 10
    # Bài nhập từ mp3: KHÔNG có `source_id`, nên nó không bao giờ vào ảnh chụp
    # đồng bộ (F-5a′). Giao diện phải nói thật điều đó, nên sự thật ấy phải đi
    # ra tới hàng chứ không nằm im dưới database.
    LocalOnlyRole = Qt.ItemDataRole.UserRole + 11

    countChanged = Signal()
    searchChanged = Signal()
    sortChanged = Signal()
    editModeChanged = Signal()
    selectionChanged = Signal()
    playlistChanged = Signal()
    errorOccurred = Signal(str)
    trackRemoved = Signal(int)
    contentsChanged = Signal(int)
    # (id bài, tên mới) — cho mọi chỗ KHÁC đang hiện tên bài này.
    songRenamed = Signal(int, str)
    # Kéo xong thì hàng đợi đang phát phải đi theo thứ tự MỚI. Bắn ra ngoài
    # thay vì gọi thẳng PlayerBridge: model không được biết ai đang phát nhạc.
    songsReordered = Signal(int, "QVariantList")

    def __init__(
        self,
        repository: PlaylistRepository,
        tracks: TrackRepository,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._repository = repository
        # Đổi tên bài đụng vào bảng `tracks`, không phải bảng thành viên track.
        self._tracks_repository = tracks
        self._playlist_id = -1
        # Phạm vi phát PHẢI đi kèm id bài: cùng một bài có thể nằm trong nhiều
        # track, nên chỉ track thực sự đang phát (đúng _playing_scope_id) mới
        # được tô sáng -- nếu chỉ so track_id, mở track B chứa cùng bài đang
        # phát ở track A cũng sẽ sáng nhầm.
        self._playing_scope_id = self._playing_track_id = -1
        self._playlist_name = self._search = ""
        self._tracks: list[Track] = []
        # Toàn bộ bài của track, TRƯỚC khi lọc — lựa chọn và hộp xác nhận xoá
        # phải nói về cả những bài đang bị ô tìm kiếm giấu đi.
        self._all_tracks: list[Track] = []
        self._selection_mode = False
        self._selected_ids: set[int] = set()
        self._sort_key = sorting.SORT_CUSTOM
        self._sort_descending = False
        self._edit_mode = False
        self._editing_id = -1
        self.refresh()

    def roleNames(self) -> dict[int, QByteArray]:
        return {
            self.TrackIdRole: QByteArray(b"trackId"), self.TitleRole: QByteArray(b"title"),
            self.ArtistRole: QByteArray(b"artist"), self.DurationTextRole: QByteArray(b"durationText"),
            self.DurationMsRole: QByteArray(b"durationMs"), self.CoverPathRole: QByteArray(b"coverPath"),
            self.AddedTextRole: QByteArray(b"addedText"), self.PlayCountRole: QByteArray(b"playCount"),
            self.IsPlayingRole: QByteArray(b"isPlaying"), self.SelectedRole: QByteArray(b"selected"),
            self.LocalOnlyRole: QByteArray(b"localOnly"),
        }

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._tracks)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._tracks)):
            return None
        track = self._tracks[index.row()]
        match role:
            case self.TrackIdRole: return track.id or -1
            case self.TitleRole: return track.title
            case self.ArtistRole: return track.artist_label
            case self.DurationTextRole: return format_duration(track.duration_ms)
            case self.DurationMsRole: return track.duration_ms
            case self.CoverPathRole: return track.cover_path or ""
            case self.AddedTextRole: return format_relative_date(track.added_at)
            case self.PlayCountRole: return track.play_count
            case self.IsPlayingRole:
                return track.id == self._playing_track_id and self._playlist_id == self._playing_scope_id
            case self.SelectedRole: return track.id in self._selected_ids
            case self.LocalOnlyRole: return not track.source_id
        return None

    @Slot()
    def refresh(self) -> None:
        """Reload the songs of the currently open playlist, keeping selection where possible."""
        all_tracks: list[Track] = []
        if self._playlist_id >= 0:
            try:
                all_tracks = self._repository.tracks(self._playlist_id)
            except Exception as exc:
                log.exception("Cannot load songs for playlist %s", self._playlist_id)
                self.errorOccurred.emit(getattr(exc, "user_message", "Không đọc được các bài trong track."))
                return
        tracks = all_tracks
        if self._search:
            needle = self._search.lower()
            tracks = [t for t in all_tracks if needle in t.title.lower() or needle in t.artist_label.lower()]
        tracks = sorting.sort_tracks(tracks, self._sort_key, descending=self._sort_descending)
        self.beginResetModel()
        self._all_tracks = all_tracks
        self._tracks = tracks
        self.endResetModel()
        # Trên danh sách ĐẦY ĐỦ: tìm kiếm chỉ giấu bài, không được bỏ chọn nó.
        live_ids = {t.id for t in self._all_tracks if t.id is not None}
        before = len(self._selected_ids)
        self._selected_ids &= live_ids
        self.countChanged.emit()
        if len(self._selected_ids) != before:
            self.selectionChanged.emit()

    def _notify_selected_changed(self) -> None:
        if self._tracks:
            top, bottom = self.index(0, 0), self.index(len(self._tracks) - 1, 0)
            self.dataChanged.emit(top, bottom, [self.SelectedRole])

    def _remove_many(self, track_ids: list[int]) -> list[int]:
        """Xoá HẲN các bài khỏi track: dòng, thành viên, và file mp3 của track này.

        Mỗi track giữ bản sao riêng, nên gỡ khỏi danh sách mà để lại dòng và
        file là sai: tải lại đúng bài đó sẽ va vào bản cũ và báo "bài đã có".
        """
        if not track_ids:
            return []
        try:
            removed_ids, orphans = self._repository.remove_songs(self._playlist_id, track_ids)
        except Exception:
            log.exception("Cannot remove songs from playlist %s", self._playlist_id)
            self.errorOccurred.emit("Không xoá được bài khỏi track.")
            return []
        # Chỉ mp3, KHÔNG xoá ảnh bìa: bìa dùng chung giữa các bản sao (xem
        # DownloadBridge._copy_existing_into_playlist), xoá theo là mất bìa của
        # track khác.
        remove_files([Path(t.file_path) for t in orphans if t.file_path])
        return removed_ids

    def _finish_removal(self, track_ids: list[int]) -> None:
        for track_id in track_ids:
            self._selected_ids.discard(track_id)
            self.trackRemoved.emit(track_id)
        self.refresh()
        self.selectionChanged.emit()
        self.contentsChanged.emit(self._playlist_id)

    @Slot(int)
    def setPlaylist(self, playlist_id: int) -> None:
        """Open a different playlist, clearing any search filter, selection and selection mode."""
        self._playlist_id = playlist_id
        try:
            playlist = self._repository.get(playlist_id) if playlist_id >= 0 else None
        except Exception:
            log.exception("Cannot read playlist %s", playlist_id)
            playlist = None
        self._playlist_name = playlist.name if playlist else ""
        self._search = ""
        self._selected_ids.clear()
        self._selection_mode = False
        # Mở track khác thì thoát luôn chế độ sửa: để nó bật sang track mới là
        # người dùng không hề yêu cầu, mà ô nhập vẫn đang chờ phím.
        self._edit_mode = False
        self.playlistChanged.emit()
        self.editModeChanged.emit()
        self.searchChanged.emit()
        self.selectionChanged.emit()
        self.refresh()

    @Slot(str)
    def setSearch(self, text: str) -> None:
        """Filter the open playlist by a case-insensitive substring of title or artist."""
        text = (text or "").strip()
        if text == self._search:
            return
        self._search = text
        self.searchChanged.emit()
        # `canReorder` phụ thuộc cả ô tìm kiếm: đang lọc thì dòng thứ 3 trên màn
        # hình không phải bài thứ 3 của track, nên phải khoá kéo thả. Không báo
        # ở đây thì binding trong QML giữ giá trị cũ.
        self.sortChanged.emit()
        self.refresh()

    @Slot(bool)
    def setSelectionMode(self, on: bool) -> None:
        """Turn selection mode on/off; turning it off clears any selected songs."""
        if on == self._selection_mode:
            return
        self._selection_mode = on
        if not on:
            self.clearSelection()
        self.selectionChanged.emit()

    @Slot(int)
    def toggleSelected(self, track_id: int) -> None:
        """Flip whether one song is selected. Ignores ids not in the open track."""
        if track_id not in {t.id for t in self._all_tracks}:
            return
        if track_id in self._selected_ids:
            self._selected_ids.discard(track_id)
        else:
            self._selected_ids.add(track_id)
        self._notify_selected_changed()
        self.selectionChanged.emit()

    @Slot()
    def clearSelection(self) -> None:
        """Deselect every song without leaving selection mode."""
        if not self._selected_ids:
            return
        self._selected_ids.clear()
        self._notify_selected_changed()
        self.selectionChanged.emit()

    @Slot(result="QVariantMap")
    def summary(self) -> dict:
        """Return the header facts of this track: up to four covers and the total length."""
        covers = [t.cover_path for t in self._all_tracks if t.cover_path][:4]
        return {"covers": covers, "totalMs": sum(t.duration_ms for t in self._all_tracks),
                "count": len(self._all_tracks)}

    @Slot()
    def selectAll(self) -> None:
        """Select every song shown in the track (the floating bar's "Chọn hết")."""
        if not self._selection_mode:
            return
        self._selected_ids = {t.id for t in self._tracks if t.id is not None}
        self._notify_selected_changed()
        self.selectionChanged.emit()

    @Slot(result="QVariantList")
    def selectedTitles(self) -> list[str]:
        """Titles of every selected song, including ones the search is hiding.

        Reads the FULL list on purpose: removeSelected() works by id, so a
        dialog built from the filtered list would under-report what it deletes.
        """
        return [t.title for t in self._all_tracks if t.id in self._selected_ids]

    @Slot(result=int)
    def removeSelected(self) -> int:
        """Xoá hẳn các bài đã chọn khỏi track này; trả về số bài đã xoá.

        Xoá THẬT: dòng trong tracks, thành viên trong playlist_items, và file
        mp3 mà track này sở hữu. Bài còn nằm trong track khác thì giữ nguyên.
        """
        if self._playlist_id < 0 or not self._selected_ids:
            return 0
        removed_ids = self._remove_many(list(self._selected_ids))
        if not removed_ids:
            return 0
        self._selection_mode = False
        self._finish_removal(removed_ids)
        return len(removed_ids)

    @Slot(int, result=bool)
    def removeTrack(self, track_id: int) -> bool:
        """Unlist ONE song from the OPEN PLAYLIST only; returns False if it was not a member.

        Same slot name as LibraryBridge.removeTrack on purpose: the shared list
        component always calls `model.removeTrack(id)` meaning "drop this row
        from whatever list I'm showing." Here that means deleting the copy this
        track owns -- see _remove_many.
        """
        if self._playlist_id < 0:
            return False
        removed = bool(self._remove_many([track_id]))
        if removed:
            self._finish_removal([track_id])
        return removed

    @Slot(str)
    def setSort(self, key: str) -> None:
        """Sort by `key`; asking for the same key again flips the direction."""
        if not sorting.is_valid(key):
            return
        if key == self._sort_key:
            # Thứ tự tự tay xếp không có chiều ngược: đảo nó chẳng nói lên điều
            # gì, mà lại KHOÁ kéo-thả trong khi chip vẫn sáng như đang bật —
            # người dùng thấy nút nắm biến mất và không có lời giải thích nào.
            # CB-043.
            if key == sorting.SORT_CUSTOM:
                return
            self._sort_descending = not self._sort_descending
        else:
            self._sort_key = key
            self._sort_descending = False
        self.sortChanged.emit()
        self.refresh()

    @Slot(bool)
    def setEditMode(self, on: bool) -> None:
        """Turn the rename/reorder mode on or off."""
        if on == self._edit_mode and (on or self._editing_id < 0):
            return
        self._edit_mode = on
        if not on:
            self._editing_id = -1
        self.editModeChanged.emit()

    @Slot(int)
    def startRenaming(self, track_id: int) -> None:
        """Enter edit mode with the cursor already in this song's name."""
        self._edit_mode = True
        self._editing_id = track_id
        self.editModeChanged.emit()

    @Slot(int, str, result=bool)
    def renameSong(self, track_id: int, title: str) -> bool:
        """Change the displayed name of one song; the file itself is untouched."""
        # Cùng luật với TrackRepository.rename — xem lý do ở đó.
        cleaned = " ".join((title or "").split())
        if not cleaned:
            return False
        try:
            renamed = self._tracks_repository.rename(track_id, cleaned)
        except Exception as exc:
            log.exception("Cannot rename track %s", track_id)
            self.errorOccurred.emit(getattr(exc, "user_message", "Không đổi được tên bài."))
            return False
        if not renamed:
            return False
        self._apply_new_name(track_id, cleaned)
        # Ghi xuống database rồi im lặng là hỏng, kể cả khi ghi đúng (CB-029).
        # Danh sách này không phải chỗ duy nhất đang hiện tên bài đó: còn
        # Mini Lumen, và thanh phát + MPRIS khi đúng bài này đang chạy.
        self.songRenamed.emit(track_id, cleaned)
        return True

    @Slot(int, object, result=bool)
    def setCover(self, track_id: int, file_url: object) -> bool:
        """Đổi ảnh bìa của MỘT bài bằng ảnh chủ dự án vừa chọn trên đĩa.

        Ảnh được chép vào kho bìa trước khi ghi đường dẫn xuống database — xem
        `artwork.adopt`. Hỏng ở bất kỳ bước nào thì database không đổi và câu
        tiếng Việt đi ra `errorOccurred`.
        """
        # `FileDialog.selectedFile` là QUrl chứ không phải chuỗi, và `str()`
        # lên QUrl ra "PySide6.QtCore.QUrl(...)" — nuốt cả cái đó vào thì đường
        # dẫn sai mà không có lỗi nào nổ. Cùng cái bẫy đã chặn ở ImportBridge.
        raw = file_url.toLocalFile() if isinstance(file_url, QUrl) else str(file_url or "")
        text = raw.strip()
        if track_id < 0 or not text:
            return False
        try:
            stored = artwork.adopt(mp3_import.local_path(text), covers_dir())
        except LumenError as exc:
            self.errorOccurred.emit(exc.user_message)
            return False
        try:
            changed = self._tracks_repository.set_cover(track_id, str(stored))
        except LumenError as exc:
            self.errorOccurred.emit(exc.user_message)
            return False
        if not changed:
            return False
        self._apply_new_cover(track_id, str(stored))
        return True

    def _apply_new_cover(self, track_id: int, cover_path: str) -> None:
        """Vá đúng dòng vừa đổi bìa, KHÔNG nạp lại cả danh sách.

        Cùng lối với `_apply_new_name`, và cùng lý do: `refresh()` dựng lại
        model, mà dựng lại model trong lúc chế độ sửa đang mở là cướp con trỏ
        khỏi ô đang gõ.

        Sửa TẠI CHỖ trên `_all_tracks`: hai danh sách dùng chung đúng những đối
        tượng Track đó, nên gán một lần là cả hai thấy. Thay bằng bản sao mới là
        bẻ mất chỗ dùng chung ấy và bài đang bị ô tìm giấu sẽ giữ bìa cũ.
        """
        for track in self._all_tracks:
            if track.id == track_id:
                track.cover_path = cover_path
                break
        else:
            return
        for row, shown in enumerate(self._tracks):
            if shown.id == track_id:
                index = self.index(row, 0)
                self.dataChanged.emit(index, index, [self.CoverPathRole])
                break

    @Slot(int, str)
    def onSongRenamed(self, track_id: int, title: str) -> None:
        """Một danh sách KHÁC vừa đổi tên bài này; theo tên đó, đừng ghi lại database.

        Không bắn lại `songRenamed`: hai danh sách nối vào nhau cả hai chiều,
        bắn lại là chúng chuyền qua chuyền lại không dứt.
        """
        self._apply_new_name(track_id, title)

    def _apply_new_name(self, track_id: int, title: str) -> None:
        """Đổi tên trên bản sao trong bộ nhớ rồi báo đúng MỘT hàng.

        Sửa tại chỗ chứ không dựng lại cả model: dựng lại sẽ cướp con trỏ khỏi
        ô đang gõ và cuộn danh sách về đầu.

        Ghi vào `display_name`, KHÔNG vào `real_name` — giống hệt câu UPDATE
        chạy dưới database (QĐ-019). `Track.title` là thứ tính ra từ hai ô đó,
        không gán được.

        Duyệt `_all_tracks` chứ không phải `_tracks`: ô tìm kiếm chỉ GIẤU bài,
        bài bị giấu vẫn phải mang tên mới cho lần bỏ lọc sau. Hai danh sách
        dùng chung đúng những đối tượng Track đó, nên sửa một lần là đủ; chỉ
        có `dataChanged` mới cần số hàng, và chỉ khi hàng đang hiện.

        Không sắp xếp lại: đang sắp theo tên thì bài vừa đổi tên sẽ nhảy chỗ
        ngay dưới ngón tay người dùng.
        """
        for track in self._all_tracks:
            if track.id == track_id:
                track.display_name = title
                break
        else:
            return
        for row, shown in enumerate(self._tracks):
            if shown.id == track_id:
                index = self.index(row, 0)
                self.dataChanged.emit(index, index, [self.TitleRole])
                break

    @Slot(int, int, result=bool)
    def moveSong(self, from_index: int, to_index: int) -> bool:
        """Move a song to another slot and remember it; only in the user's own order.

        Kéo thả chỉ có nghĩa khi danh sách đang ở ĐÚNG thứ tự người dùng tự đặt
        và không bị ô tìm kiếm giấu bớt: sắp theo tên rồi kéo thì "chỗ mới" là
        chỗ nào trong thứ tự thật? Còn khi đang lọc, dòng thứ 3 trên màn hình
        không phải bài thứ 3 của track.
        """
        if not self.canReorder:
            return False
        last = len(self._all_tracks) - 1
        if not (0 <= from_index <= last and 0 <= to_index <= last) or from_index == to_index:
            return False

        order = list(self._all_tracks)
        order.insert(to_index, order.pop(from_index))
        ids = [t.id for t in order if t.id is not None]
        try:
            self._repository.reorder_tracks(self._playlist_id, ids)
        except Exception as exc:
            log.exception("Cannot reorder playlist %s", self._playlist_id)
            self.errorOccurred.emit(
                getattr(exc, "user_message", "Không đổi được thứ tự các bài.")
            )
            return False

        # beginMoveRows chứ KHÔNG dựng lại cả model: dựng lại thì ListView coi
        # như một danh sách hoàn toàn mới và bỏ qua hoạt ảnh `displaced` — các
        # hàng cụp sang chỗ mới thay vì trượt.
        #
        # Qt tính đích theo chỗ TRƯỚC khi bỏ hàng ra, nên dời xuống phải +1.
        destination = to_index + 1 if to_index > from_index else to_index
        self.beginMoveRows(QModelIndex(), from_index, from_index, QModelIndex(), destination)
        self._all_tracks = order
        self._tracks = list(order)
        self.endMoveRows()
        # Database đã đổi, lưới đã đổi — còn hàng đợi đang phát thì vẫn là bản
        # chép lúc bấm play. Không báo ra thì người dùng kéo xong, nhìn màn hình
        # thấy đúng, mà hết bài này nhạc vẫn nhảy theo thứ tự cũ.
        self.songsReordered.emit(self._playlist_id, ids)
        return True

    @Slot(result="QVariantList")
    def orderedIds(self) -> list[int]:
        """Track ids in exactly the order currently shown, for Player.playPlaylist."""
        return [t.id for t in self._tracks if t.id is not None]

    @Slot(int)
    def onPlaylistContentsChanged(self, playlist_id: int) -> None:
        """Refresh when PlaylistsBridge reports a membership change to the currently open playlist."""
        if playlist_id == self._playlist_id:
            self.refresh()

    def set_playing(self, playlist_id: int, track_id: int) -> None:
        """Mark which row is currently playing so the table can highlight it.

        Takes the SCOPE (which track/playlist is playing) as well as the song
        id -- a song can sit in more than one track, so track_id alone cannot
        tell this track apart from another one showing the same song.
        """
        if playlist_id == self._playing_scope_id and track_id == self._playing_track_id:
            return
        self._playing_scope_id = playlist_id
        self._playing_track_id = track_id
        if self._tracks:
            top = self.index(0, 0)
            bottom = self.index(len(self._tracks) - 1, 0)
            self.dataChanged.emit(top, bottom, [self.IsPlayingRole])

    playlistId = Property(int, lambda self: self._playlist_id, notify=playlistChanged)
    playlistName = Property(str, lambda self: self._playlist_name, notify=playlistChanged)
    count = Property(int, lambda self: len(self._tracks), notify=countChanged)
    searchText = Property(str, lambda self: self._search, notify=searchChanged)
    selectionMode = Property(bool, lambda self: self._selection_mode, notify=selectionChanged)
    selectedCount = Property(int, lambda self: len(self._selected_ids), notify=selectionChanged)
    editMode = Property(bool, lambda self: self._edit_mode, notify=editModeChanged)
    #: Bài nào đang được nhắm để đổi tên; -1 = không nhắm ai (chỉ bật chế độ sửa).
    editingTrackId = Property(int, lambda self: self._editing_id, notify=editModeChanged)
    sortKey = Property(str, lambda self: self._sort_key, notify=sortChanged)
    sortDescending = Property(bool, lambda self: self._sort_descending, notify=sortChanged)
    def _reorder_blocked_reason(self) -> str:
        """Why drag-reorder is off right now; empty string when it is on.

        Ẩn nút nắm mà không nói gì là lỗi đã gặp thật (CB-043): người dùng chỉ
        thấy tính năng biến mất. Mỗi lý do đi kèm ĐÚNG cách bật lại.
        """
        if self._search:
            return "Đang lọc theo ô tìm — xoá ô tìm để kéo đổi thứ tự."
        if self._sort_key != sorting.SORT_CUSTOM:
            label = sorting.SORT_LABELS.get(self._sort_key, self._sort_key)
            return f'Đang sắp theo "{label}" — bấm "Thứ tự của bạn" để kéo đổi thứ tự.'
        if self._sort_descending:
            return 'Đang sắp ngược — bấm "Thứ tự của bạn" để kéo đổi thứ tự.'
        return ""

    #: Câu giải thích cho lúc nút nắm vắng mặt. Rỗng = kéo thả đang mở.
    reorderBlockedReason = Property(str, _reorder_blocked_reason, notify=sortChanged)

    # Kéo thả chỉ mở khi thứ tự trên màn hình ĐÚNG là thứ tự thật của track.
    canReorder = Property(
        bool,
        lambda self: self._sort_key == sorting.SORT_CUSTOM
        and not self._sort_descending
        and not self._search,
        notify=sortChanged,
    )
