"""Mục "Nhạc sĩ": ai đã tải bao nhiêu, và người dùng nghĩ sao về họ."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402

from lumen.bridge.artists_bridge import ArtistsBridge  # noqa: E402
from lumen.core import db  # noqa: E402
from lumen.core.artist_prefs import (  # noqa: E402
    RATING_BLOCKED,
    RATING_VERY,
    ArtistPrefsRepository,
)
from lumen.core.history import DownloadHistoryRepository  # noqa: E402
from lumen.core.repository import PlaylistRepository, TrackRepository  # noqa: E402
from tests.conftest import make_track  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QGuiApplication:
    return QGuiApplication.instance() or QGuiApplication([])


@pytest.fixture
def conn(tmp_path: Path):
    return db.connect(tmp_path / "library.db")


@pytest.fixture
def bridge(conn) -> ArtistsBridge:
    return ArtistsBridge(DownloadHistoryRepository(conn), ArtistPrefsRepository(conn))


def _own(conn, artist: str, count: int) -> None:
    """Đặt `count` bài của nghệ sĩ này vào một track."""
    tracks = TrackRepository(conn)
    playlists = PlaylistRepository(conn)
    playlist = playlists.create(f"t-{artist}")
    for i in range(count):
        song = tracks.add(
            make_track(title=f"{artist}{i}", artist=artist, file_path=f"/tmp/{artist}{i}.mp3")
        )
        playlists.add_track(playlist.id, song.id)


def _names(bridge: ArtistsBridge) -> list[str]:
    return [
        bridge.data(bridge.index(i, 0), ArtistsBridge.NameRole) for i in range(bridge.count)
    ]


class TestListing:
    def test_lists_artists_of_songs_currently_held(self, qapp, conn, bridge) -> None:
        _own(conn, "Zachz Winner", 3)
        _own(conn, "Cukak", 1)
        bridge.refresh()

        assert sorted(_names(bridge)) == ["Cukak", "Zachz Winner"]

    def test_song_count_is_reported(self, qapp, conn, bridge) -> None:
        _own(conn, "Zachz Winner", 5)
        bridge.refresh()

        assert bridge.data(bridge.index(0, 0), ArtistsBridge.SongCountRole) == 5

    def test_an_unrated_artist_is_marked_as_such(self, qapp, conn, bridge) -> None:
        _own(conn, "Cukak", 2)
        bridge.refresh()

        assert bridge.data(bridge.index(0, 0), ArtistsBridge.RatedRole) is False


class TestRating:
    def test_rating_sticks_and_marks_the_row(self, qapp, conn, bridge) -> None:
        _own(conn, "Cukak", 1)
        bridge.refresh()

        assert bridge.setRating("Cukak", RATING_VERY) is True

        assert bridge.data(bridge.index(0, 0), ArtistsBridge.RatingRole) == RATING_VERY
        assert bridge.data(bridge.index(0, 0), ArtistsBridge.RatedRole) is True

    def test_clearing_hands_the_artist_back_to_the_guess(self, qapp, conn, bridge) -> None:
        _own(conn, "Cukak", 1)
        bridge.setRating("Cukak", RATING_VERY)

        assert bridge.clearRating("Cukak") is True
        assert bridge.data(bridge.index(0, 0), ArtistsBridge.RatedRole) is False

    def test_a_blocked_artist_still_shows_here(self, qapp, conn, bridge) -> None:
        """Trang khám phá bỏ họ đi, nhưng mục này PHẢI hiện để còn bỏ chặn được."""
        _own(conn, "Ghét", 4)
        bridge.setRating("Ghét", RATING_BLOCKED)

        assert "Ghét" in _names(bridge)

    def test_an_artist_can_be_rated_before_owning_any_song(self, qapp, bridge) -> None:
        assert bridge.setRating("Chưa Nghe", RATING_VERY) is True

        assert _names(bridge) == ["Chưa Nghe"]

    def test_junk_rating_is_reported_not_silently_dropped(self, qapp, bridge) -> None:
        errors: list[str] = []
        bridge.errorOccurred.connect(errors.append)

        assert bridge.setRating("", RATING_VERY) is False
        assert len(errors) == 1


class TestNoDuplicateRows:
    """Chặn một nghệ sĩ từng làm họ hiện HAI dòng: một có số bài, một "chưa có bài nào"."""

    def test_blocking_keeps_exactly_one_row(self, qapp, conn, bridge) -> None:
        _own(conn, "amity", 1)
        bridge.refresh()
        assert _names(bridge) == ["amity"]

        bridge.setRating("amity", RATING_BLOCKED)

        assert _names(bridge) == ["amity"]

    def test_a_blocked_artist_keeps_its_song_count(self, qapp, conn, bridge) -> None:
        _own(conn, "amity", 3)
        bridge.setRating("amity", RATING_BLOCKED)

        assert bridge.data(bridge.index(0, 0), ArtistsBridge.SongCountRole) == 3

    def test_every_rating_leaves_one_row_each(self, qapp, conn, bridge) -> None:
        _own(conn, "A", 2)
        _own(conn, "B", 1)
        for rating in (RATING_BLOCKED, 0, 1, RATING_VERY):
            bridge.setRating("A", rating)
            assert sorted(_names(bridge)) == ["A", "B"], f"hỏng ở mức {rating}"

    def test_rows_are_ordered_by_song_count(self, qapp, conn, bridge) -> None:
        _own(conn, "Ít", 1)
        _own(conn, "Nhiều", 5)
        bridge.refresh()

        assert _names(bridge) == ["Nhiều", "Ít"]


class TestSearch:
    def test_filters_to_matching_names(self, qapp, conn, bridge) -> None:
        _own(conn, "Zachz Winner", 2)
        _own(conn, "Cukak", 1)
        bridge.refresh()

        bridge.setSearch("zach")

        assert _names(bridge) == ["Zachz Winner"]

    def test_ignores_case_and_padding(self, qapp, conn, bridge) -> None:
        _own(conn, "Cukak", 1)
        bridge.refresh()

        bridge.setSearch("  CUK ".strip())

        assert _names(bridge) == ["Cukak"]

    def test_clearing_brings_everyone_back(self, qapp, conn, bridge) -> None:
        _own(conn, "Zachz Winner", 2)
        _own(conn, "Cukak", 1)
        bridge.refresh()

        bridge.setSearch("zach")
        bridge.setSearch("")

        assert sorted(_names(bridge)) == ["Cukak", "Zachz Winner"]

    def test_typing_letter_by_letter_does_not_eat_the_list(self, qapp, conn, bridge) -> None:
        """Lọc dồn lên chính danh sách hiển thị sẽ mất dần dữ liệu qua mỗi phím."""
        _own(conn, "Cukak", 1)
        bridge.refresh()

        for typed in ("c", "cu", "cuk", "cu", "c", ""):
            bridge.setSearch(typed)

        assert _names(bridge) == ["Cukak"]

    def test_a_refresh_keeps_the_current_filter(self, qapp, conn, bridge) -> None:
        _own(conn, "Zachz Winner", 2)
        _own(conn, "Cukak", 1)
        bridge.refresh()
        bridge.setSearch("zach")

        bridge.refresh()

        assert _names(bridge) == ["Zachz Winner"]

    def test_no_match_leaves_an_empty_list(self, qapp, conn, bridge) -> None:
        _own(conn, "Cukak", 1)
        bridge.refresh()

        bridge.setSearch("nobody")

        assert bridge.count == 0


class TestNgheSiNgheNhieuNhat:
    """`topArtists` — hàng nghệ sĩ ở trang thư viện của gói Free (QĐ-010).

    Đây là thứ Free ĐƯỢC SỞ HỮU: dựng từ `core/tiers.py` + sqlite trên máy,
    không một cú gọi mạng nào. Trang khám phá (đi tìm nhạc MỚI của những người
    này) mới là phần của Pro.
    """

    def test_xep_theo_so_bai_giam_dan(self, bridge: ArtistsBridge, conn) -> None:
        _own(conn, "Ít", 2)
        _own(conn, "Nhiều", 9)
        _own(conn, "Vừa", 5)
        bridge.refresh()

        assert [a["name"] for a in bridge.topArtists] == ["Nhiều", "Vừa", "Ít"]

    def test_chi_lay_ba_nguoi_dau(self, bridge: ArtistsBridge, conn) -> None:
        for i in range(6):
            _own(conn, f"NS{i}", 10 - i)
        bridge.refresh()

        assert [a["name"] for a in bridge.topArtists] == ["NS0", "NS1", "NS2"]

    def test_thu_vien_rong_thi_hang_rong(self, bridge: ArtistsBridge) -> None:
        """Không có nhạc thì không có ai — LibraryView đổi câu mời theo cái này."""
        assert bridge.topArtists == []

    def test_mang_du_thu_cho_giao_dien_ve(self, bridge: ArtistsBridge, conn) -> None:
        _own(conn, "Sơn Tùng", 4)
        bridge.refresh()

        assert bridge.topArtists[0] == {
            "name": "Sơn Tùng", "songCount": 4, "rating": 1, "rated": False, "avatar": ""
        }

    def test_o_tim_cua_trang_nhac_si_khong_dung_toi(
        self, bridge: ArtistsBridge, conn
    ) -> None:
        """Bộ lọc của trang "Nhạc sĩ" là chuyện của trang đó.

        Đọc `_rows` thay vì `_all` thì gõ vào ô tìm ở một trang KHÁC sẽ làm hàng
        nghệ sĩ ở trang thư viện co lại — hỏng im lặng, và chỉ lộ khi người dùng
        tình cờ để lại chữ trong ô tìm.
        """
        _own(conn, "Alpha", 5)
        _own(conn, "Beta", 3)
        bridge.refresh()
        bridge.setSearch("alpha")

        assert bridge.count == 1
        assert [a["name"] for a in bridge.topArtists] == ["Alpha", "Beta"]

    def test_nghe_si_bi_chan_khong_len_hang(self, bridge: ArtistsBridge, conn) -> None:
        """Chặn ai thì đừng dí mặt người đó vào trang chính của họ."""
        _own(conn, "Ghét", 9)
        _own(conn, "Thích", 4)
        bridge.setRating("Ghét", RATING_BLOCKED)

        assert [a["name"] for a in bridge.topArtists] == ["Thích"]
