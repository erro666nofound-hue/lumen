"""Sắp xếp các bài trong một track."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lumen.core import sorting  # noqa: E402
from lumen.core.models import Track  # noqa: E402


def _track(
    title: str,
    artist: str = "",
    duration_ms: int = 0,
    added_at: int = 0,
    source_id: str | None = "vid",
) -> Track:
    """Mặc định là bài ĐÃ TẢI (có source_id).

    Bỏ `source_id` đi thì `Track.artist_label` trả về "Custom mp3" cho mọi bài
    và mọi test xếp theo nghệ sĩ sẽ so cùng một chữ — QĐ-025.
    """
    return Track(
        real_name=title,
        artist=artist,
        duration_ms=duration_ms,
        added_at=added_at,
        source_id=source_id,
    )


def _titles(tracks: list[Track]) -> list[str]:
    return [t.title for t in tracks]


class TestCustomOrder:
    def test_leaves_the_order_alone(self) -> None:
        """SQL đã trả về theo `position`, đụng vào là hỏng thứ tự người dùng tự đặt."""
        tracks = [_track("c"), _track("a"), _track("b")]

        assert _titles(sorting.sort_tracks(tracks, sorting.SORT_CUSTOM)) == ["c", "a", "b"]

    def test_descending_flips_it(self) -> None:
        tracks = [_track("c"), _track("a"), _track("b")]

        result = sorting.sort_tracks(tracks, sorting.SORT_CUSTOM, descending=True)

        assert _titles(result) == ["b", "a", "c"]

    def test_does_not_touch_the_list_it_was_given(self) -> None:
        tracks = [_track("c"), _track("a")]

        sorting.sort_tracks(tracks, sorting.SORT_TITLE)

        assert _titles(tracks) == ["c", "a"]


class TestByTitle:
    def test_alphabetical(self) -> None:
        tracks = [_track("doodle"), _track("Boogie"), _track("apple")]

        assert _titles(sorting.sort_tracks(tracks, sorting.SORT_TITLE)) == [
            "apple",
            "Boogie",
            "doodle",
        ]

    def test_case_does_not_split_the_list(self) -> None:
        """'ABBA' và 'abba' phải đứng cạnh nhau, không phải hai cụm hoa/thường."""
        tracks = [_track("abba"), _track("Beta"), _track("ABBA")]

        assert _titles(sorting.sort_tracks(tracks, sorting.SORT_TITLE))[:2] == ["abba", "ABBA"]

    def test_leading_spaces_do_not_send_a_song_to_the_top(self) -> None:
        tracks = [_track("beta"), _track("  zulu")]

        assert _titles(sorting.sort_tracks(tracks, sorting.SORT_TITLE)) == ["beta", "  zulu"]


class TestByArtistAndDuration:
    def test_artist_then_title(self) -> None:
        tracks = [
            _track("z", artist="Cukak"),
            _track("a", artist="Zachz"),
            _track("b", artist="Cukak"),
        ]

        assert _titles(sorting.sort_tracks(tracks, sorting.SORT_ARTIST)) == ["b", "z", "a"]

    def test_duration_shortest_first(self) -> None:
        tracks = [_track("dai", duration_ms=300), _track("ngan", duration_ms=100)]

        assert _titles(sorting.sort_tracks(tracks, sorting.SORT_DURATION)) == ["ngan", "dai"]

    def test_equal_durations_fall_back_to_title(self) -> None:
        """Không có khoá phụ thì hai bài bằng nhau nhảy chỗ mỗi lần sắp — nhìn như lỗi."""
        tracks = [_track("bbb", duration_ms=100), _track("aaa", duration_ms=100)]

        assert _titles(sorting.sort_tracks(tracks, sorting.SORT_DURATION)) == ["aaa", "bbb"]

    def test_added_newest_last_by_default(self) -> None:
        tracks = [_track("moi", added_at=200), _track("cu", added_at=100)]

        assert _titles(sorting.sort_tracks(tracks, sorting.SORT_ADDED)) == ["cu", "moi"]


class TestUnknownKey:
    def test_is_ignored_rather_than_crashing(self) -> None:
        tracks = [_track("c"), _track("a")]

        assert _titles(sorting.sort_tracks(tracks, "khong-co-tieu-chi-nay")) == ["c", "a"]

    def test_every_key_has_a_label(self) -> None:
        assert set(sorting.SORT_LABELS) == set(sorting.SORT_KEYS)
