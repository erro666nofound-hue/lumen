"""Tests for metadata.py -- cleaning yt-dlp titles into (title, artist) pairs.

Uses real, messy video titles instead of hand-crafted easy examples, because
the whole point of this module is to survive what uploaders actually type.
The derived artist name later feeds a recommendation lookup, so getting the
artist half right matters as much as the title half.
"""

from __future__ import annotations

import pytest

from lumen.core.metadata import (
    TrackNaming,
    clean_title,
    derive_naming,
    sanitize_filename,
)


# ---------------------------------------------------------------------------
# clean_title
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Never Gonna Give You Up (Official Video)", "Never Gonna Give You Up"),
        ("Weightless (Official Audio)", "Weightless"),
        ("Back In Black (Official 4K Video)", "Back In Black"),
        ("Some Song [Official Music Video]", "Some Song"),
        ("Some Song (Official Lyric Video)", "Some Song"),
        ("Some Song (Lyric Video)", "Some Song"),
        ("Some Song (Lyrics)", "Some Song"),
        ("Some Song (Audio)", "Some Song"),
        ("Some Song (Visualizer)", "Some Song"),
        ("Some Song [MV]", "Some Song"),
        ("Some Song (HD)", "Some Song"),
        ("Some Song (4K)", "Some Song"),
        ("Some Song (HQ)", "Some Song"),
        ("Some Song (Video Oficial)", "Some Song"),
        ("Some Song (Clip Officiel)", "Some Song"),
        ("Some Song (Full HD)", "Some Song"),
        ("Some Song (Explicit)", "Some Song"),
        ("Some Song (Free Download)", "Some Song"),
        ("Some Song (Remastered)", "Some Song"),
        ("'뚜두뚜두 (DDU-DU DDU-DU)' M/V", "뚜두뚜두 (DDU-DU DDU-DU)"),
        ("[MV] IU(아이유) _ Blueming", "IU(아이유) _ Blueming"),
    ],
)
def test_clean_title_strips_noise(raw: str, expected: str) -> None:
    assert clean_title(raw) == expected


def test_clean_title_keeps_full_album_it_is_real_information() -> None:
    assert clean_title("Greatest Hits (Full Album)") == "Greatest Hits (Full Album)"


def test_clean_title_keeps_prod_by_credit() -> None:
    assert clean_title("Money Trees (Prod. by DJ Dahi)") == "Money Trees (Prod. by DJ Dahi)"


def test_clean_title_keeps_real_parenthetical_content() -> None:
    # "(DDU-DU DDU-DU)" is the Korean title's romanization, not an annotation.
    assert clean_title("뚜두뚜두 (DDU-DU DDU-DU)") == "뚜두뚜두 (DDU-DU DDU-DU)"


def test_clean_title_strips_pipe_separated_trailing_tag() -> None:
    assert (
        clean_title("HÃY TRAO CHO ANH ft. Snoop Dogg | Official MV")
        == "HÃY TRAO CHO ANH ft. Snoop Dogg"
    )


def test_clean_title_empty_after_cleaning_falls_back_to_trimmed_raw() -> None:
    assert clean_title("(Official Video)") == "(Official Video)"


def test_clean_title_blank_input_returns_trimmed() -> None:
    assert clean_title("   ") == ""


def test_clean_title_collapses_internal_whitespace() -> None:
    assert clean_title("Song   Title   (Official Video)") == "Song Title"


# ---------------------------------------------------------------------------
# derive_naming -- real-world video titles
# ---------------------------------------------------------------------------

# --- derive_naming: tên bài = tiêu đề video, nghệ sĩ = kênh ---------------------
#
# Luật này thay cho phép tách "A - B" cũ. Phép tách sai thường xuyên và sai theo
# CẢ HAI CHIỀU vì tiêu đề YouTube là chữ tự do — mỗi lần chữa một ca lại đẻ ra
# ca khác. Nguyên tiêu đề thì đôi khi dài, nhưng luôn đúng cái người dùng thấy.


def test_title_is_the_whole_video_title() -> None:
    result = derive_naming(
        video_title="discopled - zachz winner (SLOWED + REVERB)", uploader="amity"
    )

    assert result.title == "discopled - zachz winner (SLOWED + REVERB)"
    assert result.artist == "amity"


def test_the_other_word_order_gives_the_same_shape() -> None:
    """Ca ngược lại từng làm phép tách cũ đảo tên bài với nghệ sĩ."""
    result = derive_naming(video_title="Hikari - Clovis Reyes & VDYCD", uploader="VDYCD")

    assert result.title == "Hikari - Clovis Reyes & VDYCD"
    assert result.artist == "VDYCD"


def test_channel_noise_is_stripped_from_the_artist() -> None:
    for channel, expected in (
        ("RickAstleyVEVO", "RickAstley"),   # VEVO bị cắt; khoảng trắng thì kênh vốn không có
        ("Marconi Union - Topic", "Marconi Union"),
        ("Sơn Tùng M-TP Official", "Sơn Tùng M-TP"),
    ):
        assert derive_naming(video_title="bất kỳ", uploader=channel).artist == expected


def test_title_noise_is_still_cleaned() -> None:
    result = derive_naming(
        video_title="Never Gonna Give You Up (Official Video)", uploader="RickAstleyVEVO"
    )

    assert result.title == "Never Gonna Give You Up"


def test_youtube_music_tags_win_when_present() -> None:
    """`artist`/`track` là siêu dữ liệu có cấu trúc, không phải chữ tự do."""
    result = derive_naming(
        video_title="IU(아이유) - Blueming(블루밍) M/V",
        uploader="1theK",
        yt_artist="IU",
        yt_track="Blueming",
    )

    assert result == TrackNaming(title="Blueming", artist="IU")


def test_half_a_tag_is_not_enough_to_trust_it() -> None:
    result = derive_naming(
        video_title="Some Song", uploader="Some Channel", yt_artist="IU", yt_track=""
    )

    assert result.artist == "Some Channel"


def test_no_channel_means_unknown_artist() -> None:
    assert derive_naming(video_title="Một bài nào đó").artist == "Unknown Artist"



# ---------------------------------------------------------------------------
# sanitize_filename
# ---------------------------------------------------------------------------

def test_sanitize_filename_strips_forbidden_characters() -> None:
    # The repo itself lives under a path containing ":" and ">" -- this is
    # exactly the class of character that must never survive into a filename.
    result = sanitize_filename('AC/DC: Back In Black? "Live" <2026> | *hot*.')
    assert set('/\\:*?"<>|') & set(result) == set()


def test_sanitize_filename_spaces_become_single_dash() -> None:
    assert sanitize_filename("My   Favorite   Song") == "My-Favorite-Song"


def test_sanitize_filename_does_not_end_with_dot_or_dash() -> None:
    result = sanitize_filename("Weird Name...")
    assert not result.endswith(".")
    assert not result.endswith("-")


def test_sanitize_filename_truncates_to_max_length() -> None:
    result = sanitize_filename("x" * 200, max_length=80)
    assert len(result) <= 80


def test_sanitize_filename_truncation_does_not_leave_trailing_separator() -> None:
    result = sanitize_filename("a" * 79 + ".mp3-junk", max_length=80)
    assert not result.endswith(".")
    assert not result.endswith("-")


def test_sanitize_filename_empty_input_returns_placeholder() -> None:
    assert sanitize_filename("") == "track"


def test_sanitize_filename_only_junk_returns_placeholder() -> None:
    assert sanitize_filename("   ...---   ") == "track"


def test_sanitize_filename_removes_control_characters() -> None:
    result = sanitize_filename("Song\x00Title\x1f")
    assert "\x00" not in result
    assert "\x1f" not in result


def test_sanitize_filename_preserves_unicode_track_names() -> None:
    result = sanitize_filename("뚜두뚜두 (DDU-DU DDU-DU)")
    assert "뚜두뚜두" in result
