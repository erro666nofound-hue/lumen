from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Iterator, Sequence

from . import sync_clock, sync_songs
from .errors import DatabaseError, DuplicatePlaylistNameError, DuplicateTrackError
from .models import Playlist, Track, playlist_from_row, track_from_row

# Tên hiện ra = tên chủ dự án đặt, không đặt thì tên thật (QĐ-019). Cùng một
# phép này ở SQL và ở `Track.title` bên models — hai chỗ phải nói một câu.
_SHOWN_NAME_SQL = "COALESCE(NULLIF(display_name, ''), real_name)"

_TRACK_ORDER_SQL = {
    "added_desc": "added_at DESC, id DESC",
    "added_asc": "added_at ASC, id ASC",
    # Sắp theo tên là sắp theo tên NHÌN THẤY, không phải tên YouTube.
    "title": f"{_SHOWN_NAME_SQL} COLLATE NOCASE ASC",
    "artist": "artist COLLATE NOCASE ASC",
    "most_played": "play_count DESC, id DESC",
}

_PLAYLIST_WITH_COUNT_SQL = (
    "SELECT p.*, COUNT(pi.track_id) AS track_count FROM playlists p "
    "LEFT JOIN playlist_items pi ON pi.playlist_id = p.id "
)


@contextmanager
def _wrap_errors(conn: sqlite3.Connection, message: str, *, write: bool = False) -> Iterator[None]:
    """Translate sqlite3 errors into DatabaseError, committing/rolling back write operations."""
    try:
        yield
        if write:
            conn.commit()
    except sqlite3.Error as exc:
        if write:
            conn.rollback()
        raise DatabaseError(message, user_message="Could not access the music library") from exc


class TrackRepository:
    """All SQL access for the tracks table."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(self, track: Track) -> Track:
        """Insert a new track (filling added_at when unset) and return it with its id."""
        added_at = track.added_at if track.added_at else int(time.time())
        try:
            cursor = self._conn.execute(
                "INSERT INTO tracks (source_id, content_hash, source_url, real_name, "
                "display_name, display_name_updated_at, artist, duration_ms, "
                "file_path, cover_path, added_at, play_count, last_played_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    track.source_id,
                    # Rỗng xuống NULL, cùng lối với `file_path` ngay dưới: chuỗi
                    # rỗng và NULL là HAI cách nói "chưa băm", và `HAS_IDENTITY`
                    # phải trả lời như nhau cho cả hai (QĐ-027).
                    track.content_hash or None,
                    track.source_url,
                    track.real_name,
                    track.display_name,
                    track.display_name_updated_at,
                    track.artist,
                    track.duration_ms,
                    # Rỗng phải xuống database thành NULL, không phải `''`:
                    # UNIQUE cho nhiều NULL cùng tồn tại, nhưng chỉ cho MỘT
                    # chuỗi rỗng. Xem migration v9.
                    track.file_path or None,
                    track.cover_path,
                    added_at,
                    track.play_count,
                    track.last_played_at,
                ),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            self._conn.rollback()
            raise DuplicateTrackError(
                f"Track already exists: {exc}",
                user_message="This track is already in your library",
            ) from exc
        except sqlite3.Error as exc:
            self._conn.rollback()
            raise DatabaseError(
                "Failed to add track", user_message="Could not access the music library"
            ) from exc
        added = self.get(cursor.lastrowid)
        assert added is not None
        return added

    def get(self, track_id: int) -> Track | None:
        """Return the track with the given id, or None if not found."""
        with _wrap_errors(self._conn, f"Failed to get track {track_id}"):
            row = self._conn.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
        return track_from_row(row) if row is not None else None

    def get_by_file_path(self, file_path: str) -> Track | None:
        """Dòng đang giữ đúng file này, nếu có.

        Cần vì `file_path` là UNIQUE: chép một bài vào thư mục track mà ở đó đã
        có sẵn đúng file đó (bản sót từ lần xoá cũ, hoặc người dùng tự chép vào)
        sẽ đụng ràng buộc và báo "bài đã có" — trong khi việc đúng phải làm là
        dùng lại chính dòng đó.
        """
        with _wrap_errors(self._conn, f"Failed to look up track by path {file_path}"):
            row = self._conn.execute(
                "SELECT * FROM tracks WHERE file_path = ?", (file_path,)
            ).fetchone()
        return track_from_row(row) if row else None

    def get_by_source_id(self, source_id: str) -> Track | None:
        """Return a track downloaded from this YouTube video, preferring one that has a file."""
        # Bản CÓ FILE đứng trước. Từ v9 cùng một `source_id` có thể có cả dòng
        # chỗ trống do đồng bộ dựng lên (chưa tải) lẫn bản đã tải thật. Người
        # gọi hỏi câu này để CHÉP file đã có sang track khác — vớ phải dòng chỗ
        # trống là chép một đường dẫn rỗng.
        with _wrap_errors(self._conn, f"Failed to get track by source_id {source_id!r}"):
            row = self._conn.execute(
                "SELECT * FROM tracks WHERE source_id = ? "
                "ORDER BY (file_path IS NULL OR file_path = ''), id LIMIT 1",
                (source_id,),
            ).fetchone()
        return track_from_row(row) if row is not None else None

    def get_by_file_path(self, file_path: str) -> Track | None:
        """Return the track with the given absolute file path, or None if not found."""
        with _wrap_errors(self._conn, f"Failed to get track by file_path {file_path!r}"):
            row = self._conn.execute(
                "SELECT * FROM tracks WHERE file_path = ?", (file_path,)
            ).fetchone()
        return track_from_row(row) if row is not None else None

    def list_all(self, search: str | None = None, order: str = "added_desc") -> list[Track]:
        """Return tracks ordered by `order`, optionally filtered by a case-insensitive substring search."""
        if order not in _TRACK_ORDER_SQL:
            raise ValueError(f"Invalid order: {order!r}")
        with _wrap_errors(self._conn, "Failed to list tracks"):
            rows = self._conn.execute(
                f"SELECT * FROM tracks ORDER BY {_TRACK_ORDER_SQL[order]}"
            ).fetchall()
        tracks = [track_from_row(row) for row in rows]
        needle = search.strip().lower() if search else ""
        if needle:
            tracks = [t for t in tracks if needle in t.title.lower() or needle in t.artist.lower()]
        return tracks

    def delete(self, track_id: int) -> bool:
        """Delete a track by id; return True if a row was removed."""
        with _wrap_errors(self._conn, f"Failed to delete track {track_id}", write=True):
            # Phải hỏi TRƯỚC khi xoá: CASCADE dọn sạch playlist_items rồi thì
            # không còn cách nào biết bài này từng nằm ở những track nào.
            keys = sync_clock.item_keys_of_track(self._conn, track_id)
            cursor = self._conn.execute("DELETE FROM tracks WHERE id = ?", (track_id,))
            if cursor.rowcount > 0:
                sync_clock.bury_many(self._conn, sync_clock.KIND_PLAYLIST_ITEM, keys)
        return cursor.rowcount > 0

    def rename(self, track_id: int, title: str, when: int | None = None) -> bool:
        """Change only the owner's displayed name; return True if a row was updated.

        CHỈ đụng vào `display_name` (+ mốc của nó). `real_name` là tên YouTube
        nói và KHÔNG ai được đè từ đây (QĐ-019): lần tải lại sau sẽ làm mới
        `real_name`, và tên chủ dự án đặt phải sống sót qua đúng lúc đó.

        File mp3, thẻ tag bên trong nó và ảnh bìa đều không bị chạm tới — đổi
        tên hiển thị không được có cơ hội làm hỏng file nhạc.

        Gom mọi cụm khoảng trắng thành MỘT dấu cách. Cắt hai đầu thôi thì chưa
        đủ: gõ dấu cách vào GIỮA tên vẫn lọt xuống database và nằm đó vĩnh viễn.

        Đóng dấu `now()` ở đây là ĐÚNG — đây là người dùng vừa gõ trên máy này,
        không phải dữ liệu khôi phục từ ảnh chụp (CB-024 nói về chỗ ngược lại).
        """
        cleaned = " ".join((title or "").split())
        if not cleaned:
            return False
        stamped = sync_clock.now() if when is None else when
        with _wrap_errors(self._conn, f"Failed to rename track {track_id}", write=True):
            cursor = self._conn.execute(
                "UPDATE tracks SET display_name = ?, display_name_updated_at = ? "
                "WHERE id = ?",
                (cleaned, stamped, track_id),
            )
        return cursor.rowcount > 0

    def set_cover(self, track_id: int, cover_path: str) -> bool:
        """Point a track at a new cover image; return True if a row was updated.

        Chỉ đổi ĐƯỜNG DẪN. File mp3 và thẻ tag bên trong nó không bị chạm — đổi
        bìa không được có cơ hội làm hỏng file nhạc (cùng luật với `rename`).

        Bìa CŨ cố ý không bị xoá: hai bài có thể đang trỏ vào cùng một file bìa
        (tên file trong kho lấy theo vân tay nội dung), nên xoá ở đây là bài kia
        mất ảnh mà không ai hiểu vì sao.
        """
        if not cover_path:
            return False
        with _wrap_errors(self._conn, f"Failed to set cover for track {track_id}", write=True):
            cursor = self._conn.execute(
                "UPDATE tracks SET cover_path = ? WHERE id = ?",
                (cover_path, track_id),
            )
        return cursor.rowcount > 0

    def record_play(self, track_id: int, when: int | None = None) -> None:
        """Increment play_count and set last_played_at for a track."""
        played_at = when if when is not None else int(time.time())
        with _wrap_errors(self._conn, f"Failed to record play for track {track_id}", write=True):
            self._conn.execute(
                "UPDATE tracks SET play_count = play_count + 1, last_played_at = ? WHERE id = ?",
                (played_at, track_id),
            )

    def list_needing_file(self) -> list[Track]:
        """Return the file-less rows: songs synced from another machine, not downloaded here."""
        with _wrap_errors(self._conn, "Failed to list songs needing a file"):
            rows = sync_songs.songs_needing_file(self._conn)
        return [track_from_row(row) for row in rows]

    def attach_file(self, track_id: int, downloaded: Track) -> Track | None:
        """Fill a file-less row with a finished download, in place; None when it could not.

        Luật ở `core/sync_songs.fill_song` — UPDATE chứ không INSERT, và
        `added_at` giữ nguyên mốc của ảnh chụp. Chỉ `real_name` được làm mới:
        tên chủ dự án đặt cho dòng này sống sót qua lần tải (QĐ-019).
        """
        with _wrap_errors(self._conn, f"Failed to attach file to track {track_id}", write=True):
            filled = sync_songs.fill_song(
                self._conn,
                track_id,
                file_path=downloaded.file_path,
                real_name=downloaded.real_name,
                artist=downloaded.artist,
                duration_ms=downloaded.duration_ms,
                cover_path=downloaded.cover_path,
                source_url=downloaded.source_url or "",
            )
        return self.get(track_id) if filled else None

    def count(self) -> int:
        """Return the total number of tracks in the library."""
        with _wrap_errors(self._conn, "Failed to count tracks"):
            row = self._conn.execute("SELECT COUNT(*) AS n FROM tracks").fetchone()
        return int(row["n"])


class PlaylistRepository:
    """All SQL access for playlists and their track membership."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # F-5 §1 — hai track KHÔNG được trùng tên
    #
    # Luật hoà theo tên (QĐ-017) cố ý đứng im khi một bên có từ hai track cùng
    # tên trở lên: nó không có cách nào biết cái nào ghép cái nào, nên để
    # nguyên cả hai và người dùng nhìn thấy track thừa. Chặn ở cửa TẠO là thứ
    # giữ cho ca đó không sinh ra.
    #
    # Chặn ở ĐÂY chứ không phải bằng `UNIQUE` dưới SQL, vì phép áp bản kê
    # (sync_restore) đi bằng SQL thô và PHẢI đặt xuống được đúng thứ đã hoà —
    # kể cả ca hai track cùng tên mà QĐ-017 chừa lại. Một `UNIQUE` ở lược đồ
    # sẽ làm phép áp nổ giữa chừng, đúng vào ca nó cần chạy nhất.
    def _refuse_taken_name(self, name: str, *, except_id: int | None = None) -> None:
        """Raise DuplicatePlaylistNameError when another playlist carries this exact name."""
        # `=` trên cột TEXT không khai COLLATE là so từng byte, nên "Test" và
        # "test" vẫn là hai track — đúng như QĐ-017 đọc tên.
        sql = "SELECT 1 FROM playlists WHERE name = ?"
        params: list[Any] = [name]
        if except_id is not None:
            sql += " AND id != ?"
            params.append(except_id)
        with _wrap_errors(self._conn, "Failed to check playlist name"):
            taken = self._conn.execute(sql, params).fetchone() is not None
        if taken:
            raise DuplicatePlaylistNameError(
                f"Playlist named {name!r} already exists",
                user_message=f"Đã có track tên “{name}”.",
            )

    def create(self, name: str, icon: str = "") -> Playlist:
        """Create a new playlist appended after the current highest position."""
        self._refuse_taken_name(name)
        with _wrap_errors(self._conn, "Failed to create playlist", write=True):
            row = self._conn.execute(
                "SELECT COALESCE(MAX(position) + 1, 0) AS next FROM playlists"
            ).fetchone()
            # `uuid` do DEFAULT của v8 sinh. Hai đồng hồ khởi bằng created_at
            # chứ không phải 0, nếu không track mới thua ngay lần hoà đầu.
            born = sync_clock.now()
            cursor = self._conn.execute(
                "INSERT INTO playlists (name, icon, position, created_at, updated_at, "
                "order_updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (name, icon, int(row["next"]), born, born, born),
            )
        created = self.get(cursor.lastrowid)
        assert created is not None
        return created

    def get(self, playlist_id: int) -> Playlist | None:
        """Return the playlist with the given id (with track_count filled in), or None."""
        with _wrap_errors(self._conn, f"Failed to get playlist {playlist_id}"):
            row = self._conn.execute(
                f"{_PLAYLIST_WITH_COUNT_SQL}WHERE p.id = ? GROUP BY p.id", (playlist_id,)
            ).fetchone()
        return playlist_from_row(row) if row is not None else None

    def list_all(self) -> list[Playlist]:
        """Return all playlists ordered by position, with track_count filled in."""
        with _wrap_errors(self._conn, "Failed to list playlists"):
            rows = self._conn.execute(
                f"{_PLAYLIST_WITH_COUNT_SQL}GROUP BY p.id ORDER BY p.position ASC"
            ).fetchall()
        return [playlist_from_row(row) for row in rows]

    def rename(self, playlist_id: int, name: str) -> None:
        """Rename a playlist; refuses a name another playlist already carries."""
        self._refuse_taken_name(name, except_id=playlist_id)
        with _wrap_errors(self._conn, f"Failed to rename playlist {playlist_id}", write=True):
            self._conn.execute(
                "UPDATE playlists SET name = ?, updated_at = ? WHERE id = ?",
                (name, sync_clock.now(), playlist_id),
            )

    def set_icon(self, playlist_id: int, icon: str) -> None:
        """Set the icon glyph for a playlist."""
        with _wrap_errors(self._conn, f"Failed to set icon for playlist {playlist_id}", write=True):
            self._conn.execute(
                "UPDATE playlists SET icon = ?, updated_at = ? WHERE id = ?",
                (icon, sync_clock.now(), playlist_id),
            )

    def delete(self, playlist_id: int) -> bool:
        """Delete a playlist (cascading to its items); return True if a row was removed.

        Leaves the songs themselves alone. Callers that want the music gone too
        want delete_with_songs().
        """
        with _wrap_errors(self._conn, f"Failed to delete playlist {playlist_id}", write=True):
            uuid_value = sync_clock.playlist_uuid(self._conn, playlist_id)
            cursor = self._conn.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
            if cursor.rowcount > 0 and uuid_value is not None:
                sync_clock.bury(self._conn, sync_clock.KIND_PLAYLIST, uuid_value)
        return cursor.rowcount > 0

    def delete_with_songs(self, playlist_id: int) -> list[Track]:
        """Delete a playlist AND the songs that lived only inside it.

        Returns the deleted songs so the caller can remove their files: this
        layer owns SQL, not the disk. A song that is also a member of another
        track is left alone -- each track owns its own copy, but a row CAN be
        shared (see add_track), and deleting it would gut the other track.
        """
        with _wrap_errors(self._conn, f"Failed to delete playlist {playlist_id}", write=True):
            rows = self._conn.execute(
                "SELECT t.* FROM tracks t "
                "JOIN playlist_items pi ON pi.track_id = t.id "
                "WHERE pi.playlist_id = ? AND ("
                "  SELECT COUNT(*) FROM playlist_items o WHERE o.track_id = t.id"
                ") = 1",
                (playlist_id,),
            ).fetchall()
            orphans = [track_from_row(row) for row in rows]
            if orphans:
                self._conn.executemany(
                    "DELETE FROM tracks WHERE id = ?",
                    [(track.id,) for track in orphans],
                )
            uuid_value = sync_clock.playlist_uuid(self._conn, playlist_id)
            self._conn.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
            if uuid_value is not None:
                sync_clock.bury(self._conn, sync_clock.KIND_PLAYLIST, uuid_value)
        return orphans

    def remove_songs(
        self, playlist_id: int, track_ids: Sequence[int]
    ) -> tuple[list[int], list[Track]]:
        """Gỡ vài bài khỏi một track VÀ xoá hẳn bản sao mà track này sở hữu.

        Trả về (id các bài THẬT SỰ là thành viên và đã gỡ, các Track đã xoá hẳn).
        Hai danh sách khác nhau: bài còn nằm trong track khác thì được gỡ khỏi
        track này nhưng KHÔNG bị xoá. Tầng trên dùng danh sách sau để xoá file —
        tầng này chỉ biết SQL.

        Mỗi track giữ bản sao riêng trong thư mục riêng của nó, nên "xoá bài
        khỏi track" phải là xoá thật. Trước đây chỉ gỡ khỏi playlist_items —
        dòng và file mp3 ở lại, nên tải lại đúng bài đó là va vào file cũ và
        báo "bài đã có". Cùng một luật với delete_with_songs: CHỈ xoá dòng mà
        track này là thành viên duy nhất, vì một bài có thể nằm trong hai track.
        """
        ids = [int(t) for t in track_ids]
        if not ids:
            return [], []
        placeholders = ",".join("?" for _ in ids)
        with _wrap_errors(
            self._conn, f"Failed to remove songs from playlist {playlist_id}", write=True
        ):
            rows = self._conn.execute(
                f"SELECT t.* FROM tracks t "
                f"JOIN playlist_items pi ON pi.track_id = t.id "
                f"WHERE pi.playlist_id = ? AND t.id IN ({placeholders}) AND ("
                f"  SELECT COUNT(*) FROM playlist_items o WHERE o.track_id = t.id"
                f") = 1",
                (playlist_id, *ids),
            ).fetchall()
            orphans = [track_from_row(row) for row in rows]
            member_rows = self._conn.execute(
                f"SELECT track_id FROM playlist_items "
                f"WHERE playlist_id = ? AND track_id IN ({placeholders})",
                (playlist_id, *ids),
            ).fetchall()
            removed_ids = [int(row["track_id"]) for row in member_rows]
            keys = sync_clock.item_keys_of_playlist(self._conn, playlist_id, removed_ids)
            self._conn.execute(
                f"DELETE FROM playlist_items WHERE playlist_id = ? AND track_id IN ({placeholders})",
                (playlist_id, *ids),
            )
            if orphans:
                self._conn.executemany(
                    "DELETE FROM tracks WHERE id = ?", [(t.id,) for t in orphans]
                )
            sync_clock.bury_many(self._conn, sync_clock.KIND_PLAYLIST_ITEM, keys)
        return removed_ids, orphans

    def add_track(self, playlist_id: int, track_id: int) -> bool:
        """Append a track to the end of a playlist; return False if it is already present."""
        if self.contains(playlist_id, track_id):
            return False
        with _wrap_errors(self._conn, f"Failed to add track {track_id} to playlist {playlist_id}", write=True):
            row = self._conn.execute(
                "SELECT COALESCE(MAX(position) + 1, 0) AS next FROM playlist_items WHERE playlist_id = ?",
                (playlist_id,),
            ).fetchone()
            self._conn.execute(
                "INSERT INTO playlist_items (playlist_id, track_id, position, added_at) "
                "VALUES (?, ?, ?, ?)",
                (playlist_id, track_id, int(row["next"]), sync_clock.now()),
            )
            # Bài quay lại thì bia mộ cũ phải đi (xem sync_clock.unbury_many).
            sync_clock.unbury_many(
                self._conn,
                sync_clock.KIND_PLAYLIST_ITEM,
                sync_clock.item_keys_of_playlist(self._conn, playlist_id, [track_id]),
            )
        return True

    def remove_track(self, playlist_id: int, track_id: int) -> bool:
        """Remove a track from a playlist; return True if a row was removed."""
        with _wrap_errors(
            self._conn, f"Failed to remove track {track_id} from playlist {playlist_id}", write=True
        ):
            keys = sync_clock.item_keys_of_playlist(self._conn, playlist_id, [track_id])
            cursor = self._conn.execute(
                "DELETE FROM playlist_items WHERE playlist_id = ? AND track_id = ?",
                (playlist_id, track_id),
            )
            if cursor.rowcount > 0:
                sync_clock.bury_many(self._conn, sync_clock.KIND_PLAYLIST_ITEM, keys)
        return cursor.rowcount > 0

    def tracks(self, playlist_id: int) -> list[Track]:
        """Return the tracks in a playlist, ordered by position."""
        with _wrap_errors(self._conn, f"Failed to list tracks for playlist {playlist_id}"):
            rows = self._conn.execute(
                "SELECT t.* FROM tracks t JOIN playlist_items pi ON pi.track_id = t.id "
                "WHERE pi.playlist_id = ? ORDER BY pi.position ASC",
                (playlist_id,),
            ).fetchall()
        return [track_from_row(row) for row in rows]

    def reorder_tracks(self, playlist_id: int, track_ids: list[int]) -> None:
        """Reassign playlist_items positions to 0..n-1 following the given track order."""
        with _wrap_errors(self._conn, f"Failed to reorder tracks for playlist {playlist_id}", write=True):
            self._conn.executemany(
                "UPDATE playlist_items SET position = ? WHERE playlist_id = ? AND track_id = ?",
                [(index, playlist_id, track_id) for index, track_id in enumerate(track_ids)],
            )
            sync_clock.touch_playlist(self._conn, playlist_id, order=True)

    def reorder_playlists(self, playlist_ids: list[int]) -> None:
        """Reassign playlist positions to 0..n-1 following the given order."""
        with _wrap_errors(self._conn, "Failed to reorder playlists", write=True):
            self._conn.executemany(
                "UPDATE playlists SET position = ? WHERE id = ?",
                [(index, playlist_id) for index, playlist_id in enumerate(playlist_ids)],
            )
            sync_clock.touch_playlist_order(self._conn)

    def playlists_of(self, track_id: int) -> list[int]:
        """Return the ids of every playlist this track sits in.

        Cần khi một dòng đổi tại chỗ (bài đồng bộ về vừa được tải lại): lưới
        đang mở phải vẽ lại, mà nó chỉ nghe tên track của CHÍNH nó.
        """
        with _wrap_errors(self._conn, f"Failed to list playlists of track {track_id}"):
            rows = self._conn.execute(
                "SELECT playlist_id FROM playlist_items WHERE track_id = ?", (track_id,)
            ).fetchall()
        return [int(row["playlist_id"]) for row in rows]

    def contains(self, playlist_id: int, track_id: int) -> bool:
        """Return True if the track is already in the playlist."""
        with _wrap_errors(
            self._conn, f"Failed to check membership of track {track_id} in playlist {playlist_id}"
        ):
            row = self._conn.execute(
                "SELECT 1 FROM playlist_items WHERE playlist_id = ? AND track_id = ? LIMIT 1",
                (playlist_id, track_id),
            ).fetchone()
        return row is not None
