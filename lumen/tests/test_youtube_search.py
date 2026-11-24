"""Tests for lumen.core.youtube_search. No network: yt_dlp.YoutubeDL is replaced by a fake."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import yt_dlp

from lumen.core.errors import NetworkError
from lumen.core.youtube_search import SearchResult, search


class _FakeYoutubeDL:
    """Stand-in for yt_dlp.YoutubeDL, covering the single call `search()` makes:
    ``yt_dlp.YoutubeDL(opts)`` then ``.extract_info(query, download=False)`` as a
    context manager. Behavior is set on the class before `search()` runs; the
    `fake_ydl` fixture resets everything between tests.
    """

    result: dict | None = None
    exception: Exception | None = None

    last_opts: dict | None = None
    last_query: str | None = None

    def __init__(self, opts: dict) -> None:
        self.opts = dict(opts)
        type(self).last_opts = self.opts

    def __enter__(self) -> "_FakeYoutubeDL":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def extract_info(self, url: str, download: bool = False) -> dict | None:
        type(self).last_query = url
        if self.exception is not None:
            raise self.exception
        return dict(self.result) if self.result is not None else None


def _entry(**overrides: object) -> dict:
    base = {
        "id": "dQw4w9WgXcQ",
        "title": "Rick Astley - Never Gonna Give You Up",
        "uploader": "Rick Astley",
        "channel": "Rick Astley",
        "duration": 214,
        "thumbnails": [
            {"url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/small.jpg", "height": 94},
            {"url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/large.jpg", "height": 720},
        ],
    }
    base.update(overrides)
    return base


@pytest.fixture
def fake_ydl(monkeypatch: pytest.MonkeyPatch) -> type[_FakeYoutubeDL]:
    _FakeYoutubeDL.result = None
    _FakeYoutubeDL.exception = None
    _FakeYoutubeDL.last_opts = None
    _FakeYoutubeDL.last_query = None
    monkeypatch.setattr(yt_dlp, "YoutubeDL", _FakeYoutubeDL)
    return _FakeYoutubeDL


# --- empty query --------------------------------------------------------


def test_empty_query_returns_empty_list_without_calling_ytdlp(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_cls = MagicMock()
    monkeypatch.setattr(yt_dlp, "YoutubeDL", fake_cls)

    assert search("") == []
    assert search("   ") == []

    fake_cls.assert_not_called()


# --- normal parsing -------------------------------------------------------


def test_normal_results_are_parsed(fake_ydl) -> None:
    fake_ydl.result = {"entries": [_entry()]}

    results = search("never gonna give you up")

    assert results == [
        SearchResult(
            video_id="dQw4w9WgXcQ",
            title="Rick Astley - Never Gonna Give You Up",
            uploader="Rick Astley",
            duration_ms=214_000,
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            thumbnail="https://i.ytimg.com/vi/dQw4w9WgXcQ/mqdefault.jpg",
        )
    ]


def test_search_query_becomes_ytsearch_url_with_limit(fake_ydl) -> None:
    fake_ydl.result = {"entries": []}

    search("foo bar", limit=5)

    assert fake_ydl.last_query == "ytsearch5:foo bar"


def test_default_limit_is_twelve(fake_ydl) -> None:
    fake_ydl.result = {"entries": []}

    search("foo bar")

    assert fake_ydl.last_query == "ytsearch12:foo bar"


# --- duration edge cases ---------------------------------------------------


def test_missing_duration_becomes_zero_but_entry_is_kept(fake_ydl) -> None:
    fake_ydl.result = {"entries": [_entry(duration=None)]}

    results = search("query")

    assert len(results) == 1
    assert results[0].duration_ms == 0


# --- malformed entries ------------------------------------------------------


def test_entries_missing_id_or_title_are_skipped(fake_ydl) -> None:
    fake_ydl.result = {
        "entries": [
            _entry(id=None),
            _entry(title=None),
            None,
            _entry(),
        ]
    }

    results = search("query")

    assert len(results) == 1
    assert results[0].video_id == "dQw4w9WgXcQ"


def test_thumbnail_is_derived_from_the_video_id(fake_ydl) -> None:
    """Không dùng thumbnails[] của yt-dlp nữa — nó trả ảnh hq720 nặng, đo được
    hơn 6 giây mới tải xong nên danh sách hiện ra trống ảnh. mqdefault.jpg dựng
    từ id thì luôn tồn tại và nhẹ hơn hẳn, kể cả khi yt-dlp không trả ảnh nào."""
    fake_ydl.result = {"entries": [_entry(thumbnails=[])]}

    results = search("query")

    assert results[0].thumbnail == "https://i.ytimg.com/vi/dQw4w9WgXcQ/mqdefault.jpg"


# --- uploader fallback ------------------------------------------------------


def test_missing_uploader_falls_back_to_channel(fake_ydl) -> None:
    fake_ydl.result = {"entries": [_entry(uploader=None, channel="Some Channel")]}

    results = search("query")

    assert results[0].uploader == "Some Channel"


def test_missing_both_uploader_and_channel_is_empty_string(fake_ydl) -> None:
    fake_ydl.result = {"entries": [_entry(uploader=None, channel=None)]}

    results = search("query")

    assert results[0].uploader == ""


# --- errors -----------------------------------------------------------------


def test_ytdlp_failure_raises_network_error_with_user_message(fake_ydl) -> None:
    fake_ydl.exception = yt_dlp.utils.DownloadError(
        "<urlopen error [Errno -3] Temporary failure in name resolution>"
    )

    with pytest.raises(NetworkError) as exc_info:
        search("query")

    assert exc_info.value.user_message
    assert "YouTube" in exc_info.value.user_message


def test_none_info_returns_empty_list(fake_ydl) -> None:
    fake_ydl.result = None

    assert search("query") == []


# --- opts sanity ------------------------------------------------------------


def test_opts_request_flat_extraction_for_speed(fake_ydl) -> None:
    fake_ydl.result = {"entries": []}

    search("query")

    # Without extract_flat, yt-dlp fully resolves every result (one extra
    # network round-trip per video) and a single search takes tens of seconds.
    assert fake_ydl.last_opts is not None
    assert fake_ydl.last_opts.get("extract_flat") == "in_playlist"
    assert fake_ydl.last_opts.get("skip_download") is True


# --- xếp hạng theo tỉ lệ like/view -------------------------------------------


def _scored(views: int, likes: int) -> SearchResult:
    return SearchResult(
        video_id="x", title="t", uploader="u", duration_ms=0,
        url="", thumbnail="", view_count=views, like_count=likes,
    )


def test_ratio_beats_raw_view_count() -> None:
    """Đây là cả lý do có `score`: chỉ xét lượt xem thì bài đại chúng luôn thắng."""
    loved = _scored(views=405_000_000, likes=19_000_000)   # 4.7% thích
    merely_popular = _scored(views=6_000_000_000, likes=32_000_000)  # 0.5% thích

    assert loved.score > merely_popular.score


def test_ratio_beats_raw_like_count() -> None:
    """Và chỉ xét lượt like cũng sai: bài ít view mà tỉ lệ cao vẫn phải nổi lên."""
    niche = _scored(views=2_600_000, likes=41_000)          # 1.6%
    huge = _scored(views=56_000_000, likes=494_000)         # 0.9%

    assert niche.like_count < huge.like_count
    assert niche.score > huge.score


def test_tiny_sample_cannot_top_the_list() -> None:
    """Không có giảm chấn thì 100 view / 50 like ra tỉ lệ 50% và chiếm đầu bảng."""
    fluke = _scored(views=100, likes=50)
    real = _scored(views=2_600_000, likes=41_000)

    assert fluke.score < real.score


def test_unknown_like_count_scores_zero() -> None:
    """0 nghĩa là CHƯA BIẾT (pha hai chưa về), không phải 'không ai thích'."""
    assert _scored(views=1_000_000, likes=0).score == 0.0
    assert _scored(views=0, likes=1_000).score == 0.0
