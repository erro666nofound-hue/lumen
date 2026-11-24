"""F-5a′: các cột v8 phải được GHI VÀO, không chỉ tồn tại."""

from __future__ import annotations

import sqlite3

import pytest

from lumen.core import sync_clock
from lumen.core.artist_prefs import RATING_FAV, RATING_VERY, ArtistPrefsRepository
from lumen.core.tiers import normalise_artist
from lumen.core.repository import PlaylistRepository, TrackRepository

from conftest import make_track


class FakeClock:
    """Đồng hồ gõ tay: time.time() chỉ có độ phân giải GIÂY nên hai thao tác
    liên tiếp trong test thật sẽ ra cùng một mốc, và mọi phép so 'mới hơn'
    đều thành vô nghĩa."""

    def __init__(self, start: int = 1_000) -> None:
        self.value = start

    def __call__(self) -> int:
        return self.value

    def tick(self, seconds: int = 10) -> int:
        self.value += seconds
        return self.value


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    """Thay sync_clock.now() bằng đồng hồ gõ tay cho mọi nơi gọi vào nó."""
    fake = FakeClock()
    monkeypatch.setattr(sync_clock, "now", fake)
    return fake


def _row(conn: sqlite3.Connection, playlist_id: int) -> sqlite3.Row:
    return conn.execute(
        "SELECT uuid, updated_at, order_updated_at FROM playlists WHERE id = ?",
        (playlist_id,),
    ).fetchone()


# --- Đồng hồ của track ------------------------------------------------------


def test_create_stamps_both_clocks_not_zero(
    conn: sqlite3.Connection, playlists: PlaylistRepository, clock: FakeClock
) -> None:
    """create() phải đóng dấu cả hai đồng hồ; 0 nghĩa là 'chưa ai sửa' và thua mọi máy khác."""
    made = playlists.create("Chill")
    row = _row(conn, made.id)

    assert len(row["uuid"]) == 32
    assert row["updated_at"] == clock.value
    assert row["order_updated_at"] == clock.value


def test_rename_bumps_name_clock_only(
    conn: sqlite3.Connection, playlists: PlaylistRepository, clock: FakeClock
) -> None:
    """Đổi tên KHÔNG được chạm đồng hồ thứ tự: gộp chung là nuốt thứ tự của máy kia."""
    made = playlists.create("Chill")
    born = clock.value
    playlists.rename(made.id, "Focus")
    row = _row(conn, made.id)

    assert row["updated_at"] == clock.tick(0) == born  # chưa gõ, cùng giây
    playlists.rename(made.id, "Deep")
    assert _row(conn, made.id)["updated_at"] == born

    clock.tick()
    playlists.rename(made.id, "Night")
    row = _row(conn, made.id)
    assert row["updated_at"] == clock.value
    assert row["order_updated_at"] == born


def test_set_icon_bumps_name_clock(
    conn: sqlite3.Connection, playlists: PlaylistRepository, clock: FakeClock
) -> None:
    """Đổi icon cũng là sửa chính track đó."""
    made = playlists.create("Chill")
    born = clock.value
    clock.tick()
    playlists.set_icon(made.id, "🌙")
    row = _row(conn, made.id)

    assert row["updated_at"] == clock.value
    assert row["order_updated_at"] == born


def test_reorder_tracks_bumps_order_clock_only(
    conn: sqlite3.Connection,
    tracks: TrackRepository,
    playlists: PlaylistRepository,
    clock: FakeClock,
) -> None:
    """Sắp lại bài chỉ chạm đồng hồ thứ tự, không làm track trông như vừa đổi tên."""
    made = playlists.create("Chill")
    born = clock.value
    first = tracks.add(make_track(source_id="aaa"))
    second = tracks.add(make_track(source_id="bbb"))
    playlists.add_track(made.id, first.id)
    playlists.add_track(made.id, second.id)

    clock.tick()
    playlists.reorder_tracks(made.id, [second.id, first.id])
    row = _row(conn, made.id)

    assert row["order_updated_at"] == clock.value
    assert row["updated_at"] == born


# --- Đồng hồ chung của thanh bên -------------------------------------------


def test_reorder_playlists_bumps_shared_clock_not_each_playlist(
    conn: sqlite3.Connection, playlists: PlaylistRepository, clock: FakeClock
) -> None:
    """Kéo thả thanh bên KHÔNG được làm mọi track 'mới hơn' — nó sẽ nuốt cú đổi tên bên máy kia."""
    one = playlists.create("A")
    two = playlists.create("B")
    born = clock.value
    assert sync_clock.playlist_order_updated_at(conn) == 0

    clock.tick()
    playlists.reorder_playlists([two.id, one.id])

    assert sync_clock.playlist_order_updated_at(conn) == clock.value
    assert _row(conn, one.id)["updated_at"] == born
    assert _row(conn, two.id)["updated_at"] == born


def test_playlist_order_clock_survives_garbage(conn: sqlite3.Connection) -> None:
    """Giá trị hỏng đọc ra 0 (nhường máy kia), không nổ."""
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, 'rác')", (sync_clock.PLAYLIST_ORDER_KEY,)
    )
    assert sync_clock.playlist_order_updated_at(conn) == 0


# --- added_at của từng bài trong track --------------------------------------


def test_add_track_stamps_added_at(
    conn: sqlite3.Connection,
    tracks: TrackRepository,
    playlists: PlaylistRepository,
    clock: FakeClock,
) -> None:
    """Không có added_at thì bài mới thêm luôn thua bia mộ cũ bên máy kia."""
    made = playlists.create("Chill")
    track = tracks.add(make_track(source_id="aaa"))
    clock.tick()
    playlists.add_track(made.id, track.id)

    row = conn.execute(
        "SELECT added_at FROM playlist_items WHERE playlist_id = ? AND track_id = ?",
        (made.id, track.id),
    ).fetchone()
    assert row["added_at"] == clock.value


# --- Bia mộ -----------------------------------------------------------------


def test_remove_track_buries_the_pair(
    conn: sqlite3.Connection,
    tracks: TrackRepository,
    playlists: PlaylistRepository,
    clock: FakeClock,
) -> None:
    """Xoá không có bia mộ thì bài MỌC LẠI ở lần hoà sau."""
    made = playlists.create("Chill")
    track = tracks.add(make_track(source_id="aaa"))
    playlists.add_track(made.id, track.id)
    uuid_value = _row(conn, made.id)["uuid"]

    clock.tick()
    playlists.remove_track(made.id, track.id)

    graves = sync_clock.tombstones(conn, sync_clock.KIND_PLAYLIST_ITEM)
    assert graves == {f"{uuid_value}:aaa": clock.value}


def test_readding_a_song_clears_its_tombstone(
    conn: sqlite3.Connection,
    tracks: TrackRepository,
    playlists: PlaylistRepository,
    clock: FakeClock,
) -> None:
    """Ảnh chụp không được vừa nói 'có bài' vừa nói 'đã xoá bài'."""
    made = playlists.create("Chill")
    track = tracks.add(make_track(source_id="aaa"))
    playlists.add_track(made.id, track.id)
    clock.tick()
    playlists.remove_track(made.id, track.id)
    clock.tick()
    playlists.add_track(made.id, track.id)

    assert sync_clock.tombstones(conn, sync_clock.KIND_PLAYLIST_ITEM) == {}


def test_tombstone_keeps_the_later_timestamp(conn: sqlite3.Connection) -> None:
    """Xoá → thêm lại → xoá lại: bia mộ tụt về mốc cũ là bài mọc lại."""
    sync_clock.bury(conn, sync_clock.KIND_PLAYLIST, "u1", 500)
    sync_clock.bury(conn, sync_clock.KIND_PLAYLIST, "u1", 900)
    sync_clock.bury(conn, sync_clock.KIND_PLAYLIST, "u1", 700)

    assert sync_clock.tombstones(conn, sync_clock.KIND_PLAYLIST) == {"u1": 900}


def test_songs_without_source_id_get_no_tombstone(
    conn: sqlite3.Connection,
    tracks: TrackRepository,
    playlists: PlaylistRepository,
    clock: FakeClock,
) -> None:
    """Bài nhập từ mp3 không có danh tính bền: thà bỏ qua còn hơn bịa khoá xoá nhầm bài máy kia."""
    made = playlists.create("Chill")
    track = tracks.add(make_track(source_id=None))
    playlists.add_track(made.id, track.id)
    playlists.remove_track(made.id, track.id)

    assert sync_clock.tombstones(conn, sync_clock.KIND_PLAYLIST_ITEM) == {}


def test_remove_songs_buries_only_real_members(
    conn: sqlite3.Connection,
    tracks: TrackRepository,
    playlists: PlaylistRepository,
    clock: FakeClock,
) -> None:
    """Bia mộ chỉ dựng cho bài THẬT SỰ nằm trong track đó."""
    made = playlists.create("Chill")
    inside = tracks.add(make_track(source_id="aaa"))
    outside = tracks.add(make_track(source_id="bbb"))
    playlists.add_track(made.id, inside.id)
    uuid_value = _row(conn, made.id)["uuid"]

    clock.tick()
    playlists.remove_songs(made.id, [inside.id, outside.id])

    assert sync_clock.tombstones(conn, sync_clock.KIND_PLAYLIST_ITEM) == {
        f"{uuid_value}:aaa": clock.value
    }


def test_deleting_a_playlist_buries_its_uuid(
    conn: sqlite3.Connection, playlists: PlaylistRepository, clock: FakeClock
) -> None:
    """Bia mộ khoá theo uuid, không theo id — id là số của RIÊNG máy này."""
    made = playlists.create("Chill")
    uuid_value = _row(conn, made.id)["uuid"]

    clock.tick()
    playlists.delete(made.id)

    assert sync_clock.tombstones(conn, sync_clock.KIND_PLAYLIST) == {uuid_value: clock.value}


def test_delete_with_songs_buries_its_uuid(
    conn: sqlite3.Connection,
    tracks: TrackRepository,
    playlists: PlaylistRepository,
    clock: FakeClock,
) -> None:
    """Xoá track kèm nhạc cũng phải để lại bia mộ."""
    made = playlists.create("Chill")
    track = tracks.add(make_track(source_id="aaa"))
    playlists.add_track(made.id, track.id)
    uuid_value = _row(conn, made.id)["uuid"]

    clock.tick()
    playlists.delete_with_songs(made.id)

    assert sync_clock.tombstones(conn, sync_clock.KIND_PLAYLIST) == {uuid_value: clock.value}


def test_deleting_a_song_buries_it_in_every_playlist(
    conn: sqlite3.Connection,
    tracks: TrackRepository,
    playlists: PlaylistRepository,
    clock: FakeClock,
) -> None:
    """Xoá hẳn một bài: CASCADE dọn playlist_items, nên bia mộ phải dựng trước khi xoá."""
    one = playlists.create("A")
    two = playlists.create("B")
    track = tracks.add(make_track(source_id="aaa"))
    playlists.add_track(one.id, track.id)
    playlists.add_track(two.id, track.id)
    uuid_one = _row(conn, one.id)["uuid"]
    uuid_two = _row(conn, two.id)["uuid"]

    clock.tick()
    assert tracks.delete(track.id) is True

    assert sync_clock.tombstones(conn, sync_clock.KIND_PLAYLIST_ITEM) == {
        f"{uuid_one}:aaa": clock.value,
        f"{uuid_two}:aaa": clock.value,
    }


# --- Đánh giá nghệ sĩ -------------------------------------------------------


def test_rerating_bumps_the_clock(conn: sqlite3.Connection, clock: FakeClock) -> None:
    """added_at là đồng hồ hoà; không bơm khi SỬA thì cú sửa mới nhất thua bên máy kia."""
    prefs = ArtistPrefsRepository(conn)
    prefs.set_rating("Đen", RATING_FAV)
    clock.tick()
    prefs.set_rating("Đen", RATING_VERY)

    row = conn.execute(
        "SELECT rating, added_at FROM artist_prefs WHERE name = ?", (normalise_artist("Đen"),)
    ).fetchone()
    assert row is not None
    assert row["rating"] == RATING_VERY
    assert row["added_at"] == clock.value


def test_clearing_a_rating_buries_it_and_rerating_revives(
    conn: sqlite3.Connection, clock: FakeClock
) -> None:
    """Bỏ đánh giá phải để lại bia mộ; đánh giá lại thì bia mộ đi."""
    prefs = ArtistPrefsRepository(conn)
    prefs.set_rating("Đen", RATING_VERY)
    clock.tick()
    assert prefs.clear("Đen") is True
    assert sync_clock.tombstones(conn, sync_clock.KIND_ARTIST_PREF) == {
        normalise_artist("Đen"): clock.value
    }

    clock.tick()
    prefs.set_rating("Đen", RATING_FAV)
    assert sync_clock.tombstones(conn, sync_clock.KIND_ARTIST_PREF) == {}


def test_clearing_a_missing_rating_buries_nothing(
    conn: sqlite3.Connection, clock: FakeClock
) -> None:
    """Không có gì để xoá thì không dựng bia mộ — bia rỗng làm máy kia mất đánh giá thật."""
    prefs = ArtistPrefsRepository(conn)
    assert prefs.clear("Đen") is False
    assert sync_clock.tombstones(conn, sync_clock.KIND_ARTIST_PREF) == {}
