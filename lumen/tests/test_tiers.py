"""Mức yêu thích: bao nhiêu bài đã tải thì nghệ sĩ đó đáng được đề xuất bao nhiêu.

Luật do chủ dự án đặt: 1-3 bài = bình thường, 4-6 = yêu thích, 7+ = rất yêu
thích; trang cho tối đa 3 hàng rất-yêu-thích, 2 yêu-thích, 1 bình-thường.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lumen.core.tiers import (  # noqa: E402
    TIER_FAV,
    TIER_NORMAL,
    TIER_VERY,
    ArtistTier,
    artist_tiers,
    select_shelves,
    tier_for,
)


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (1, TIER_NORMAL), (2, TIER_NORMAL), (3, TIER_NORMAL),
        (4, TIER_FAV), (5, TIER_FAV), (6, TIER_FAV),
        (7, TIER_VERY), (20, TIER_VERY),
    ],
)
def test_tier_boundaries(count: int, expected: str) -> None:
    assert tier_for(count) == expected


def test_zero_downloads_is_still_the_lowest_tier() -> None:
    # Không xảy ra trong thực tế (không tải thì không có tên), nhưng hàm không
    # được nổ nếu ai đó gọi với 0.
    assert tier_for(0) == TIER_NORMAL


class TestArtistTiers:
    def test_counts_and_orders_by_frequency(self) -> None:
        names = ["A"] * 8 + ["B"] * 5 + ["C"]

        tiers = artist_tiers(names)

        assert [(t.artist, t.count, t.tier) for t in tiers] == [
            ("A", 8, TIER_VERY),
            ("B", 5, TIER_FAV),
            ("C", 1, TIER_NORMAL),
        ]

    def test_merges_case_variants_and_strips_channel_junk(self) -> None:
        names = ["Rick Astley", "rick astley - Topic", "RICK ASTLEY VEVO"]

        tiers = artist_tiers(names)

        assert len(tiers) == 1
        assert tiers[0].count == 3
        assert tiers[0].tier == TIER_NORMAL

    def test_blank_names_are_dropped(self) -> None:
        assert artist_tiers(["", "   ", "Topic"]) == []


class TestSelectShelves:
    def _tiers(self, spec: list[tuple[str, int]]) -> list[ArtistTier]:
        return [ArtistTier(artist=a, count=c) for a, c in spec]

    def test_caps_each_tier_at_its_limit(self) -> None:
        spec = [(f"V{i}", 10) for i in range(5)]
        spec += [(f"F{i}", 5) for i in range(4)]
        spec += [(f"N{i}", 2) for i in range(3)]

        chosen = select_shelves(self._tiers(spec))

        assert [t.artist for t in chosen] == ["V0", "V1", "V2", "F0", "F1", "N0"]

    def test_favourites_lead_when_there_is_nothing_above_them(self) -> None:
        chosen = select_shelves(self._tiers([("N", 1), ("F", 5)]))

        assert [t.artist for t in chosen] == ["F", "N"]

    def test_normal_always_comes_last(self) -> None:
        chosen = select_shelves(self._tiers([("N", 3), ("V", 9), ("F", 4)]))

        assert [t.tier for t in chosen] == [TIER_VERY, TIER_FAV, TIER_NORMAL]

    def test_only_normal_artists_still_returns_them(self) -> None:
        # Chọn hàng vẫn trả về; QUYẾT ĐỊNH "chưa đề xuất gì cả" nằm ở tầng
        # trên (DiscoveryBridge), không phải ở đây.
        chosen = select_shelves(self._tiers([("A", 1), ("B", 2), ("C", 3)]))

        assert len(chosen) == 1
        assert chosen[0].tier == TIER_NORMAL

    def test_nothing_in_nothing_out(self) -> None:
        assert select_shelves([]) == []


class TestCollaborationsCountForThePrimaryArtist:
    """YouTube Music trả cả dàn hợp tác trong MỘT chuỗi.

    Chủ dự án gặp: tải 6 bài Zachz Winner nhưng app thấy ba "nghệ sĩ" khác nhau
    ("Zachz Winner", "Zachz Winner, springs!, maxwell4k",
    "Zachz Winner, Фрози, Joyful"), mỗi người 1-3 bài, nên không ai đủ ngưỡng
    và trang khám phá không bao giờ bật lên.
    """

    def test_a_collaboration_list_counts_for_its_first_name(self) -> None:
        names = [
            "Zachz Winner",
            "Zachz Winner, springs!, maxwell4k",
            "Zachz Winner, Фрози, Joyful",
            "Zachz Winner",
        ]

        tiers = artist_tiers(names)

        assert [(t.artist, t.count) for t in tiers] == [("Zachz Winner", 4)]

    def test_feat_is_a_separator_too(self) -> None:
        assert artist_tiers(["Tia ft. Lê Thiện Hiếu"])[0].artist == "Tia"
        assert artist_tiers(["Tia feat. Ai Đó"])[0].artist == "Tia"

    def test_ampersand_and_x_stay_inside_the_name(self) -> None:
        # Chúng nằm trong tên THẬT khá nhiều — cắt là phá tên nghệ sĩ.
        assert artist_tiers(["Clovis Reyes & VDYCD"])[0].artist == "Clovis Reyes & VDYCD"
        assert artist_tiers(["øneheart x reidenshi"])[0].artist == "øneheart x reidenshi"

    def test_a_guest_does_not_become_a_favourite_on_their_own(self) -> None:
        """Đóng vai phụ trong bài của người khác không nói lên gì về gu."""
        names = ["Chinh, Khach"] * 5

        tiers = artist_tiers(names)

        assert [t.artist for t in tiers] == ["Chinh"]


class TestManualRatingsBeatTheGuess:
    """Người dùng nói thẳng bao giờ cũng đúng hơn app suy từ số lần tải."""

    def test_a_rating_overrides_the_count(self) -> None:
        # Một bài duy nhất, nhưng người dùng bảo "rất yêu thích".
        tiers = artist_tiers(["Mới Nghe"], {"Mới Nghe": TIER_VERY})

        assert tiers[0].tier == TIER_VERY
        assert tiers[0].count == 1

    def test_a_blocked_artist_disappears_entirely(self) -> None:
        names = ["Ghét"] * 9 + ["Thích"]

        tiers = artist_tiers(names, {"Ghét": None})

        assert [t.artist for t in tiers] == ["Thích"]

    def test_an_artist_can_be_rated_before_any_song_is_downloaded(self) -> None:
        # Thêm một kênh rồi mới nghe, không phải ngược lại.
        tiers = artist_tiers([], {"Chưa Tải Bài Nào": TIER_FAV})

        assert [(t.artist, t.count, t.tier) for t in tiers] == [
            ("Chưa Tải Bài Nào", 0, TIER_FAV)
        ]

    def test_unrated_artists_still_follow_the_count(self) -> None:
        names = ["Nhiều"] * 8 + ["Ít"]

        tiers = artist_tiers(names, {"Ít": TIER_VERY})

        by_name = {t.artist: t.tier for t in tiers}
        assert by_name["Nhiều"] == TIER_VERY      # 8 bài -> suy ra
        assert by_name["Ít"] == TIER_VERY         # 1 bài nhưng được đánh giá

    def test_rating_matches_regardless_of_case(self) -> None:
        tiers = artist_tiers(["Zachz Winner"], {"zachz winner": TIER_VERY})

        assert tiers[0].tier == TIER_VERY
