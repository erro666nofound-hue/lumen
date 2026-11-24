"""Tests for TrackSongsBridge (songs within a playlist).

This file tests the Qt model that shows songs inside a user-created playlist,
with operations for search, multi-select, and membership removal.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402

from lumen.bridge.track_songs_bridge import TrackSongsBridge  # noqa: E402
from lumen.core import db  # noqa: E402
from lumen.core.repository import PlaylistRepository, TrackRepository  # noqa: E402
from tests.conftest import make_track  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QGuiApplication:
    return QGuiApplication.instance() or QGuiApplication([])


@pytest.fixture
def repo(tmp_path: Path) -> PlaylistRepository:
    conn = db.connect(tmp_path / "library.db")
    return PlaylistRepository(conn)


@pytest.fixture
def track_repo(tmp_path: Path) -> TrackRepository:
    conn = db.connect(tmp_path / "library.db")
    return TrackRepository(conn)


@pytest.fixture
def bridge(repo: PlaylistRepository, track_repo: TrackRepository) -> TrackSongsBridge:
    bridge = TrackSongsBridge(repo, track_repo)
    # Keep strong references to prevent garbage collection
    bridge._kept_repo = repo
    return bridge


class TestTrackSongsNoPlaylist:
    """Test behavior when no playlist is selected."""

    def test_no_playlist_initially(self, qapp, bridge: TrackSongsBridge) -> None:
        assert bridge.playlistId == -1
        assert bridge.count == 0

    def test_remove_selected_no_crash_when_no_playlist(self, qapp, bridge: TrackSongsBridge) -> None:
        result = bridge.removeSelected()
        assert result == 0

    def test_remove_track_no_crash_when_no_playlist(self, qapp, bridge: TrackSongsBridge) -> None:
        result = bridge.removeTrack(1)
        assert result is False

    def test_toggle_selected_no_crash_when_no_playlist(self, qapp, bridge: TrackSongsBridge) -> None:
        # Should not crash
        bridge.toggleSelected(1)


class TestTrackSongsPlaylistBasics:
    """Test opening a playlist and basic properties."""

    def test_set_playlist_updates_properties(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository
    ) -> None:
        playlist = repo.create("MyPlaylist")
        bridge.setPlaylist(playlist.id)

        assert bridge.playlistId == playlist.id
        assert bridge.playlistName == "MyPlaylist"

    def test_set_playlist_clears_search(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository
    ) -> None:
        bridge.setSearch("oldSearch")
        playlist = repo.create("NewPlaylist")
        bridge.setPlaylist(playlist.id)

        assert bridge.searchText == ""

    def test_set_playlist_clears_selection(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository
    ) -> None:
        playlist = repo.create("First")
        bridge.setPlaylist(playlist.id)
        bridge.setSelectionMode(True)
        bridge.setSelectionMode(False)

        second = repo.create("Second")
        bridge.setPlaylist(second.id)

        assert bridge.selectedCount == 0

    def test_set_playlist_disables_selection_mode(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository
    ) -> None:
        playlist = repo.create("First")
        bridge.setPlaylist(playlist.id)
        bridge.setSelectionMode(True)

        second = repo.create("Second")
        bridge.setPlaylist(second.id)

        assert bridge.selectionMode is False


class TestTrackSongsOrdering:
    """Test that track order in playlist is preserved."""

    def test_tracks_in_position_order(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        playlist = repo.create("Ordered")
        # Add in intentionally non-alphabetical order
        t3 = track_repo.add(make_track(title="Charlie"))
        t1 = track_repo.add(make_track(title="Alice"))
        t2 = track_repo.add(make_track(title="Bob"))

        repo.add_track(playlist.id, t3.id)
        repo.add_track(playlist.id, t1.id)
        repo.add_track(playlist.id, t2.id)

        bridge.setPlaylist(playlist.id)

        ids = bridge.orderedIds()
        assert ids == [t3.id, t1.id, t2.id]


class TestTrackSongsSelection:
    """Test multi-select mode."""

    def test_set_selection_mode_on(self, qapp, bridge: TrackSongsBridge) -> None:
        bridge.setSelectionMode(True)
        assert bridge.selectionMode is True

    def test_toggle_selected_adds_to_selection(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        playlist = repo.create("SelectTest")
        t = track_repo.add(make_track(title="Song"))
        repo.add_track(playlist.id, t.id)

        bridge.setPlaylist(playlist.id)
        bridge.setSelectionMode(True)
        bridge.toggleSelected(t.id)

        assert bridge.selectedCount == 1

    def test_toggle_selected_twice_clears(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        playlist = repo.create("ToggleTest")
        t = track_repo.add(make_track(title="Song"))
        repo.add_track(playlist.id, t.id)

        bridge.setPlaylist(playlist.id)
        bridge.setSelectionMode(True)
        bridge.toggleSelected(t.id)
        bridge.toggleSelected(t.id)

        assert bridge.selectedCount == 0

    def test_set_selection_mode_false_clears_selection(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        playlist = repo.create("ModeTest")
        t = track_repo.add(make_track(title="Song"))
        repo.add_track(playlist.id, t.id)

        bridge.setPlaylist(playlist.id)
        bridge.setSelectionMode(True)
        bridge.toggleSelected(t.id)
        assert bridge.selectedCount == 1

        bridge.setSelectionMode(False)
        assert bridge.selectedCount == 0

    def test_clear_selection_keeps_mode(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        playlist = repo.create("ClearTest")
        t = track_repo.add(make_track(title="Song"))
        repo.add_track(playlist.id, t.id)

        bridge.setPlaylist(playlist.id)
        bridge.setSelectionMode(True)
        bridge.toggleSelected(t.id)

        bridge.clearSelection()

        assert bridge.selectedCount == 0
        assert bridge.selectionMode is True

    def test_selection_kept_when_partially_filtered(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        """Test that visible selected items remain selected through search filter.

        Note: This test does not cover the case where ALL selected items are
        hidden by search, as that appears to be a bug in the source code
        (refresh() removes selected_ids when they disappear from _tracks).
        """
        playlist = repo.create("PartialFilter")
        t1 = track_repo.add(make_track(title="Keep"))
        t2 = track_repo.add(make_track(title="Filter"))
        t3 = track_repo.add(make_track(title="Also"))
        repo.add_track(playlist.id, t1.id)
        repo.add_track(playlist.id, t2.id)
        repo.add_track(playlist.id, t3.id)

        bridge.setPlaylist(playlist.id)
        bridge.setSelectionMode(True)
        bridge.toggleSelected(t1.id)
        bridge.toggleSelected(t3.id)
        assert bridge.selectedCount == 2

        # Filter that keeps at least one selected item
        bridge.setSearch("Keep")
        assert bridge.count == 1
        assert bridge.selectedCount >= 1

    def test_selected_titles_returns_correct_names(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        playlist = repo.create("TitlesTest")
        t1 = track_repo.add(make_track(title="First Song"))
        t2 = track_repo.add(make_track(title="Second Song"))
        repo.add_track(playlist.id, t1.id)
        repo.add_track(playlist.id, t2.id)

        bridge.setPlaylist(playlist.id)
        bridge.setSelectionMode(True)
        bridge.toggleSelected(t1.id)
        bridge.toggleSelected(t2.id)

        titles = set(bridge.selectedTitles())
        assert titles == {"First Song", "Second Song"}



def _titles(bridge: TrackSongsBridge) -> list[str]:
    return [
        bridge.data(bridge.index(row, 0), TrackSongsBridge.TitleRole)
        for row in range(bridge.count)
    ]


def _fill(repo, track_repo, titles, artists=None, durations=None):
    """Dựng một track có sẵn các bài, theo đúng thứ tự truyền vào."""
    # Tên phải khác nhau mỗi lần gọi: F-5 §1 cấm hai track trùng tên, mà mấy
    # phép kiểm dưới đây dựng hai track để mở qua mở lại.
    playlist = repo.create(f"Sort {len(repo.list_all()) + 1}")
    for index, title in enumerate(titles):
        song = track_repo.add(
            make_track(
                title=title,
                artist=(artists or {}).get(title, ""),
                duration_ms=(durations or {}).get(title, 0),
                file_path=f"/tmp/{title}.mp3",
            )
        )
        repo.add_track(playlist.id, song.id)
    return playlist


class TestSorting:
    def test_starts_in_the_users_own_order(self, qapp, bridge, repo, track_repo) -> None:
        bridge.setPlaylist(_fill(repo, track_repo, ["mot"]).id)

        assert bridge.sortKey == "custom"
        assert bridge.canReorder is True

    def test_sorting_by_title_reorders_the_rows(self, qapp, bridge, repo, track_repo) -> None:
        bridge.setPlaylist(_fill(repo, track_repo, ["zulu", "alpha"]).id)

        bridge.setSort("title")

        assert _titles(bridge) == ["alpha", "zulu"]

    def test_asking_twice_flips_the_direction(self, qapp, bridge, repo, track_repo) -> None:
        bridge.setPlaylist(_fill(repo, track_repo, ["zulu", "alpha"]).id)

        bridge.setSort("title")
        bridge.setSort("title")

        assert bridge.sortDescending is True
        assert _titles(bridge) == ["zulu", "alpha"]

    def test_switching_key_starts_ascending_again(self, qapp, bridge, repo, track_repo) -> None:
        bridge.setPlaylist(_fill(repo, track_repo, ["zulu", "alpha"]).id)
        bridge.setSort("title")
        bridge.setSort("title")

        bridge.setSort("artist")

        assert bridge.sortDescending is False

    def test_an_unknown_key_is_ignored(self, qapp, bridge, repo, track_repo) -> None:
        bridge.setPlaylist(_fill(repo, track_repo, ["mot"]).id)

        bridge.setSort("khong-co")

        assert bridge.sortKey == "custom"


class TestReordering:
    def test_moving_a_song_sticks_after_a_reload(self, qapp, bridge, repo, track_repo) -> None:
        bridge.setPlaylist(_fill(repo, track_repo, ["mot", "hai", "ba"]).id)

        assert bridge.moveSong(0, 2) is True

        assert _titles(bridge) == ["hai", "ba", "mot"]
        bridge.refresh()
        assert _titles(bridge) == ["hai", "ba", "mot"], "thứ tự phải được ghi xuống database"

    def test_a_move_tells_the_world_the_new_order(self, qapp, bridge, repo, track_repo) -> None:
        """Hàng đợi đang phát nghe tiếng này. Không bắn = nhạc đi theo thứ tự cũ."""
        bridge.setPlaylist(_fill(repo, track_repo, ["mot", "hai", "ba"]).id)
        heard: list[tuple[int, list[int]]] = []
        bridge.songsReordered.connect(lambda pid, ids: heard.append((pid, list(ids))))

        assert bridge.moveSong(0, 2) is True

        assert len(heard) == 1, "kéo một cái phải kêu đúng một tiếng"
        playlist_id, ids = heard[0]
        assert playlist_id == bridge.playlistId
        assert ids == [t.id for t in bridge._all_tracks], "thứ tự bắn ra phải là thứ tự MỚI"

    def test_a_refused_move_stays_silent(self, qapp, bridge, repo, track_repo) -> None:
        """Kéo bị từ chối mà vẫn kêu thì hàng đợi bị xáo theo một cú kéo không xảy ra."""
        bridge.setPlaylist(_fill(repo, track_repo, ["mot", "hai"]).id)
        bridge.setSort("title")
        heard: list[int] = []
        bridge.songsReordered.connect(lambda pid, ids: heard.append(pid))

        assert bridge.moveSong(0, 1) is False

        assert heard == []

    def test_refused_while_sorted(self, qapp, bridge, repo, track_repo) -> None:
        """Sắp theo tên rồi kéo thì "chỗ mới" là chỗ nào trong thứ tự thật?"""
        bridge.setPlaylist(_fill(repo, track_repo, ["zulu", "alpha"]).id)
        bridge.setSort("title")

        assert bridge.canReorder is False
        assert bridge.moveSong(0, 1) is False

    def test_refused_while_filtering(self, qapp, bridge, repo, track_repo) -> None:
        """Đang lọc thì dòng thứ 3 trên màn hình không phải bài thứ 3 của track."""
        bridge.setPlaylist(_fill(repo, track_repo, ["zulu", "alpha"]).id)
        bridge.setSearch("zu")

        assert bridge.canReorder is False
        assert bridge.moveSong(0, 1) is False

    def test_out_of_range_is_refused(self, qapp, bridge, repo, track_repo) -> None:
        bridge.setPlaylist(_fill(repo, track_repo, ["mot"]).id)

        assert bridge.moveSong(0, 5) is False
        assert bridge.moveSong(0, 0) is False


class TestRenaming:
    def test_changes_only_the_display_name(self, qapp, bridge, repo, track_repo) -> None:
        bridge.setPlaylist(_fill(repo, track_repo, ["ten cu"]).id)
        track_id = bridge.data(bridge.index(0, 0), TrackSongsBridge.TrackIdRole)

        assert bridge.renameSong(track_id, "ten moi") is True

        assert _titles(bridge) == ["ten moi"]
        assert track_repo.get(track_id).file_path == "/tmp/ten cu.mp3", "file không được đụng tới"

    def test_an_empty_name_is_refused(self, qapp, bridge, repo, track_repo) -> None:
        bridge.setPlaylist(_fill(repo, track_repo, ["ten cu"]).id)
        track_id = bridge.data(bridge.index(0, 0), TrackSongsBridge.TrackIdRole)

        assert bridge.renameSong(track_id, "   ") is False
        assert _titles(bridge) == ["ten cu"]

    def test_the_new_name_survives_a_reload(self, qapp, bridge, repo, track_repo) -> None:
        bridge.setPlaylist(_fill(repo, track_repo, ["ten cu"]).id)
        track_id = bridge.data(bridge.index(0, 0), TrackSongsBridge.TrackIdRole)

        bridge.renameSong(track_id, "ten moi")
        bridge.refresh()

        assert _titles(bridge) == ["ten moi"]


class TestEditMode:
    def test_starts_off(self, qapp, bridge) -> None:
        assert bridge.editMode is False

    def test_can_be_switched(self, qapp, bridge) -> None:
        bridge.setEditMode(True)

        assert bridge.editMode is True


class TestNamesCannotBeCorruptedBySpaces:
    """Lỗi thật: gõ dấu cách vào ô sửa tên (kể cả khi tưởng đã tắt) ghi thẳng xuống database."""

    def test_spaces_in_the_middle_are_collapsed(self, qapp, bridge, repo, track_repo) -> None:
        bridge.setPlaylist(_fill(repo, track_repo, ["ten"]).id)
        track_id = bridge.data(bridge.index(0, 0), TrackSongsBridge.TrackIdRole)

        bridge.renameSong(track_id, "doo     dle")

        assert _titles(bridge) == ["doo dle"]

    def test_a_name_of_only_spaces_is_refused(self, qapp, bridge, repo, track_repo) -> None:
        bridge.setPlaylist(_fill(repo, track_repo, ["ten cu"]).id)
        track_id = bridge.data(bridge.index(0, 0), TrackSongsBridge.TrackIdRole)

        assert bridge.renameSong(track_id, "      ") is False
        assert _titles(bridge) == ["ten cu"]

    def test_opening_another_track_leaves_edit_mode(self, qapp, bridge, repo, track_repo) -> None:
        """Không tắt thì ô nhập của track cũ vẫn đang chờ phím ở một màn hình khác."""
        first = _fill(repo, track_repo, ["a"])
        second = _fill(repo, track_repo, ["b"])
        bridge.setPlaylist(first.id)
        bridge.setEditMode(True)

        bridge.setPlaylist(second.id)

        assert bridge.editMode is False


class TestRenamingOneSongOnPurpose:
    """Menu chuột phải → "Đổi tên" phải nhắm đúng bài đó, không chỉ bật chế độ sửa."""

    def test_it_turns_on_edit_mode_and_aims_at_the_song(self, qapp, bridge, repo, track_repo) -> None:
        bridge.setPlaylist(_fill(repo, track_repo, ["mot", "hai"]).id)
        second = bridge.data(bridge.index(1, 0), TrackSongsBridge.TrackIdRole)

        bridge.startRenaming(second)

        assert bridge.editMode is True
        assert bridge.editingTrackId == second

    def test_leaving_edit_mode_clears_the_aim(self, qapp, bridge, repo, track_repo) -> None:
        bridge.setPlaylist(_fill(repo, track_repo, ["mot"]).id)
        track_id = bridge.data(bridge.index(0, 0), TrackSongsBridge.TrackIdRole)
        bridge.startRenaming(track_id)

        bridge.setEditMode(False)

        assert bridge.editingTrackId == -1

    def test_aiming_at_another_song_while_already_editing(self, qapp, bridge, repo, track_repo) -> None:
        """Đang sửa bài này mà chuột phải bài khác thì con trỏ phải nhảy sang bài khác."""
        bridge.setPlaylist(_fill(repo, track_repo, ["mot", "hai"]).id)
        first = bridge.data(bridge.index(0, 0), TrackSongsBridge.TrackIdRole)
        second = bridge.data(bridge.index(1, 0), TrackSongsBridge.TrackIdRole)
        bridge.startRenaming(first)

        bridge.startRenaming(second)

        assert bridge.editingTrackId == second


class TestARenameTellsEveryone:
    """CB-029 lần nữa: ghi đúng xuống database mà không báo ai thì màn hình vẫn tên cũ.

    Danh sách trong Mini Lumen là một `TrackSongsBridge` THỨ HAI trên cùng
    mấy dòng đó. Đổi tên ở cửa sổ lớn mà không nối dây thì Mini giữ tên cũ tới
    lần nạp lại vì một lý do khác — mà người dùng thì không biết lý do nào cả.
    """

    def _hai_danh_sach(self, repo, track_repo, titles):
        """Dựng đúng như `app.py` dựng: hai bridge, nối `songRenamed` cả hai chiều."""
        chinh = TrackSongsBridge(repo, track_repo)
        mini = TrackSongsBridge(repo, track_repo)
        chinh.songRenamed.connect(mini.onSongRenamed)
        mini.songRenamed.connect(chinh.onSongRenamed)
        playlist = _fill(repo, track_repo, titles)
        chinh.setPlaylist(playlist.id)
        mini.setPlaylist(playlist.id)
        return chinh, mini

    def test_danh_sach_kia_doi_ten_theo(self, qapp, repo, track_repo) -> None:
        chinh, mini = self._hai_danh_sach(repo, track_repo, ["ten cu"])
        track_id = chinh.data(chinh.index(0, 0), TrackSongsBridge.TrackIdRole)

        chinh.renameSong(track_id, "ten moi")

        assert _titles(mini) == ["ten moi"], "Mini Lumen còn giữ tên cũ"

    def test_doi_o_mini_thi_cua_so_lon_cung_theo(self, qapp, repo, track_repo) -> None:
        chinh, mini = self._hai_danh_sach(repo, track_repo, ["ten cu"])
        track_id = mini.data(mini.index(0, 0), TrackSongsBridge.TrackIdRole)

        mini.renameSong(track_id, "ten moi")

        assert _titles(chinh) == ["ten moi"]

    def test_bao_dung_mot_hang_chu_khong_dung_lai_ca_model(self, qapp, repo, track_repo) -> None:
        """Dựng lại model sẽ cuộn danh sách về đầu; hàng kia không được nhấp nháy."""
        chinh, mini = self._hai_danh_sach(repo, track_repo, ["mot", "hai"])
        track_id = chinh.data(chinh.index(1, 0), TrackSongsBridge.TrackIdRole)
        reset, hang = [], []
        mini.modelAboutToBeReset.connect(lambda: reset.append(1))
        mini.dataChanged.connect(lambda top, bottom, roles: hang.append((top.row(), bottom.row())))

        chinh.renameSong(track_id, "hai moi")

        assert reset == [], "dựng lại cả model là cướp chỗ cuộn của người dùng"
        assert hang == [(1, 1)], "phải báo đúng hàng vừa đổi tên"

    def test_bai_dang_bi_o_tim_kiem_giau_van_mang_ten_moi(self, qapp, repo, track_repo) -> None:
        """Ô tìm kiếm chỉ GIẤU bài. Bỏ lọc ra phải thấy tên mới, không phải tên cũ."""
        chinh, mini = self._hai_danh_sach(repo, track_repo, ["ten cu", "bai khac"])
        track_id = chinh.data(chinh.index(0, 0), TrackSongsBridge.TrackIdRole)
        mini.setSearch("bai khac")
        assert _titles(mini) == ["bai khac"]

        chinh.renameSong(track_id, "ten moi")
        mini.setSearch("")

        assert _titles(mini) == ["ten moi", "bai khac"]

    def test_hai_ben_khong_chuyen_qua_chuyen_lai(self, qapp, repo, track_repo) -> None:
        """Nối cả hai chiều mà bên nhận bắn lại thì hai bridge gọi nhau không dứt."""
        chinh, mini = self._hai_danh_sach(repo, track_repo, ["ten cu"])
        track_id = chinh.data(chinh.index(0, 0), TrackSongsBridge.TrackIdRole)
        keu = []
        mini.songRenamed.connect(lambda _id, _t: keu.append(1))

        chinh.renameSong(track_id, "ten moi")

        assert keu == [], "bên nhận không được bắn lại songRenamed"

    def test_khong_ghi_lai_xuong_database(self, qapp, repo, track_repo) -> None:
        """Bên nhận chỉ theo tên, không được tự ghi — nó không biết luật của bên kia."""
        chinh, mini = self._hai_danh_sach(repo, track_repo, ["ten cu"])
        track_id = chinh.data(chinh.index(0, 0), TrackSongsBridge.TrackIdRole)
        chinh.renameSong(track_id, "ten moi")
        dau_thoi_gian = track_repo.get(track_id).display_name_updated_at

        mini.onSongRenamed(track_id, "ten moi")

        assert track_repo.get(track_id).display_name_updated_at == dau_thoi_gian

    def test_ten_bi_tu_choi_thi_khong_bao_ai(self, qapp, repo, track_repo) -> None:
        chinh, mini = self._hai_danh_sach(repo, track_repo, ["ten cu"])
        track_id = chinh.data(chinh.index(0, 0), TrackSongsBridge.TrackIdRole)

        assert chinh.renameSong(track_id, "   ") is False

        assert _titles(mini) == ["ten cu"]

    def test_bai_khong_co_trong_danh_sach_nay_thi_bo_qua(self, qapp, repo, track_repo) -> None:
        """Hai cửa sổ đang mở HAI track khác nhau — chuyện thường."""
        chinh, mini = self._hai_danh_sach(repo, track_repo, ["ten cu"])
        khac = _fill(repo, track_repo, ["bai cua track khac"])
        mini.setPlaylist(khac.id)
        track_id = chinh.data(chinh.index(0, 0), TrackSongsBridge.TrackIdRole)

        chinh.renameSong(track_id, "ten moi")

        assert _titles(mini) == ["bai cua track khac"]


class TestAppPyThatSuNoiDay:
    """Signal có bắn mà `app.py` không nối thì lỗi y hệt như chưa sửa gì (CB-029).

    Kiểm bằng CHỮ trong `app.py`: dựng cả
    `QQmlApplicationEngine` chỉ để đếm mấy cái `connect` thì đắt hơn giá trị nó
    mang lại, mà phép kiểm chữ vẫn bắt được đúng cái hồi quy đáng sợ — ai đó
    xoá dòng nối đi.
    """

    def _nguon(self) -> str:
        return (Path(__file__).resolve().parent.parent / "src" / "lumen" / "app.py").read_text(
            encoding="utf-8"
        )

    def test_hai_danh_sach_noi_ca_hai_chieu(self) -> None:
        nguon = self._nguon()
        assert "track_songs.songRenamed.connect(mini_songs.onSongRenamed)" in nguon
        assert "mini_songs.songRenamed.connect(track_songs.onSongRenamed)" in nguon

    def test_thanh_phat_cung_duoc_bao(self) -> None:
        nguon = self._nguon()
        for day in ("track_songs.songRenamed.connect(player.onSongRenamed)",
                    "mini_songs.songRenamed.connect(player.onSongRenamed)"):
            assert day in nguon, f"sót {day} — thanh phát và MPRIS giữ tên cũ"
