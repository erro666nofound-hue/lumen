"""Đánh giá nghệ sĩ do người dùng đặt tay.

App vẫn suy mức yêu thích từ số bài đã tải, nhưng suy thì hay sai — tải 5 bài
của một kênh remix không có nghĩa là thích kênh đó. Các test ở đây khoá lại
việc đánh giá tay ĐÈ LÊN phép đoán, và tên luôn được chuẩn hoá trước khi lưu.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lumen.core import db  # noqa: E402
from lumen.core.artist_prefs import (  # noqa: E402
    RATING_BLOCKED,
    RATING_FAV,
    RATING_NORMAL,
    RATING_VERY,
    ArtistPrefsRepository,
    tier_of_rating,
)
from lumen.core.tiers import TIER_FAV, TIER_NORMAL, TIER_VERY  # noqa: E402


@pytest.fixture
def prefs(tmp_path: Path) -> ArtistPrefsRepository:
    return ArtistPrefsRepository(db.connect(tmp_path / "library.db"))


class TestRatingToTier:
    def test_the_three_normal_ratings_map_onto_the_existing_tiers(self) -> None:
        assert tier_of_rating(RATING_NORMAL) == TIER_NORMAL
        assert tier_of_rating(RATING_FAV) == TIER_FAV
        assert tier_of_rating(RATING_VERY) == TIER_VERY

    def test_blocked_has_no_tier_at_all(self) -> None:
        # None = không lên trang khám phá, dù đã tải bao nhiêu bài.
        assert tier_of_rating(RATING_BLOCKED) is None


class TestStoringRatings:
    def test_set_then_read(self, prefs: ArtistPrefsRepository) -> None:
        assert prefs.set_rating("Zachz Winner", RATING_VERY) is True

        assert prefs.ratings() == {"Zachz Winner": RATING_VERY}

    def test_rating_again_replaces_it(self, prefs: ArtistPrefsRepository) -> None:
        prefs.set_rating("Cukak", RATING_FAV)
        prefs.set_rating("Cukak", RATING_BLOCKED)

        assert prefs.ratings() == {"Cukak": RATING_BLOCKED}

    def test_names_are_normalised_before_storing(self, prefs: ArtistPrefsRepository) -> None:
        # Tên nghệ sĩ suy từ nhạc cũng đã chuẩn hoá; không chuẩn hoá ở đây thì
        # "Joyful - Topic" và "Joyful" thành hai dòng không bao giờ khớp nhau.
        prefs.set_rating("Joyful - Topic", RATING_FAV)

        assert list(prefs.ratings()) == ["Joyful"]

    def test_a_collaboration_list_is_stored_under_its_primary_artist(
        self, prefs: ArtistPrefsRepository
    ) -> None:
        prefs.set_rating("Zachz Winner, springs!, maxwell4k", RATING_FAV)

        assert list(prefs.ratings()) == ["Zachz Winner"]

    def test_junk_input_is_refused(self, prefs: ArtistPrefsRepository) -> None:
        assert prefs.set_rating("", RATING_FAV) is False
        assert prefs.set_rating("   ", RATING_FAV) is False
        assert prefs.set_rating("Ai Đó", 99) is False
        assert prefs.ratings() == {}

    def test_clear_hands_the_artist_back_to_the_guess(
        self, prefs: ArtistPrefsRepository
    ) -> None:
        prefs.set_rating("Cukak", RATING_BLOCKED)

        assert prefs.clear("Cukak") is True
        assert prefs.ratings() == {}

    def test_clearing_something_unrated_is_not_an_error(
        self, prefs: ArtistPrefsRepository
    ) -> None:
        assert prefs.clear("Chua Ai Danh Gia") is False

    def test_listing_puts_the_most_loved_first(self, prefs: ArtistPrefsRepository) -> None:
        prefs.set_rating("Binh Thuong", RATING_NORMAL)
        prefs.set_rating("Rat Thich", RATING_VERY)
        prefs.set_rating("Bi Chan", RATING_BLOCKED)
        prefs.set_rating("Thich", RATING_FAV)

        assert [p.name for p in prefs.all()] == ["Rat Thich", "Thich", "Binh Thuong", "Bi Chan"]


class TestRatingsSurviveRestart:
    def test_reopening_the_database_keeps_them(self, tmp_path: Path) -> None:
        first = ArtistPrefsRepository(db.connect(tmp_path / "library.db"))
        first.set_rating("Zachz Winner", RATING_VERY)

        second = ArtistPrefsRepository(db.connect(tmp_path / "library.db"))

        assert second.ratings() == {"Zachz Winner": RATING_VERY}


class TestAvatarCache:
    @pytest.fixture
    def avatars(self, tmp_path: Path):
        from lumen.core.artist_prefs import ArtistAvatarCache

        return ArtistAvatarCache(db.connect(tmp_path / "library.db"))

    def test_put_then_read(self, avatars) -> None:
        avatars.put("Zachz Winner", "https://yt3.example/a.jpg")

        assert avatars.all() == {"Zachz Winner": "https://yt3.example/a.jpg"}

    def test_an_empty_url_still_counts_as_asked(self, avatars) -> None:
        # Đã hỏi và không có ảnh: phải nhớ, nếu không mỗi lần mở trang lại hỏi
        # lại và mỗi lần tốn ~3 giây mạng.
        avatars.put("Không Có Ảnh", "")

        assert "Không Có Ảnh" in avatars.known()
        assert avatars.all()["Không Có Ảnh"] == ""

    def test_names_are_normalised_like_everywhere_else(self, avatars) -> None:
        avatars.put("Joyful - Topic", "https://yt3.example/j.jpg")

        assert list(avatars.all()) == ["Joyful"]

    def test_putting_again_replaces_the_url(self, avatars) -> None:
        avatars.put("Cukak", "https://old")
        avatars.put("Cukak", "https://new")

        assert avatars.all()["Cukak"] == "https://new"
