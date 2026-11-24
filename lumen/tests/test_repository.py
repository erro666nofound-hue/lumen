from __future__ import annotations

import pytest

from lumen.core.errors import (
    DatabaseError,
    DuplicatePlaylistNameError,
    DuplicateTrackError,
)
from lumen.core.repository import PlaylistRepository, TrackRepository

from conftest import make_track

# --- TrackRepository -------------------------------------------------------


def test_add_assigns_id_and_added_at(tracks: TrackRepository) -> None:
    """add() fills added_at when zero and returns the track with a database id."""
    track = make_track(added_at=0)
    added = tracks.add(track)

    assert added.id is not None
    assert added.added_at > 0


def test_add_keeps_explicit_added_at(tracks: TrackRepository) -> None:
    """add() preserves a caller-supplied added_at instead of overwriting it."""
    added = tracks.add(make_track(added_at=12345))
    assert added.added_at == 12345


def test_get_returns_none_when_missing(tracks: TrackRepository) -> None:
    """get() returns None for an id that does not exist."""
    assert tracks.get(999) is None


def test_get_roundtrip(tracks: TrackRepository) -> None:
    """get() returns a track matching what was added."""
    added = tracks.add(make_track(title="Roundtrip", artist="Someone"))
    fetched = tracks.get(added.id)  # type: ignore[arg-type]
    assert fetched is not None
    assert fetched.title == "Roundtrip"
    assert fetched.artist == "Someone"


def test_same_source_id_allowed_once_per_track_folder(tracks: TrackRepository) -> None:
    """The SAME YouTube video may appear many times — once per track folder.

    Each track owns a folder, so putting one song into two tracks means two
    files and therefore two rows. Schema v2 dropped UNIQUE(source_id) for
    exactly this; file_path stays unique because the folders differ.
    """
    first = tracks.add(make_track(source_id="yt-abc", file_path="/music/Gaming/song.mp3"))
    second = tracks.add(make_track(source_id="yt-abc", file_path="/music/Study/song.mp3"))

    assert first.id != second.id
    assert {t.file_path for t in tracks.list_all()} == {
        "/music/Gaming/song.mp3",
        "/music/Study/song.mp3",
    }


def test_add_duplicate_file_path_raises(tracks: TrackRepository) -> None:
    """Adding two tracks with the same file_path raises DuplicateTrackError."""
    tracks.add(make_track(file_path="/music/same.mp3"))
    with pytest.raises(DuplicateTrackError):
        tracks.add(make_track(file_path="/music/same.mp3"))


def test_get_by_source_id(tracks: TrackRepository) -> None:
    """get_by_source_id() finds a track by its YouTube source id."""
    tracks.add(make_track(source_id="yt-xyz"))
    found = tracks.get_by_source_id("yt-xyz")
    assert found is not None
    assert found.source_id == "yt-xyz"
    assert tracks.get_by_source_id("does-not-exist") is None


def test_get_by_source_id_uu_tien_ban_co_file(tracks: TrackRepository) -> None:
    """Người gọi hỏi câu này để CHÉP file đã có — vớ phải dòng chỗ trống là chép hư không.

    Từ v9, cùng một bài có thể có cả dòng chỗ trống do đồng bộ dựng lên (chưa
    tải) lẫn bản đã tải thật, và dòng chỗ trống thường ĐỨNG TRƯỚC.
    """
    tracks.add(make_track(source_id="yt-abc", file_path=""))
    that = tracks.add(make_track(source_id="yt-abc", file_path="/music/that.mp3"))

    found = tracks.get_by_source_id("yt-abc")

    assert found is not None and found.id == that.id


def test_duong_dan_rong_khong_dung_hai_bai_vao_nhau(tracks: TrackRepository) -> None:
    """Hai bài chưa tải là hai dòng khác nhau, không phải một cú trùng khoá."""
    a = tracks.add(make_track(source_id="yt-a", file_path=""))
    b = tracks.add(make_track(source_id="yt-b", file_path=""))

    assert a.id != b.id
    assert a.file_path == "" and b.file_path == "", "rỗng đi xuống, rỗng đi lên"


def test_get_by_file_path(tracks: TrackRepository) -> None:
    """get_by_file_path() finds a track by its absolute path."""
    tracks.add(make_track(file_path="/music/special.mp3"))
    found = tracks.get_by_file_path("/music/special.mp3")
    assert found is not None
    assert tracks.get_by_file_path("/music/missing.mp3") is None


def test_list_all_invalid_order_raises(tracks: TrackRepository) -> None:
    """list_all() rejects an unknown order value."""
    with pytest.raises(ValueError):
        tracks.list_all(order="not_a_real_order")


def test_list_all_added_desc_and_asc(tracks: TrackRepository) -> None:
    """list_all() orders by added_at correctly in both directions."""
    tracks.add(make_track(title="First", added_at=100))
    tracks.add(make_track(title="Second", added_at=200))

    desc = tracks.list_all(order="added_desc")
    assert [t.title for t in desc] == ["Second", "First"]

    asc = tracks.list_all(order="added_asc")
    assert [t.title for t in asc] == ["First", "Second"]


def test_list_all_title_and_artist_order(tracks: TrackRepository) -> None:
    """list_all() orders case-insensitively by title and by artist."""
    tracks.add(make_track(title="banana", artist="zeta"))
    tracks.add(make_track(title="Apple", artist="Alpha"))

    by_title = tracks.list_all(order="title")
    assert [t.title for t in by_title] == ["Apple", "banana"]

    by_artist = tracks.list_all(order="artist")
    assert [t.artist for t in by_artist] == ["Alpha", "zeta"]


def test_list_all_most_played_order(tracks: TrackRepository) -> None:
    """list_all() orders by play_count descending for 'most_played'."""
    low = tracks.add(make_track(title="Low"))
    high = tracks.add(make_track(title="High"))
    tracks.record_play(low.id)  # type: ignore[arg-type]
    tracks.record_play(high.id)  # type: ignore[arg-type]
    tracks.record_play(high.id)  # type: ignore[arg-type]

    ordered = tracks.list_all(order="most_played")
    assert [t.title for t in ordered] == ["High", "Low"]


def test_list_all_search_case_and_diacritics(tracks: TrackRepository) -> None:
    """search matches case-insensitively and preserves diacritics correctly."""
    tracks.add(make_track(title="Đường Về Nhà", artist="Various"))
    tracks.add(make_track(title="Unrelated Song", artist="Other"))

    by_lower = tracks.list_all(search="đường")
    assert len(by_lower) == 1
    assert by_lower[0].title == "Đường Về Nhà"

    by_upper = tracks.list_all(search="NHÀ")
    assert len(by_upper) == 1

    by_artist_search = tracks.list_all(search="var")
    assert len(by_artist_search) == 1

    assert tracks.list_all(search="no-such-thing") == []


def test_delete_track(tracks: TrackRepository) -> None:
    """delete() removes a track and reports success/failure correctly."""
    added = tracks.add(make_track())
    assert tracks.delete(added.id) is True  # type: ignore[arg-type]
    assert tracks.get(added.id) is None  # type: ignore[arg-type]
    assert tracks.delete(added.id) is False  # type: ignore[arg-type]


def test_record_play_increments_count_and_sets_timestamp(tracks: TrackRepository) -> None:
    """record_play() increments play_count and updates last_played_at."""
    added = tracks.add(make_track())
    assert added.play_count == 0
    assert added.last_played_at is None

    tracks.record_play(added.id, when=555)  # type: ignore[arg-type]
    once = tracks.get(added.id)  # type: ignore[arg-type]
    assert once is not None
    assert once.play_count == 1
    assert once.last_played_at == 555

    tracks.record_play(added.id)  # type: ignore[arg-type]
    twice = tracks.get(added.id)  # type: ignore[arg-type]
    assert twice is not None
    assert twice.play_count == 2


def test_count(tracks: TrackRepository) -> None:
    """count() reflects the number of tracks added and removed."""
    assert tracks.count() == 0
    a = tracks.add(make_track())
    tracks.add(make_track())
    assert tracks.count() == 2
    tracks.delete(a.id)  # type: ignore[arg-type]
    assert tracks.count() == 1


# --- PlaylistRepository ------------------------------------------------------


def test_create_assigns_increasing_position(playlists: PlaylistRepository) -> None:
    """create() appends new playlists after the current maximum position."""
    first = playlists.create("Gaming", icon="🎮")
    second = playlists.create("Study")

    assert first.position == 0
    assert second.position == 1
    assert first.icon == "🎮"
    assert second.icon == ""


def test_get_returns_none_when_missing(playlists: PlaylistRepository) -> None:
    """get() returns None for a playlist id that does not exist."""
    assert playlists.get(999) is None


def test_list_all_ordered_by_position_with_track_count(
    playlists: PlaylistRepository, tracks: TrackRepository
) -> None:
    """list_all() returns playlists sorted by position, each with its track_count."""
    p1 = playlists.create("Work")
    p2 = playlists.create("Study")
    t1 = tracks.add(make_track())

    playlists.add_track(p1.id, t1.id)  # type: ignore[arg-type]

    result = playlists.list_all()
    assert [p.name for p in result] == ["Work", "Study"]
    by_id = {p.id: p for p in result}
    assert by_id[p1.id].track_count == 1
    assert by_id[p2.id].track_count == 0


def test_rename_and_set_icon(playlists: PlaylistRepository) -> None:
    """rename() and set_icon() update the stored playlist fields."""
    playlist = playlists.create("Old Name")
    playlists.rename(playlist.id, "New Name")  # type: ignore[arg-type]
    playlists.set_icon(playlist.id, "🔥")  # type: ignore[arg-type]

    updated = playlists.get(playlist.id)  # type: ignore[arg-type]
    assert updated is not None
    assert updated.name == "New Name"
    assert updated.icon == "🔥"


# --- F-5 §1: hai track không được trùng tên --------------------------------


def test_create_tu_choi_ten_da_co(playlists: PlaylistRepository) -> None:
    """create() ném DuplicatePlaylistNameError khi tên đã có, và KHÔNG thêm hàng nào."""
    playlists.create("Chill")
    with pytest.raises(DuplicatePlaylistNameError):
        playlists.create("Chill")

    assert [p.name for p in playlists.list_all()] == ["Chill"]


def test_ten_khac_hoa_van_la_hai_track(playlists: PlaylistRepository) -> None:
    """So từng ký tự (QĐ-017): "Chill" và "chill" là hai tên khác nhau."""
    playlists.create("Chill")
    playlists.create("chill")

    assert sorted(p.name for p in playlists.list_all()) == ["Chill", "chill"]


def test_rename_tu_choi_ten_track_khac_dang_giu(playlists: PlaylistRepository) -> None:
    """rename() ném khi tên thuộc về một track khác, và tên cũ ở nguyên."""
    playlists.create("Chill")
    other = playlists.create("Gym")

    with pytest.raises(DuplicatePlaylistNameError):
        playlists.rename(other.id, "Chill")  # type: ignore[arg-type]

    unchanged = playlists.get(other.id)  # type: ignore[arg-type]
    assert unchanged is not None
    assert unchanged.name == "Gym"


def test_rename_ve_chinh_ten_minh_van_duoc(playlists: PlaylistRepository) -> None:
    """Đổi tên một track về đúng tên nó đang mang không phải là trùng tên."""
    playlist = playlists.create("Chill")
    playlists.rename(playlist.id, "Chill")  # type: ignore[arg-type]

    still = playlists.get(playlist.id)  # type: ignore[arg-type]
    assert still is not None
    assert still.name == "Chill"


def test_xoa_roi_thi_ten_do_dung_lai_duoc(playlists: PlaylistRepository) -> None:
    """Tên chỉ bị giữ bởi track còn sống — xoá track đi là dùng lại tên được."""
    playlist = playlists.create("Chill")
    playlists.delete(playlist.id)  # type: ignore[arg-type]

    reborn = playlists.create("Chill")
    assert reborn.name == "Chill"


def test_delete_playlist(playlists: PlaylistRepository) -> None:
    """delete() removes a playlist and reports success/failure correctly."""
    playlist = playlists.create("Temp")
    assert playlists.delete(playlist.id) is True  # type: ignore[arg-type]
    assert playlists.get(playlist.id) is None  # type: ignore[arg-type]
    assert playlists.delete(playlist.id) is False  # type: ignore[arg-type]


def test_add_track_duplicate_returns_false(
    playlists: PlaylistRepository, tracks: TrackRepository
) -> None:
    """add_track() returns False (without error) when the track is already in the playlist."""
    playlist = playlists.create("Mood")
    track = tracks.add(make_track())

    assert playlists.add_track(playlist.id, track.id) is True  # type: ignore[arg-type]
    assert playlists.add_track(playlist.id, track.id) is False  # type: ignore[arg-type]
    assert len(playlists.tracks(playlist.id)) == 1  # type: ignore[arg-type]


def test_remove_track(playlists: PlaylistRepository, tracks: TrackRepository) -> None:
    """remove_track() removes membership and reports success/failure correctly."""
    playlist = playlists.create("Mood")
    track = tracks.add(make_track())
    playlists.add_track(playlist.id, track.id)  # type: ignore[arg-type]

    assert playlists.remove_track(playlist.id, track.id) is True  # type: ignore[arg-type]
    assert playlists.tracks(playlist.id) == []  # type: ignore[arg-type]
    assert playlists.remove_track(playlist.id, track.id) is False  # type: ignore[arg-type]


def test_tracks_ordered_by_position(
    playlists: PlaylistRepository, tracks: TrackRepository
) -> None:
    """tracks() returns playlist members in insertion (position) order."""
    playlist = playlists.create("Mood")
    a = tracks.add(make_track(title="A"))
    b = tracks.add(make_track(title="B"))
    c = tracks.add(make_track(title="C"))
    for t in (a, b, c):
        playlists.add_track(playlist.id, t.id)  # type: ignore[arg-type]

    assert [t.title for t in playlists.tracks(playlist.id)] == ["A", "B", "C"]  # type: ignore[arg-type]


def test_reorder_tracks_keeps_correct_order(
    playlists: PlaylistRepository, tracks: TrackRepository
) -> None:
    """reorder_tracks() reassigns positions 0..n-1 matching the given order."""
    playlist = playlists.create("Mood")
    a = tracks.add(make_track(title="A"))
    b = tracks.add(make_track(title="B"))
    c = tracks.add(make_track(title="C"))
    for t in (a, b, c):
        playlists.add_track(playlist.id, t.id)  # type: ignore[arg-type]

    playlists.reorder_tracks(playlist.id, [c.id, a.id, b.id])  # type: ignore[arg-type]

    assert [t.title for t in playlists.tracks(playlist.id)] == ["C", "A", "B"]  # type: ignore[arg-type]


def test_reorder_playlists_keeps_correct_order(playlists: PlaylistRepository) -> None:
    """reorder_playlists() reassigns positions 0..n-1 matching the given order."""
    a = playlists.create("A")
    b = playlists.create("B")
    c = playlists.create("C")

    playlists.reorder_playlists([c.id, a.id, b.id])  # type: ignore[arg-type]

    assert [p.name for p in playlists.list_all()] == ["C", "A", "B"]


def test_contains(playlists: PlaylistRepository, tracks: TrackRepository) -> None:
    """contains() reports whether a track is a member of a playlist."""
    playlist = playlists.create("Mood")
    track = tracks.add(make_track())

    assert playlists.contains(playlist.id, track.id) is False  # type: ignore[arg-type]
    playlists.add_track(playlist.id, track.id)  # type: ignore[arg-type]
    assert playlists.contains(playlist.id, track.id) is True  # type: ignore[arg-type]


def test_delete_track_removes_it_from_playlists(
    playlists: PlaylistRepository, tracks: TrackRepository
) -> None:
    """Deleting a track cascades to remove it from any playlist_items rows."""
    playlist = playlists.create("Mood")
    track = tracks.add(make_track())
    playlists.add_track(playlist.id, track.id)  # type: ignore[arg-type]

    tracks.delete(track.id)  # type: ignore[arg-type]

    assert playlists.tracks(playlist.id) == []  # type: ignore[arg-type]


class TestRenamingATrack:
    """Đổi tên chỉ là đổi CHỮ HIỂN THỊ — không được đụng tới file nhạc."""

    def test_changes_the_title(self, tracks) -> None:
        song = tracks.add(make_track(title="ten cu", file_path="/tmp/a.mp3"))

        assert tracks.rename(song.id, "ten moi") is True
        assert tracks.get(song.id).title == "ten moi"

    def test_leaves_the_file_and_the_artist_alone(self, tracks) -> None:
        song = tracks.add(
            make_track(title="ten cu", artist="Zachz Winner", file_path="/tmp/a.mp3")
        )

        tracks.rename(song.id, "ten moi")

        after = tracks.get(song.id)
        assert after.artist == "Zachz Winner"
        assert after.file_path == "/tmp/a.mp3"
        assert after.cover_path == song.cover_path

    def test_trims_spaces(self, tracks) -> None:
        song = tracks.add(make_track(title="a", file_path="/tmp/a.mp3"))

        tracks.rename(song.id, "   ten moi  ")

        assert tracks.get(song.id).title == "ten moi"

    def test_an_empty_name_is_refused(self, tracks) -> None:
        """Tên rỗng thì hàng nhạc thành trống trơn, không ai biết đó là bài gì."""
        song = tracks.add(make_track(title="ten cu", file_path="/tmp/a.mp3"))

        assert tracks.rename(song.id, "   ") is False
        assert tracks.get(song.id).title == "ten cu"

    def test_renaming_a_missing_track_says_so(self, tracks) -> None:
        assert tracks.rename(9999, "gi do") is False


class TestRenameNeverStoresStrayWhitespace:
    def test_inner_runs_of_spaces_collapse(self, tracks) -> None:
        """Cắt hai đầu thôi là chưa đủ: dấu cách gõ vào GIỮA tên nằm lại vĩnh viễn."""
        song = tracks.add(make_track(title="a", file_path="/tmp/w.mp3"))

        tracks.rename(song.id, "doo     dle")

        assert tracks.get(song.id).title == "doo dle"

    def test_newlines_and_tabs_count_as_spaces_too(self, tracks) -> None:
        song = tracks.add(make_track(title="a", file_path="/tmp/w2.mp3"))

        tracks.rename(song.id, " ten\tcua\nbai ")

        assert tracks.get(song.id).title == "ten cua bai"


# --- Hai cái tên của một bài (QĐ-019, v10) -----------------------------------


class TestHaiCaiTen:
    """Tên YouTube nói và tên chủ dự án đặt sống cạnh nhau, không đè nhau."""

    def test_chua_dat_ten_rieng_thi_hien_ten_that(self, tracks: TrackRepository) -> None:
        added = tracks.add(make_track(real_name="Me at the zoo"))

        assert added.display_name == ""
        assert added.title == "Me at the zoo", "trống = rơi về tên thật"

    def test_doi_ten_chi_ghi_vao_ten_hien_thi(self, tracks: TrackRepository) -> None:
        added = tracks.add(make_track(real_name="Me at the zoo"))

        assert tracks.rename(added.id, "Bài của máy A một", when=1000) is True

        after = tracks.get(added.id)
        assert after.display_name == "Bài của máy A một"
        assert after.real_name == "Me at the zoo", "tên YouTube KHÔNG được đụng tới"
        assert after.title == "Bài của máy A một", "chỗ hiển thị lấy tên riêng"
        assert after.display_name_updated_at == 1000

    def test_ten_rong_van_bi_tu_choi(self, tracks: TrackRepository) -> None:
        added = tracks.add(make_track(real_name="Tên thật"))

        assert tracks.rename(added.id, "   ") is False
        assert tracks.get(added.id).title == "Tên thật"

    def test_khoang_trang_giua_ten_van_bi_gom(self, tracks: TrackRepository) -> None:
        added = tracks.add(make_track(real_name="x"))

        tracks.rename(added.id, "doo     dle")

        assert tracks.get(added.id).display_name == "doo dle"

    def test_hai_dong_cung_mot_bai_doi_ten_doc_lap(self, tracks: TrackRepository) -> None:
        """Cùng một bản thu chép ra hai cuốn băng — nhãn ai người nấy dán."""
        a = tracks.add(make_track(source_id="abc", real_name="Me at the zoo",
                                  file_path="/music/A/zoo.mp3"))
        b = tracks.add(make_track(source_id="abc", real_name="Me at the zoo",
                                  file_path="/music/B/zoo.mp3"))

        tracks.rename(a.id, "Tên riêng của track A")

        assert tracks.get(a.id).title == "Tên riêng của track A"
        assert tracks.get(b.id).title == "Me at the zoo", "track kia không đổi theo"

    def test_sap_theo_ten_la_sap_theo_ten_NHIN_THAY(self, tracks: TrackRepository) -> None:
        """Sắp theo tên thật thì danh sách xếp khác hẳn thứ tự người dùng đọc được."""
        zoo = tracks.add(make_track(real_name="Zoo", file_path="/music/zoo.mp3"))
        tracks.add(make_track(real_name="Beta", file_path="/music/beta.mp3"))
        tracks.rename(zoo.id, "Alpha")

        assert [t.title for t in tracks.list_all(order="title")] == ["Alpha", "Beta"]

    def test_tai_lai_lam_moi_ten_that_nhung_KHONG_dung_ten_rieng(
        self, tracks: TrackRepository
    ) -> None:
        """Đúng lỗi bắt được ở vòng F-5f: tải lại đè tên người dùng đặt.

        Dòng chỗ trống đồng bộ về mang tên tạm; chủ dự án đặt tên riêng; rồi bấm
        tải lại. Sau lần tải, tên YouTube phải mới, tên riêng phải còn nguyên.
        """
        placeholder = tracks.add(
            make_track(source_id="abc", real_name="abc", file_path="")
        )
        tracks.rename(placeholder.id, "Bài của máy A một")

        filled = tracks.attach_file(
            placeholder.id,
            make_track(real_name="Me at the zoo", file_path="/music/zoo.mp3"),
        )

        assert filled is not None
        assert filled.real_name == "Me at the zoo", "tên YouTube được làm mới"
        assert filled.display_name == "Bài của máy A một", "tên chủ dự án đặt SỐNG SÓT"
        assert filled.title == "Bài của máy A một"
        assert filled.file_path == "/music/zoo.mp3"
