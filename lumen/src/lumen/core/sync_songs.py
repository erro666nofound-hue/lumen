"""Dựng dòng `tracks` cho bài chỉ có trong ảnh chụp (F-5, chiều GHI).

Đồng bộ mang DANH SÁCH đi, không mang mp3 đi. Nên máy nhận luôn gặp những bài
nó chưa từng tải: có mã video, có tên, có link — không có file.

Trước file này, `sync_restore` bỏ qua chúng và track đồng bộ về hiện ra RỖNG:
`snapshot["songs"]` được đẩy lên máy chủ rồi bị lờ đi lúc nhận, và dòng "tải
lại từ link gốc" ở giao diện không có gì để bấm.

Ba luật:

1. **`file_path` để TRỐNG, không bịa đường dẫn.** `""` ở tầng Python, `NULL`
   dưới database (migration v9 mở đường cho việc này). Mọi chỗ đọc file_path
   đã hiểu "rỗng = chưa có file"; một đường dẫn bịa thì không chỗ nào hiểu.
2. **Không đóng dấu `now()`.** `added_at` lấy nguyên văn mốc "thêm vào track"
   của ảnh chụp — xem CB-024.
3. **Thiếu tên hay thiếu link không được làm mất bài.** Mã video là thứ đủ để
   tải lại; tên hiện tạm bằng mã, lần tải về sẽ có tên thật.

File này giữ CẢ VÒNG ĐỜI của dòng chỗ trống, không chỉ lúc sinh ra: dựng
(`adopt_song`), tìm lại (`songs_needing_file`), rồi LẤP khi tải xong
(`fill_song`). Gom một chỗ vì cả ba đều phải biết đúng một luật — "rỗng nghĩa
là chưa có file" — và ba chỗ khác nhau hiểu lệch nhau thì không ai bắt được.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from .sync_state import HAS_LINK, IDENTITY_KEY, item_name
from .youtube import watch_url

# Ảnh chụp: `songs[khoá danh tính] = {url, title, artist, duration_ms[, custom]}`.
# Khoá là mã video, hoặc hash của một bài nhập từ đĩa (QĐ-027). `custom: True`
# là thứ phân biệt hai loại — xem `adopt_song`.
SongTable = dict[str, dict[str, Any]]


def resolve_track(
    conn: sqlite3.Connection,
    key: str,
    songs: SongTable,
    added_at: int,
    owned: dict[str, tuple[int, str]],
    playlist_id: int,
) -> tuple[int, bool]:
    """Pick the tracks row for a synced song, creating a file-less one when it is new.

    Returns (track_id, has_file); no file means "cần tải lại từ link gốc".

    Dòng của track KHÁC không bao giờ được mượn, kể cả khi nó đã có file sẵn:
    một dòng mang MỘT tên riêng, nên hai track dùng chung một dòng là hai cái
    tên đè lên nhau (CB-036). Track này lấy dòng riêng, `file_path` để trống,
    rồi hàng đợi lấp — chép từ bản có sẵn trên đĩa nếu máy này đã có, tải từ
    link nếu chưa (QĐ-019: mỗi track một bản băng, một cái nhãn).
    """
    found = owned.get(key) or _unclaimed_copy(conn, key, playlist_id)
    if found is None:
        return adopt_song(conn, key, songs, added_at), False
    track_id, file_path = found
    return track_id, bool(file_path)


def name_track(conn: sqlite3.Connection, track_id: int, item: dict[str, Any]) -> None:
    """Put the snapshot row's owner-given name on its tracks row; the later stamp wins.

    Chỉ `display_name` (+ mốc của nó). `real_name` là của YouTube và không đường
    nào từ đồng bộ được đè lên nó — QĐ-019 luật 1, cùng lối nghĩ với `fill_song`.

    KHÔNG `now()`: mốc lấy nguyên văn từ bản kê đã hoà (CB-024).

    Chốt `display_name_updated_at < ?` không thừa, kể cả sau khi `_unclaimed_copy`
    thôi cho hai track mượn chung một dòng (CB-036). Database dựng trước bản vá
    vẫn còn những dòng dùng chung như thế, và chốt này là thứ giữ cho chúng hỏng
    CÓ THỨ TỰ: tên mốc muộn nhất thắng, áp track nào trước cũng ra một kết quả.
    """
    when, name = item_name(item)
    # Mốc 0 nghĩa là "chưa ai đặt tên riêng" — không có gì để áp, và ghi đè một
    # cái tên đang có bằng chuỗi rỗng ở đây là xoá tên mà không ai yêu cầu.
    if when <= 0:
        return
    conn.execute(
        "UPDATE tracks SET display_name = ?, display_name_updated_at = ? "
        "WHERE id = ? AND display_name_updated_at < ?",
        (name, when, track_id, when),
    )


def _unclaimed_copy(
    conn: sqlite3.Connection, key: str, playlist_id: int
) -> tuple[int, str] | None:
    """Return a local copy of a song that NO other playlist is holding, or None.

    Dòng đang nằm trong một track khác bị loại thẳng — đó là bản băng của track
    đó, có nhãn riêng của track đó (CB-036). Còn lại hai loại được nhận: dòng
    chưa thuộc track nào (bài tải rời, hoặc bản sót sau khi xoá track), và dòng
    vừa dựng cho CHÍNH track này trong cùng lượt áp — cái sau là cách ảnh chụp
    liệt một bài hai lần vẫn ra một dòng.
    """
    # Bản CÓ FILE thắng bản chỗ trống: cùng một bài có thể có cả hai, và nối
    # track vào dòng chỗ trống trong khi máy này đã tải rồi là bấm không kêu.
    row = conn.execute(
        f"SELECT t.id, t.file_path FROM tracks t WHERE {IDENTITY_KEY} = ? AND t.id NOT IN "
        "(SELECT track_id FROM playlist_items WHERE playlist_id != ?) "
        "ORDER BY (t.file_path IS NULL OR t.file_path = ''), t.id LIMIT 1",
        (key, playlist_id),
    ).fetchone()
    return None if row is None else (int(row["id"]), str(row["file_path"] or ""))


def adopt_song(
    conn: sqlite3.Connection, key: str, songs: SongTable, added_at: int
) -> int:
    """Insert a file-less tracks row for a synced song and return its track id.

    Khoá rơi vào ĐÚNG MỘT trong hai cột. Bài YouTube: `source_id`, kèm link tải
    lại. Bài nhập từ đĩa (`custom`): `content_hash`, `source_id` để NULL và
    KHÔNG bịa link — `watch_url(<64 ký tự hex>)` là một địa chỉ không tồn tại,
    và dòng mang nó sẽ nằm trong hàng đợi tải hỏng đi hỏng lại (QĐ-027).
    """
    song = songs.get(key) or {}
    if song.get("custom"):
        cursor = conn.execute(
            "INSERT INTO tracks (source_id, content_hash, source_url, real_name, "
            "artist, duration_ms, file_path, cover_path, added_at) "
            "VALUES (NULL, ?, '', ?, ?, ?, NULL, NULL, ?)",
            (
                key,
                str(song.get("title", "")) or key,
                str(song.get("artist", "")),
                int(song.get("duration_ms", 0)),
                added_at,
            ),
        )
        return int(cursor.lastrowid)
    cursor = conn.execute(
        # Chỉ `real_name`: bản kê hiện mang tên YouTube của bài, chưa mang tên
        # riêng của từng dòng (QĐ-019 để việc đó cho `items[]` sau này). Dòng
        # dựng lên ở đây vì thế CHƯA có tên riêng — trống đúng nghĩa "chưa đặt".
        "INSERT INTO tracks (source_id, source_url, real_name, artist, duration_ms, "
        "file_path, cover_path, added_at) VALUES (?, ?, ?, ?, ?, NULL, NULL, ?)",
        (
            key,
            str(song.get("url", "")) or watch_url(key),
            str(song.get("title", "")) or key,
            str(song.get("artist", "")),
            int(song.get("duration_ms", 0)),
            added_at,
        ),
    )
    return int(cursor.lastrowid)


def songs_needing_file(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return the file-less rows that a LINK can refill, oldest first.

    HAS_LINK, và đây là chỗ DUY NHẤT trong lượt tách QĐ-027 thật sự muốn hỏi câu
    đó. Hàng đợi này chỉ biết một cách lấy file về: tải từ YouTube. Một dòng nhập
    từ đĩa có `content_hash` nhưng mất file thì lấy lại từ kho R2 — việc của một
    hàng đợi khác, chưa có. Xếp nó vào đây là hỏng đi hỏng lại, mỗi vòng một lần.
    """
    return list(
        conn.execute(
            "SELECT t.* FROM tracks t WHERE (t.file_path IS NULL OR t.file_path = '') "
            f"AND {HAS_LINK} ORDER BY t.added_at, t.id"
        )
    )


def fill_song(
    conn: sqlite3.Connection,
    track_id: int,
    *,
    file_path: str,
    real_name: str,
    artist: str,
    duration_ms: int,
    cover_path: str | None,
    source_url: str,
) -> bool:
    """Give a file-less row the file that just finished downloading, in place.

    Trả False khi file đó đã thuộc về một dòng KHÁC (`file_path` là UNIQUE) —
    người gọi tự quyết, ở đây không nuốt.
    """
    # UPDATE chứ không INSERT: dòng này đã nằm trong `playlist_items`, đã có
    # thứ tự, đã được người dùng nhìn thấy. Thêm dòng mới là để lại một dòng
    # chết vĩnh viễn trong track — QĐ-016.
    #
    # `added_at` KHÔNG nằm trong câu này, cố ý: mốc đó là "thêm vào track" của
    # máy kia, không phải "tải xong lúc mấy giờ" của máy này (CB-024).
    #
    # Và `display_name` cũng KHÔNG nằm trong câu này. Tải xong là biết tên
    # YouTube đang gọi bài này là gì -> làm mới `real_name`; tên chủ dự án đặt
    # thì không ai ở đây được đụng (QĐ-019 luật 1). Đây đúng là chỗ đã bắt lỗi ở
    # vòng F-5f: tải lại đè "Bài của máy A một" thành "Me at the zoo".
    try:
        cursor = conn.execute(
            "UPDATE tracks SET file_path = ?, real_name = ?, artist = ?, "
            "duration_ms = ?, cover_path = ?, source_url = ? "
            "WHERE id = ? AND (file_path IS NULL OR file_path = '')",
            (file_path, real_name, artist, duration_ms, cover_path, source_url, track_id),
        )
    except sqlite3.IntegrityError:
        return False
    return cursor.rowcount > 0
