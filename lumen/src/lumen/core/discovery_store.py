"""Keep discovery results on disk so the page is not rebuilt from scratch daily.

Ranking by like/view needs a full extraction per video (~1.6s each), so a
freshly built page costs tens of seconds. The owner's rule for it: fetch once a
day, no streaming of live data. This is where "once a day" is enforced.

SQL only, no Qt. Main thread, like every repository here.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time

from lumen.core.discovery import from_payload, to_payload
from lumen.core.youtube_search import SearchResult

log = logging.getLogger(__name__)

# Một ngày. Chủ dự án đã chốt: "app sẽ chỉ lấy dữ liệu/ngày".
DEFAULT_MAX_AGE_S = 24 * 60 * 60

# TĂNG SỐ NÀY mỗi khi đổi luật dựng đề xuất (lọc, xếp hạng, số bài mỗi hàng).
# Đệm dựng theo luật cũ sẽ tự bị bỏ qua thay vì sống tiếp tới 24 giờ.
#   1 = thêm bộ lọc "chỉ lấy video hạng mục Music"
#   2 = video chưa biết hạng mục bị loại khi lượt bóc lấy được phần lớn hạng mục
#   3 = không cất vào đệm nữa những lượt dựng mà bộ lọc không chạy được
RULES_VERSION = 3


class DiscoveryCache:
    """Per-artist store of ranked recommendations, with an age limit."""

    def __init__(self, connection: sqlite3.Connection, max_age_s: int = DEFAULT_MAX_AGE_S) -> None:
        self._conn = connection
        self._max_age_s = max_age_s

    def get(self, artist: str, *, now: int | None = None) -> list[SearchResult] | None:
        """Songs for one artist; None when never asked or too old.

        Một danh sách RỖNG khác hẳn None: nó nghĩa là "đã hỏi rồi, kênh này
        không có nhạc". Gọi bên trên dựa vào phân biệt đó để không đi tìm lại.
        """
        stamp = int(time.time()) if now is None else now
        try:
            row = self._conn.execute(
                "SELECT payload, fetched_at FROM discovery_cache "
                "WHERE artist = ? AND rules_version = ?",
                (artist, RULES_VERSION),
            ).fetchone()
        except sqlite3.Error:
            log.exception("Could not read discovery cache for %s", artist)
            return None
        if row is None or stamp - int(row["fetched_at"]) >= self._max_age_s:
            return None
        try:
            return from_payload(json.loads(row["payload"]))
        except (ValueError, TypeError):
            # A cache line we can no longer read is just a cache miss.
            log.warning("Discarding unreadable discovery cache for %s", artist)
            return None

    def put(self, artist: str, songs: list[SearchResult], *, now: int | None = None) -> None:
        """Store one artist's songs, replacing anything already there."""
        stamp = int(time.time()) if now is None else now
        try:
            self._conn.execute(
                "INSERT INTO discovery_cache (artist, payload, fetched_at, rules_version) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(artist) DO UPDATE SET "
                "  payload = excluded.payload, fetched_at = excluded.fetched_at, "
                "  rules_version = excluded.rules_version",
                (artist, json.dumps(to_payload(songs)), stamp, RULES_VERSION),
            )
            self._conn.commit()
        except sqlite3.Error:
            # Losing the cache costs time, never correctness -- never raise.
            log.warning("Could not cache discovery results for %s", artist, exc_info=True)

    def clear(self) -> None:
        """Throw the whole cache away (a manual "làm mới" from the UI)."""
        try:
            self._conn.execute("DELETE FROM discovery_cache")
            self._conn.commit()
        except sqlite3.Error:
            log.warning("Could not clear discovery cache", exc_info=True)
