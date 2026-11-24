"""Đánh giá nghệ sĩ do người dùng tự đặt, và cách nó đè lên phép đoán.

App vẫn suy mức yêu thích từ số bài đã tải (core/tiers.py). Nhưng suy thì hay
sai: tải 5 bài của một kênh remix không có nghĩa là thích kênh đó, mà thích một
nghệ sĩ lắm khi chỉ mới tải đúng một bài. File này cho người dùng nói thẳng.

Không Qt, không mạng. Main thread only, như mọi repository ở đây.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass

from lumen.core import sync_clock
from lumen.core.tiers import TIER_FAV, TIER_NORMAL, TIER_VERY, normalise_artist

log = logging.getLogger(__name__)

# Chặn hẳn: không bao giờ đề xuất, dù đã tải bao nhiêu bài của họ.
RATING_BLOCKED = -1
RATING_NORMAL = 0
RATING_FAV = 1
RATING_VERY = 2

_RATINGS = (RATING_BLOCKED, RATING_NORMAL, RATING_FAV, RATING_VERY)

# Ba mức sau ánh xạ thẳng sang hệ mức đã có, nên trang khám phá không phải đổi
# luật — chỉ đổi NGUỒN của mức đó.
_TIER_OF = {
    RATING_NORMAL: TIER_NORMAL,
    RATING_FAV: TIER_FAV,
    RATING_VERY: TIER_VERY,
}


def tier_of_rating(rating: int) -> str | None:
    """Mức ứng với một đánh giá; None nghĩa là bị chặn (không lên trang)."""
    return _TIER_OF.get(rating)


@dataclass(frozen=True, slots=True)
class ArtistPref:
    """Một nghệ sĩ người dùng đã tự đánh giá."""

    name: str
    rating: int
    added_at: int


class ArtistPrefsRepository:
    """Đọc/ghi đánh giá nghệ sĩ. Tên luôn được chuẩn hoá trước khi chạm DB."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def set_rating(self, name: str, rating: int) -> bool:
        """Đặt đánh giá cho một nghệ sĩ; trả về False nếu tên/điểm không hợp lệ."""
        clean = normalise_artist(name)
        if not clean or rating not in _RATINGS:
            return False
        try:
            self._conn.execute(
                "INSERT INTO artist_prefs (name, rating, added_at) VALUES (?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET rating = excluded.rating, "
                "added_at = excluded.added_at",
                (clean, int(rating), sync_clock.now()),
            )
            # `added_at` là đồng hồ hoà của đánh giá này, không phải "lần đầu
            # đánh giá". Không bơm nó khi SỬA điểm thì đồng hồ đứng im, và cú
            # sửa mới nhất thua cú đánh giá cũ hơn bên máy kia.
            sync_clock.unbury(self._conn, sync_clock.KIND_ARTIST_PREF, clean)
            self._conn.commit()
        except sqlite3.Error:
            log.exception("Cannot rate artist %s", clean)
            return False
        return True

    def clear(self, name: str) -> bool:
        """Bỏ đánh giá tay, trả nghệ sĩ đó về cho phép đoán tự động."""
        clean = normalise_artist(name)
        if not clean:
            return False
        try:
            cursor = self._conn.execute("DELETE FROM artist_prefs WHERE name = ?", (clean,))
            if cursor.rowcount > 0:
                sync_clock.bury(self._conn, sync_clock.KIND_ARTIST_PREF, clean)
            self._conn.commit()
        except sqlite3.Error:
            log.exception("Cannot clear rating for %s", clean)
            return False
        return cursor.rowcount > 0

    def all(self) -> list[ArtistPref]:
        """Mọi đánh giá, điểm cao trước rồi tới tên."""
        try:
            rows = self._conn.execute(
                "SELECT name, rating, added_at FROM artist_prefs ORDER BY rating DESC, name"
            ).fetchall()
        except sqlite3.Error:
            log.exception("Cannot read artist ratings")
            return []
        return [
            ArtistPref(name=r["name"], rating=int(r["rating"]), added_at=int(r["added_at"]))
            for r in rows
        ]

    def ratings(self) -> dict[str, int]:
        """Bản đồ tên -> điểm, để tra nhanh khi dựng trang khám phá."""
        return {pref.name: pref.rating for pref in self.all()}


class ArtistAvatarCache:
    """Đệm link ảnh đại diện kênh. Lấy được nó tốn ~3s nên chỉ lấy một lần."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def all(self) -> dict[str, str]:
        """Tên -> link ảnh. Chuỗi rỗng = đã hỏi và không có."""
        try:
            rows = self._conn.execute("SELECT name, url FROM artist_avatars").fetchall()
        except sqlite3.Error:
            log.exception("Could not read artist avatars")
            return {}
        return {row["name"]: row["url"] for row in rows}

    def known(self) -> set[str]:
        """Tên đã hỏi rồi, kể cả những tên không tìm ra ảnh."""
        return set(self.all())

    def put(self, name: str, url: str) -> None:
        clean = normalise_artist(name)
        if not clean:
            return
        try:
            self._conn.execute(
                "INSERT INTO artist_avatars (name, url, fetched_at) VALUES (?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET url = excluded.url, "
                "  fetched_at = excluded.fetched_at",
                (clean, url or "", int(time.time())),
            )
            self._conn.commit()
        except sqlite3.Error:
            # Mất đệm chỉ tốn thời gian, không sai kết quả — không bao giờ ném.
            log.warning("Could not cache avatar for %s", clean, exc_info=True)
