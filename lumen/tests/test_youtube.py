"""Tests for youtube.py -- recognizing and normalizing pasted YouTube links.

Every accepted form here is a link shape that actually exists in the wild
(desktop, mobile, music.youtube.com, shortened youtu.be, shorts, embeds,
live). Every rejected form is something a user could plausibly paste that
must not be mistaken for a YouTube video.
"""

from __future__ import annotations

import pytest

from lumen.core.errors import InvalidUrlError
from lumen.core.youtube import VideoRef, is_youtube_url, parse_url

VIDEO_ID = "dQw4w9WgXcQ"
CANONICAL = f"https://www.youtube.com/watch?v={VIDEO_ID}"


# ---------------------------------------------------------------------------
# Accepted shapes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "http://youtube.com/watch?v=dQw4w9WgXcQ",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://music.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ?t=42",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "https://www.youtube.com/live/dQw4w9WgXcQ",
        "www.youtube.com/watch?v=dQw4w9WgXcQ",
        "youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf&index=3",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=90s",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&si=aBcDeF12345",
        "  https://www.youtube.com/watch?v=dQw4w9WgXcQ  ",
        "<https://www.youtube.com/watch?v=dQw4w9WgXcQ>",
    ],
)
def test_parse_url_accepts_and_normalizes(raw: str) -> None:
    ref = parse_url(raw)
    assert ref.video_id == VIDEO_ID
    assert ref.canonical_url == CANONICAL
    assert ref.is_short is False


def test_parse_url_shorts_sets_is_short() -> None:
    ref = parse_url("https://www.youtube.com/shorts/dQw4w9WgXcQ")
    assert ref.video_id == VIDEO_ID
    assert ref.canonical_url == CANONICAL
    assert ref.is_short is True


def test_parse_url_returns_video_ref_instance() -> None:
    ref = parse_url(CANONICAL)
    assert isinstance(ref, VideoRef)


def test_video_ref_is_frozen() -> None:
    ref = parse_url(CANONICAL)
    with pytest.raises(AttributeError):
        ref.video_id = "changed"  # type: ignore[misc]


def test_parse_url_extracts_id_despite_extra_params_of_every_kind() -> None:
    raw = (
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        "&list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf&index=3&t=90s&si=xyz123"
    )
    ref = parse_url(raw)
    assert ref.video_id == VIDEO_ID


# ---------------------------------------------------------------------------
# Rejected shapes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "https://vimeo.com/76979871",
        "https://soundcloud.com/artist/track",
        "https://www.facebook.com/watch/?v=123456789",
        "https://youtube.com/",
        "https://www.youtube.com/",
        "https://www.youtube.com/watch?v=short",  # id too short
        "https://www.youtube.com/watch?v=dQw4w9WgXcQextra",  # id too long
        "https://youtu.be/short",
        "not a url",
        "https://www.youtube.com/watch",  # no v= at all
        "https://www.youtube.com/channel/UCuAXFkgsw1L7xaCfnd5JJOw",
    ],
)
def test_parse_url_rejects(raw: str) -> None:
    with pytest.raises(InvalidUrlError):
        parse_url(raw)


def test_parse_url_rejects_none() -> None:
    with pytest.raises(InvalidUrlError):
        parse_url(None)  # type: ignore[arg-type]


def test_parse_url_error_has_vietnamese_user_message() -> None:
    with pytest.raises(InvalidUrlError) as excinfo:
        parse_url("https://vimeo.com/76979871")
    assert excinfo.value.user_message
    assert "YouTube" in excinfo.value.user_message


def test_is_youtube_url_true_for_valid() -> None:
    assert is_youtube_url("https://youtu.be/dQw4w9WgXcQ") is True


@pytest.mark.parametrize("raw", ["", "https://vimeo.com/1", "garbage", None])
def test_is_youtube_url_false_for_invalid_and_never_raises(raw: object) -> None:
    assert is_youtube_url(raw) is False  # type: ignore[arg-type]


def test_video_id_alphabet_is_11_chars_url_safe() -> None:
    ref = parse_url("https://youtu.be/AbC-123_XyZ")
    assert ref.video_id == "AbC-123_XyZ"
    assert len(ref.video_id) == 11
