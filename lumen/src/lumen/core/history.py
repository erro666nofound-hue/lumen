"""The append-only ledger of everything the user has ever downloaded.

Separate from `tracks` on purpose: `tracks` describes what is on disk RIGHT
NOW, so deleting a song erases every trace of it. "Nhạc của tôi" has to keep
showing songs the user already threw away, identified by their YouTube URL
rather than by a local file that may be gone. No Qt, no UI.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass

from lumen.core.tiers import normalise_artist

log = logging.getLogger(__name__)


def _primary_of(raw: str) -> str:
    """Tên nghệ sĩ chính, cùng phép chuẩn hoá mà mọi nơi khác dùng."""
    return normalise_artist(raw or "")


@dataclass(frozen=True, slots=True)
class DownloadRecord:
    """One line of the ledger: a video the user downloaded at least once."""

    url: str
    source_id: str
    title: str
    artist: str
    uploader: str
    downloaded_at: int
    # True when a row in `tracks` still points at this video -- the file is
    # still on the machine, so the UI can offer to put it back into a track.
    still_owned: bool

    @property
    def best_artist(self) -> str:
        """Uploader first: `artist` comes from guessing at "A - B" video titles.

        That guess flips whenever a channel writes "Song - Artist", which is
        common enough that the owner's own library already contains examples.
        """
        return self.uploader or self.artist


class DownloadHistoryRepository:
    """Read and append the download ledger. Main thread only, like every repo here."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def record(
        self,
        *,
        url: str,
        source_id: str = "",
        title: str = "",
        artist: str = "",
        uploader: str = "",
        when: int | None = None,
    ) -> None:
        """Note a completed download. Downloading the same video again refreshes
        the names but KEEPS the original timestamp -- the ledger answers "when
        did this first enter my life", not "when did I last re-fetch it"."""
        if not url:
            return
        stamp = int(time.time()) if when is None else int(when)
        try:
            self._conn.execute(
                "INSERT INTO download_history "
                "(source_id, url, title, artist, uploader, downloaded_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(url) DO UPDATE SET "
                "  source_id = excluded.source_id, title = excluded.title, "
                "  artist = excluded.artist, uploader = excluded.uploader",
                (source_id, url, title, artist, uploader, stamp),
            )
            self._conn.commit()
        except sqlite3.Error:
            # A missing ledger line must never break an otherwise good download.
            log.warning("Could not record download of %s", url, exc_info=True)

    def all(self) -> list[DownloadRecord]:
        """Every download ever, newest first, flagged with whether we still have it."""
        try:
            rows = self._conn.execute(
                "SELECT h.url, h.source_id, h.title, h.artist, h.uploader, h.downloaded_at, "
                "  EXISTS(SELECT 1 FROM tracks t WHERE t.source_id = h.source_id) AS owned "
                "FROM download_history h ORDER BY h.downloaded_at DESC"
            ).fetchall()
        except sqlite3.Error:
            log.exception("Could not read download history")
            return []
        return [
            DownloadRecord(
                url=row["url"],
                source_id=row["source_id"] or "",
                title=row["title"] or "",
                artist=row["artist"] or "",
                uploader=row["uploader"] or "",
                downloaded_at=int(row["downloaded_at"]),
                still_owned=bool(row["owned"]),
            )
            for row in rows
        ]

    def artists(self) -> list[str]:
        """Nghệ sĩ của các bài ĐANG NẰM TRONG TRACK, một dòng cho mỗi bài.

        Đọc từ bảng `tracks` chứ KHÔNG phải từ sổ lịch sử: sổ chỉ ghi thêm, nên
        xoá một bài đi rồi mà app vẫn đề xuất nghệ sĩ đó mãi — chủ dự án gọi
        đúng đây là "cay thí". Đề xuất phải phản ánh thứ người dùng ĐANG GIỮ.

        Cố ý KHÔNG khử trùng lặp: nơi gọi đếm số lần lặp để suy ra mức yêu thích.
        """
        try:
            rows = self._conn.execute(
                "SELECT t.artist FROM tracks t "
                "JOIN playlist_items pi ON pi.track_id = t.id "
                "WHERE t.artist IS NOT NULL AND t.artist <> ''"
            ).fetchall()
        except sqlite3.Error:
            log.exception("Could not read artists from tracks")
            return []
        return [row["artist"] for row in rows]

    def missing_uploaders(self) -> list[str]:
        """Video ids whose channel name we never stored.

        Music downloaded before the ledger existed has no uploader, and that is
        exactly the data the discovery page needs -- see DownloadRecord.best_artist.
        """
        try:
            rows = self._conn.execute(
                "SELECT source_id FROM download_history "
                "WHERE uploader = '' AND source_id IS NOT NULL AND source_id <> ''"
            ).fetchall()
        except sqlite3.Error:
            log.exception("Could not list rows missing an uploader")
            return []
        return [row["source_id"] for row in rows]

    def set_uploaders(self, names: dict[str, str]) -> int:
        """Fill in channel names found later; returns how many rows changed."""
        pairs = [(name, source_id) for source_id, name in names.items() if name]
        if not pairs:
            return 0
        try:
            cursor = self._conn.executemany(
                "UPDATE download_history SET uploader = ? WHERE source_id = ?", pairs
            )
            self._conn.commit()
        except sqlite3.Error:
            log.warning("Could not store channel names", exc_info=True)
            return 0
        return cursor.rowcount

    def songs_of_artist(self, artist: str) -> list[dict]:
        """Các bài ĐANG GIỮ của một nghệ sĩ, mỗi bài đúng MỘT lần.

        Cùng một bài nằm trong hai track là hai dòng `tracks` khác nhau (mỗi
        track giữ bản sao riêng). Gộp theo `source_id` để danh sách không hiện
        trùng — chủ dự án dặn rõ chỗ này.

        Khoá gộp là KHOÁ DANH TÍNH (QĐ-027): mã video, không có thì `content_hash`
        của bài nhập từ đĩa. Hỏi `HAS_LINK` ở đây — tức chỉ gộp theo `source_id` —
        là một bài custom nằm trong hai track hiện ra hai lần, đúng cái lỗi chủ
        dự án đã báo cho bài YouTube.

        Dòng không có danh tính nào (nhập từ đĩa trước v11, chưa băm) thì rơi về
        gộp theo đường dẫn file: mỗi bản sao một dòng, như cũ.
        """
        try:
            rows = self._conn.execute(
                # Tên NHÌN THẤY, không phải tên YouTube (QĐ-019).
                "SELECT COALESCE(NULLIF(t.display_name, ''), t.real_name) AS title, "
                "       t.artist, t.duration_ms, t.cover_path, t.source_id, "
                "       MIN(t.id) AS id, t.file_path "
                "FROM tracks t JOIN playlist_items pi ON pi.track_id = t.id "
                "WHERE t.artist IS NOT NULL AND t.artist <> '' "
                "GROUP BY COALESCE(NULLIF(t.source_id, ''), "
                "                  NULLIF(t.content_hash, ''), t.file_path) "
                "ORDER BY COALESCE(NULLIF(t.display_name, ''), t.real_name) COLLATE NOCASE"
            ).fetchall()
        except sqlite3.Error:
            log.exception("Could not read songs of %s", artist)
            return []
        wanted = artist.strip().casefold()
        return [
            {
                "trackId": int(row["id"]),
                "title": row["title"] or "",
                "artist": row["artist"] or "",
                "durationMs": int(row["duration_ms"] or 0),
                "coverPath": row["cover_path"] or "",
                "sourceId": row["source_id"] or "",
            }
            for row in rows
            if _primary_of(row["artist"]).casefold() == wanted
        ]

    def owned_source_ids(self) -> set[str]:
        """Video ids the user already has, so recommendations can skip them."""
        try:
            rows = self._conn.execute(
                "SELECT DISTINCT source_id FROM tracks WHERE source_id IS NOT NULL"
            ).fetchall()
        except sqlite3.Error:
            log.exception("Could not read owned source ids")
            return set()
        return {row["source_id"] for row in rows if row["source_id"]}
