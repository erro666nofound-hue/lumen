"""Đồng hồ và bia mộ cho đồng bộ giữa các máy (lược đồ v8).

Lược đồ v8 đã có cột, nhưng cột rỗng thì vô dụng: mọi mốc thời gian là 0 và
bảng bia mộ rỗng vĩnh viễn. Hoà dữ liệu bằng đồng hồ toàn 0 thì mọi máy trông
như "chưa ai sửa" — tệ hơn là không hoà. File này là chỗ DUY NHẤT ghi vào các
cột đó; repository chỉ gọi vào đây.

Để riêng khỏi `repository.py` vì file đó đã 363 dòng (quá mức ~250), và vì đây
là một mối lo khác hẳn: repository trả lời "thư viện đang có gì", file này trả
lời "ai sửa lúc nào, và cái gì đã bị xoá".

KHÔNG hàm nào ở đây gọi `commit()`. Chúng chạy BÊN TRONG khối ghi của
repository, nên phải sống chết cùng giao dịch đó: bơm đồng hồ mà thao tác thật
lại rollback thì đồng hồ nói dối.
"""

from __future__ import annotations

import sqlite3
import time

# Vòng tròn có thật: `sync_state` nạp `sync_clock` để lấy đồng hồ, còn ở đây
# cần đúng MỘT bản định nghĩa của `HAS_IDENTITY` (hai chỗ định nghĩa là hai
# chỗ lệch nhau). Dạng `from . import` buộc mọi lần đọc phải qua tên module,
# nên hằng số chỉ được tra lúc GỌI HÀM — lúc đó cả hai module đã nạp xong.
# Đổi sang `from .sync_state import HAS_IDENTITY` là nổ ngay lúc nạp.
from . import sync_state

# Loại bia mộ. Khoá phải là danh tính BỀN giữa các máy, không bao giờ là `id`
# AUTOINCREMENT — track #3 của máy A và track #3 của máy B là hai thứ khác nhau.
KIND_PLAYLIST = "playlist"  # khoá: playlists.uuid
KIND_PLAYLIST_ITEM = "playlist_item"  # khoá: "{playlist_uuid}:{khoá danh tính}"
KIND_ARTIST_PREF = "artist_pref"  # khoá: tên đã chuẩn hoá (đã là PRIMARY KEY)

# Thứ tự track ở thanh bên là ý định về CẢ danh sách, giống thứ tự bài trong
# một track — nên nó có MỘT đồng hồ chung, không phải đồng hồ của từng track.
# Nếu bơm `playlists.updated_at` của mọi track bị dời thì một cú kéo thả vặt sẽ
# làm mọi track "mới hơn", và nuốt mất cú đổi tên bên máy kia.
# Nằm ở bảng `meta` nên không cần migration v9.
PLAYLIST_ORDER_KEY = "playlist_order_updated_at"


def now() -> int:
    """Return the current wall-clock time in whole seconds."""
    return int(time.time())


def _at(when: int | None) -> int:
    """Return the given timestamp, or the current time when it is None."""
    return now() if when is None else int(when)


# --------------------------------------------------------------------------
# Danh tính bền
# --------------------------------------------------------------------------


def playlist_uuid(conn: sqlite3.Connection, playlist_id: int) -> str | None:
    """Return the stable cross-machine uuid of a playlist, or None if it is gone."""
    row = conn.execute("SELECT uuid FROM playlists WHERE id = ?", (playlist_id,)).fetchone()
    return None if row is None else str(row["uuid"])


def item_key(playlist_uuid_value: str, source_id: str) -> str:
    """Build the tombstone key for one (playlist, song) pair."""
    return f"{playlist_uuid_value}:{source_id}"


def item_keys_of_playlist(
    conn: sqlite3.Connection, playlist_id: int, track_ids: list[int] | None = None
) -> list[str]:
    """Return tombstone keys for the songs of a playlist that have a stable identity.

    HAS_IDENTITY, không phải HAS_LINK. Bia mộ trả lời câu *"bản kê gọi tên được
    dòng này không"*, không phải *"tải lại được không"* — một bài nhập từ đĩa có
    `content_hash` đi trong bản kê, nên nó cũng phải để lại bia mộ (QĐ-027).
    Thiếu bia mộ thì xoá nó ở máy này, vòng hoà sau máy kia đẩy nó về lại: cú
    xoá không bao giờ dính, và chủ dự án bấm xoá mãi không xong.

    Dòng không có danh tính nào thì vẫn bị bỏ ra, thay vì bịa một khoá theo tên
    + độ dài — bịa sai thì bia mộ của máy này sẽ xoá nhầm bài của máy kia.
    """
    uuid_value = playlist_uuid(conn, playlist_id)
    if uuid_value is None:
        return []
    sql = (
        f"SELECT {sync_state.IDENTITY_KEY} AS key FROM tracks t "
        "JOIN playlist_items pi ON pi.track_id = t.id "
        f"WHERE pi.playlist_id = ? AND {sync_state.HAS_IDENTITY}"
    )
    params: list[object] = [playlist_id]
    if track_ids is not None:
        if not track_ids:
            return []
        sql += f" AND t.id IN ({','.join('?' for _ in track_ids)})"
        params.extend(int(t) for t in track_ids)
    rows = conn.execute(sql, params).fetchall()
    return [item_key(uuid_value, str(row["key"])) for row in rows]


def item_keys_of_track(conn: sqlite3.Connection, track_id: int) -> list[str]:
    """Return tombstone keys for every playlist the given song currently sits in."""
    rows = conn.execute(
        f"SELECT p.uuid, {sync_state.IDENTITY_KEY} AS key FROM tracks t "
        "JOIN playlist_items pi ON pi.track_id = t.id "
        "JOIN playlists p ON p.id = pi.playlist_id "
        f"WHERE t.id = ? AND {sync_state.HAS_IDENTITY}",
        (track_id,),
    ).fetchall()
    return [item_key(str(row["uuid"]), str(row["key"])) for row in rows]


# --------------------------------------------------------------------------
# Đồng hồ
# --------------------------------------------------------------------------


def touch_playlist(
    conn: sqlite3.Connection, playlist_id: int, *, order: bool = False, when: int | None = None
) -> None:
    """Bump a playlist's clock: order=True for song order, otherwise name/icon."""
    # Hai đồng hồ tách rời vì luật hoà của chúng khác nhau: đổi tên hoà theo
    # TỪNG track, còn thứ tự bài là ý định về CẢ danh sách nên phải lấy trọn
    # của một máy. Nhập chung một cột thì mỗi lần đổi tên là nuốt mất thứ tự
    # của máy kia.
    column = "order_updated_at" if order else "updated_at"
    conn.execute(
        f"UPDATE playlists SET {column} = ? WHERE id = ?", (_at(when), playlist_id)
    )


def touch_playlist_order(conn: sqlite3.Connection, when: int | None = None) -> None:
    """Bump the single clock for the sidebar order of playlists."""
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (PLAYLIST_ORDER_KEY, str(_at(when))),
    )


def playlist_order_updated_at(conn: sqlite3.Connection) -> int:
    """Return the sidebar-order clock, or 0 when nobody has reordered yet."""
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (PLAYLIST_ORDER_KEY,)).fetchone()
    if row is None:
        return 0
    try:
        return int(row["value"])
    except (TypeError, ValueError):
        # Giá trị hỏng thì coi như chưa ai sắp lại: 0 luôn thua mọi mốc thật,
        # nên máy này nhường thứ tự cho máy kia thay vì áp một mốc bịa.
        return 0


# --------------------------------------------------------------------------
# Bia mộ
# --------------------------------------------------------------------------


def bury(conn: sqlite3.Connection, kind: str, key: str, when: int | None = None) -> None:
    """Record that one item was deleted, keeping the later timestamp on conflict."""
    bury_many(conn, kind, [key], when)


def bury_many(
    conn: sqlite3.Connection, kind: str, keys: list[str], when: int | None = None
) -> None:
    """Record that several items were deleted, keeping the later timestamp on conflict."""
    if not keys:
        return
    removed_at = _at(when)
    # `max(...)` hai đối số là hàm vô hướng, không phải hàm gộp: giữ mốc MUỘN
    # hơn. Xoá rồi thêm lại rồi xoá lại mà bia mộ tụt về mốc cũ thì cú xoá sau
    # cùng sẽ thua cú thêm ở giữa, và bài đã xoá MỌC LẠI.
    conn.executemany(
        "INSERT INTO sync_tombstones (kind, key, removed_at) VALUES (?, ?, ?) "
        "ON CONFLICT(kind, key) DO UPDATE SET removed_at = max(removed_at, excluded.removed_at)",
        [(kind, key, removed_at) for key in keys],
    )


def unbury(conn: sqlite3.Connection, kind: str, key: str) -> None:
    """Drop the tombstone of an item that has come back."""
    unbury_many(conn, kind, [key])


def unbury_many(conn: sqlite3.Connection, kind: str, keys: list[str]) -> None:
    """Drop the tombstones of items that have come back."""
    if not keys:
        return
    # Thêm lại một bài mà bia mộ cũ còn nằm đó thì ảnh chụp của chính máy này
    # đã tự mâu thuẫn. Luật hoà vẫn xử đúng nhờ so `added_at` với `removed_at`,
    # nhưng dọn ngay tại đây thì bảng bia mộ không phình vô hạn.
    conn.executemany(
        "DELETE FROM sync_tombstones WHERE kind = ? AND key = ?",
        [(kind, key) for key in keys],
    )


def tombstones(conn: sqlite3.Connection, kind: str | None = None) -> dict[str, int]:
    """Return {key: removed_at} for one kind, or for every kind when kind is None."""
    if kind is None:
        rows = conn.execute("SELECT kind, key, removed_at FROM sync_tombstones").fetchall()
        return {f"{row['kind']}:{row['key']}": int(row["removed_at"]) for row in rows}
    rows = conn.execute(
        "SELECT key, removed_at FROM sync_tombstones WHERE kind = ?", (kind,)
    ).fetchall()
    return {str(row["key"]): int(row["removed_at"]) for row in rows}
