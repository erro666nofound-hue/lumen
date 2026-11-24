"""QĐ-027: `HAS_SOURCE` tách làm hai, và SÁU chỗ phải chọn đúng câu nó định hỏi.

    HAS_IDENTITY — "bản kê gọi tên được dòng này không?"  → được vào ảnh chụp
    HAS_LINK     — "tải lại được từ link YouTube không?"  → được vào hàng đợi tải

Bài YouTube trả lời CÓ cho cả hai, nên suốt F-5a′ không ai thấy đó là hai câu.
Bài nhập từ đĩa tách chúng ra: có `content_hash` (sha256 của chính byte trong
file, cũng là địa chỉ của nó trên R2) thì bản kê gọi tên được nó, nhưng không có
link nào để tải lại.

File này gom ĐỦ SÁU chỗ vào một chỗ, mỗi chỗ một phép kiểm mang tên file của nó.
Lý do gom: QĐ-027 nói thẳng *"nửa lượt còn tệ hơn không làm"* — sót một chỗ thì
bài custom rơi khỏi bản kê mà KHÔNG AI BÁO, và chủ dự án mất nhạc mà app vừa hứa
là đã sao lưu. Rải sáu phép kiểm ra năm file test thì phiên sau xoá mất một cái
cũng không ai thấy; ở đây thì thiếu một cái là nhìn ra ngay.
"""

from __future__ import annotations

import sqlite3

import pytest

from lumen.core import history, models, sync_clock, sync_songs
from lumen.core.repository import PlaylistRepository, TrackRepository

from conftest import make_track

# 64 ký tự hex — đúng hình dạng sha256 mà kho R2 dùng làm địa chỉ.
HASH_A = "a" * 64
HASH_B = "b" * 64


def _youtube(tracks: TrackRepository, source_id: str, **fields: object) -> int:
    """Bài tải từ YouTube: có danh tính VÀ có link."""
    track = tracks.add(
        make_track(source_id=source_id, source_url=f"https://youtu.be/{source_id}", **fields)
    )
    assert track.id is not None
    return track.id


def _hashed(tracks: TrackRepository, content_hash: str, **fields: object) -> int:
    """Bài nhập từ đĩa ĐÃ băm: có danh tính, KHÔNG có link. Đây là ca thử."""
    track = tracks.add(
        make_track(source_id=None, source_url=None, content_hash=content_hash, **fields)
    )
    assert track.id is not None
    return track.id


def _unhashed(tracks: TrackRepository, **fields: object) -> int:
    """Bài nhập từ đĩa CHƯA băm (có từ trước v11): không danh tính, không link."""
    track = tracks.add(make_track(source_id=None, source_url=None, **fields))
    assert track.id is not None
    return track.id


# --------------------------------------------------------------------------
# core/sync_clock.py: bài đã băm vẫn có bia mộ khi rời track
# --------------------------------------------------------------------------


def test_sync_clock_writes_a_tombstone_for_a_hashed_import(
    conn: sqlite3.Connection, tracks: TrackRepository, playlists: PlaylistRepository
) -> None:
    """Thiếu bia mộ thì cú xoá không bao giờ dính: vòng hoà sau máy kia đẩy bài về lại."""
    made = playlists.create("Chill")
    hashed_id = _hashed(tracks, HASH_A)
    playlists.add_track(made.id, hashed_id)
    playlists.add_track(made.id, _unhashed(tracks))

    keys = sync_clock.item_keys_of_playlist(conn, made.id)
    uuid_value = sync_clock.playlist_uuid(conn, made.id)

    assert keys == [sync_clock.item_key(str(uuid_value), HASH_A)]
    assert sync_clock.item_keys_of_track(conn, hashed_id) == keys


# --------------------------------------------------------------------------
# 4/6 — core/sync_songs.py: hàng đợi TẢI mới là chỗ thật sự hỏi HAS_LINK
# --------------------------------------------------------------------------


def test_sync_songs_keeps_a_hashed_import_out_of_the_download_queue(
    conn: sqlite3.Connection, tracks: TrackRepository
) -> None:
    """Chỗ DUY NHẤT trong sáu chỗ đáng hỏi HAS_LINK.

    Hàng đợi này chỉ biết một cách lấy file: tải từ YouTube. Bài đã băm mất file
    thì phải kéo về từ kho R2 — xếp nó vào đây là hỏng đi hỏng lại mỗi vòng.
    """
    _youtube(tracks, "aaa", file_path="")
    _hashed(tracks, HASH_A, file_path="")

    queued = sync_songs.songs_needing_file(conn)

    assert [row["source_id"] for row in queued] == ["aaa"]


def test_sync_songs_adopts_a_hashed_song_without_inventing_a_link(
    conn: sqlite3.Connection,
) -> None:
    """`adopt_song` phải bỏ khoá vào ĐÚNG cột, và không bịa `watch?v=<hash>`."""
    songs: sync_songs.SongTable = {
        HASH_A: {"url": "", "title": "Bản thu nhà", "artist": "", "duration_ms": 60, "custom": True}
    }

    track_id = sync_songs.adopt_song(conn, HASH_A, songs, added_at=10)

    row = conn.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
    assert row["content_hash"] == HASH_A
    assert row["source_id"] is None
    assert HASH_A not in (row["source_url"] or ""), "không có link giả nào được dựng"


# --------------------------------------------------------------------------
# 5/6 — core/history.py: hai bản sao của cùng một bài đã băm gộp làm MỘT
# --------------------------------------------------------------------------


def test_history_groups_the_copies_of_one_hashed_import(
    conn: sqlite3.Connection, tracks: TrackRepository, playlists: PlaylistRepository
) -> None:
    """Thêm bài vào hai track là hai dòng, hai bản sao trên đĩa — nhưng MỘT bài."""
    made = playlists.create("Chill")
    other = playlists.create("Focus")
    playlists.add_track(made.id, _hashed(tracks, HASH_A, artist="Nhạc sĩ", title="Bản thu nhà"))
    playlists.add_track(other.id, _hashed(tracks, HASH_A, artist="Nhạc sĩ", title="Bản thu nhà"))
    # Hai bài CHƯA băm thì vẫn phải hiện hai lần: không có gì gọi tên chúng.
    playlists.add_track(made.id, _unhashed(tracks, artist="Nhạc sĩ", title="Chưa băm"))
    playlists.add_track(other.id, _unhashed(tracks, artist="Nhạc sĩ", title="Chưa băm"))

    found = history.DownloadHistoryRepository(conn).songs_of_artist("Nhạc sĩ")
    titles = sorted(song["title"] for song in found)

    assert titles == ["Bản thu nhà", "Chưa băm", "Chưa băm"]


# --------------------------------------------------------------------------
# 6/6 — core/models.py: gộp theo danh tính, nhưng nhãn vẫn hỏi LINK
# --------------------------------------------------------------------------


def test_models_dedupes_by_identity_but_labels_by_link() -> None:
    """Một file, HAI câu hỏi khác nhau — đây là bằng chứng lượt tách này có nghĩa.

    `one_row_per_song` hỏi danh tính: hai bản sao của một bài đã băm là một bài.
    `artist_label` hỏi link: bài nhập từ đĩa ĐÃ sao lưu VẪN đọc là `Custom mp3`.
    Đó là lý do QĐ-027 xoá hẳn huy hiệu "máy này" thay vì đổi tên nó.
    """
    rows = [
        models.Track(id=1, content_hash=HASH_A, artist="Nhạc sĩ"),
        models.Track(id=2, content_hash=HASH_A, artist="Nhạc sĩ"),
        models.Track(id=3, content_hash=HASH_B, artist="Nhạc sĩ"),
        models.Track(id=4, source_id=None, content_hash=None, artist="Nhạc sĩ"),
        models.Track(id=5, source_id=None, content_hash=None, artist="Nhạc sĩ"),
    ]

    kept = models.one_row_per_song(rows)

    assert [track.id for track in kept] == [1, 3, 4, 5]
    assert kept[0].artist_label == models.CUSTOM_ARTIST, "đã băm vẫn là Custom mp3"
