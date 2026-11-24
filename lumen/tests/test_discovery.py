"""Tests for lumen.core.discovery. No network: `search`/`fetch_details` are fakes
injected into `build()`, exactly the seam the module was designed around (see
its module docstring)."""

from __future__ import annotations

import pytest

from lumen.core.discovery import (
    ArtistRow,
    Recommendations,
    build,
    from_payload,
    normalise_artist,
    pick_podium,
    to_payload,
    top_artists,
)
from lumen.core.youtube_search import SearchResult, VideoDetails


def _details(likes: int, category: str = "Music") -> VideoDetails:
    return VideoDetails(like_count=likes, category=category)


def _song(video_id: str, *, views: int = 1_000, likes: int = 0, uploader: str = "") -> SearchResult:
    return SearchResult(
        video_id=video_id,
        title=f"title-{video_id}",
        uploader=uploader,
        duration_ms=180_000,
        url=f"https://www.youtube.com/watch?v={video_id}",
        thumbnail=f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",
        view_count=views,
        like_count=likes,
    )


# --- normalise_artist --------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Rick Astley - Topic", "Rick Astley"),
        ("Rick Astley VEVO", "Rick Astley"),
        ("Rick Astley Official", "Rick Astley"),
        ("Rick Astley - Official Artist Channel", "Rick Astley"),
        ("  Rick   Astley  ", "Rick Astley"),
        ("Rick Astley - Topic - VEVO", "Rick Astley"),
        ("Rick Astley - Official Music Video", "Rick Astley"),
    ],
)
def test_normalise_artist_strips_known_junk_suffixes(raw: str, expected: str) -> None:
    assert normalise_artist(raw) == expected


def test_normalise_artist_keeps_hyphen_that_is_part_of_the_real_name() -> None:
    """'Sơn Tùng M-TP' phải giữ nguyên khi cắt ' - Topic': hậu tố rác chỉ neo ở
    TẬN CÙNG chuỗi, không được đụng vào gạch nối là một phần tên thật."""
    assert normalise_artist("Sơn Tùng M-TP - Topic") == "Sơn Tùng M-TP"


@pytest.mark.parametrize("raw", ["", "   ", "Topic", "- Topic", "VEVO", "Official"])
def test_normalise_artist_returns_empty_for_pure_junk_or_blank(raw: str) -> None:
    assert normalise_artist(raw) == ""


# --- top_artists --------------------------------------------------------------


def test_top_artists_orders_by_descending_frequency() -> None:
    names = ["A", "B", "A", "C", "A", "B"]
    assert top_artists(names, limit=10) == ["A", "B", "C"]


def test_top_artists_tie_break_is_deterministic_across_repeated_calls() -> None:
    """Hoà tần suất phải luôn ra CÙNG một thứ tự, mọi lần gọi -- không được dựa
    vào thứ tự dict/set thô vì hash có thể đổi giữa các lần chạy."""
    names = ["Zebra", "Apple", "Mango"]  # đều tần suất 1
    first = top_artists(names, limit=10)
    for _ in range(50):
        assert top_artists(names, limit=10) == first
    assert first == ["Apple", "Mango", "Zebra"]  # alphabetical (casefold) tie-break


def test_top_artists_drops_empty_names() -> None:
    names = ["A", "", "   ", "Topic", "A"]  # "" và các mục chuẩn hoá về rỗng
    assert top_artists(names, limit=10) == ["A"]


def test_top_artists_merges_case_insensitively() -> None:
    names = ["Daft Punk", "Daft Punk", "daft punk", "DAFT PUNK", "Air"]
    result = top_artists(names, limit=10)
    # 4 biến thể hoa/thường của "Daft Punk" phải gộp thành 1 nghệ sĩ, đứng
    # trước "Air" (tần suất 1) vì tần suất gộp là 4; dạng hiển thị là casing
    # phổ biến nhất trong các biến thể ("Daft Punk" xuất hiện 2 lần).
    assert result == ["Daft Punk", "Air"]


def test_top_artists_display_form_is_the_most_common_casing() -> None:
    names = ["daft punk", "daft punk", "Daft Punk"]
    assert top_artists(names, limit=10) == ["daft punk"]


def test_top_artists_respects_limit() -> None:
    names = ["A", "B", "C", "D"]
    assert top_artists(names, limit=2) == ["A", "B"]


# --- build: fault isolation per artist ----------------------------------------


def test_build_one_failing_artist_does_not_break_the_others() -> None:
    def fake_search(artist: str, *, limit: int) -> list[SearchResult]:
        if artist == "Broken":
            raise RuntimeError("network exploded")
        return [_song(f"{artist}-1", uploader=artist)]

    result = build(
        ["Broken", "Good"],
        search=fake_search,
        fetch_details=lambda ids: {},
    )

    artists_in_rows = {row.artist for row in result.rows}
    assert artists_in_rows == {"Good"}


def test_build_all_artists_failing_returns_empty_without_crashing() -> None:
    def fake_search(artist: str, *, limit: int) -> list[SearchResult]:
        raise RuntimeError("boom")

    result = build(["A", "B"], search=fake_search, fetch_details=lambda ids: {})

    assert result == Recommendations(podium=[], rows=[])


# --- build: fetch_details called exactly once, batched ---------------------------


def test_build_calls_fetch_details_exactly_once_for_all_artists_combined() -> None:
    call_count = 0
    seen_ids: list[str] = []

    def fake_search(artist: str, *, limit: int) -> list[SearchResult]:
        return [_song(f"{artist}-1", uploader=artist), _song(f"{artist}-2", uploader=artist)]

    def fake_fetch_details(ids: list[str]) -> dict:
        nonlocal call_count
        call_count += 1
        seen_ids.extend(ids)
        return {vid: _details(10) for vid in ids}

    build(["A", "B", "C"], search=fake_search, fetch_details=fake_fetch_details)

    assert call_count == 1
    assert set(seen_ids) == {"A-1", "A-2", "B-1", "B-2", "C-1", "C-2"}


def test_build_does_not_call_fetch_details_when_no_results() -> None:
    """Không nghệ sĩ nào ra bài thì không có lý do gì gọi mạng thêm."""
    call_count = 0

    def fake_fetch_details(ids: list[str]) -> dict:
        nonlocal call_count
        call_count += 1
        return {}

    build([], search=lambda artist, **kw: [], fetch_details=fake_fetch_details)

    assert call_count == 0


# --- build: exclude_ids ---------------------------------------------------------


def test_build_excludes_ids_from_rows_and_podium() -> None:
    def fake_search(artist: str, *, limit: int) -> list[SearchResult]:
        return [
            _song(f"{artist}-owned", uploader=artist, views=1_000_000, likes=900_000),
            _song(f"{artist}-new", uploader=artist, views=1_000, likes=10),
        ]

    result = build(
        ["A", "B"],
        search=fake_search,
        fetch_details=lambda ids: {vid: _details(10) for vid in ids},
        exclude_ids={"A-owned", "B-owned"},
    )

    all_row_ids = {s.video_id for row in result.rows for s in row.songs}
    podium_ids = {s.video_id for s in result.podium}

    assert "A-owned" not in all_row_ids
    assert "B-owned" not in all_row_ids
    assert "A-owned" not in podium_ids
    assert "B-owned" not in podium_ids
    assert all_row_ids == {"A-new", "B-new"}


# --- build: no empty rows -------------------------------------------------------


def test_build_drops_artists_with_zero_results_instead_of_leaving_empty_row() -> None:
    def fake_search(artist: str, *, limit: int) -> list[SearchResult]:
        if artist == "Empty":
            return []
        return [_song(f"{artist}-1", uploader=artist)]

    result = build(["Empty", "Good"], search=fake_search, fetch_details=lambda ids: {})

    assert [row.artist for row in result.rows] == ["Good"]
    for row in result.rows:
        assert row.songs  # không có hàng nào rỗng


def test_build_drops_artist_whose_only_song_is_excluded() -> None:
    def fake_search(artist: str, *, limit: int) -> list[SearchResult]:
        return [_song(f"{artist}-1", uploader=artist)]

    result = build(
        ["OnlyExcluded", "Good"],
        search=fake_search,
        fetch_details=lambda ids: {},
        exclude_ids={"OnlyExcluded-1"},
    )

    assert [row.artist for row in result.rows] == ["Good"]


# --- podium: ranked by like/view ratio, not raw view count ----------------------


def test_podium_orders_by_score_not_view_count() -> None:
    """Yêu cầu dứt khoát của chủ dự án: bục xếp theo tỉ lệ like/view, KHÔNG
    phải lượt xem thô. Dữ liệu dưới đây cho hai cách xếp ra thứ tự NGƯỢC HẲN
    nhau ở đầu/cuối, để một cú revert vô tình về view_count sẽ bị bắt ngay."""
    songs_by_artist = {
        "Alpha": _song("v1", views=10_000_000, likes=5_000),   # score ~0.000497 (thấp)
        "Beta": _song("v2", views=1_000, likes=800),             # score ~0.0157   (cao nhất)
        "Gamma": _song("v3", views=500_000, likes=100),          # score ~0.000182 (thấp nhất)
    }

    def fake_search(artist: str, *, limit: int) -> list[SearchResult]:
        return [songs_by_artist[artist]]

    def fake_fetch_details(ids: list[str]) -> dict:
        return {s.video_id: _details(s.like_count) for s in songs_by_artist.values()}

    result = build(list(songs_by_artist), search=fake_search, fetch_details=fake_fetch_details)

    podium_ids = [s.video_id for s in result.podium]
    view_order = ["v1", "v3", "v2"]  # thứ tự nếu (sai) xếp theo view_count
    score_order = ["v2", "v1", "v3"]  # thứ tự đúng, theo score (like/view)

    assert podium_ids != view_order
    assert podium_ids == score_order


# --- podium: one song per artist, except when there's only one artist -----------


def test_podium_prefers_one_song_per_artist() -> None:
    def fake_search(artist: str, *, limit: int) -> list[SearchResult]:
        # Mỗi nghệ sĩ có 2 bài điểm rất cao, để lộ nếu bục lỡ lấy 2 bài của
        # cùng một nghệ sĩ thay vì trải ra 3 nghệ sĩ khác nhau.
        return [
            _song(f"{artist}-1", uploader=artist, views=1_000, likes=900),
            _song(f"{artist}-2", uploader=artist, views=1_000, likes=890),
        ]

    result = build(
        ["A", "B", "C"],
        search=fake_search,
        fetch_details=lambda ids: {vid: _details(900 if vid.endswith("-1") else 890) for vid in ids},
    )

    podium_artists = [s.video_id.split("-")[0] for s in result.podium]
    assert len(result.podium) == 3
    assert sorted(podium_artists) == ["A", "B", "C"]


def test_podium_with_single_artist_takes_top_three_of_that_artist() -> None:
    def fake_search(artist: str, *, limit: int) -> list[SearchResult]:
        return [
            _song("s1", uploader=artist, views=1_000, likes=900),
            _song("s2", uploader=artist, views=1_000, likes=800),
            _song("s3", uploader=artist, views=1_000, likes=700),
            _song("s4", uploader=artist, views=1_000, likes=600),
        ]

    result = build(
        ["Solo"],
        search=fake_search,
        fetch_details=lambda ids: {k: _details(v) for k, v in {"s1": 900, "s2": 800, "s3": 700, "s4": 600}.items()},
    )

    assert [s.video_id for s in result.podium] == ["s1", "s2", "s3"]


# --- podium songs still show up in their artist's row ----------------------------


def test_podium_song_still_appears_in_its_artist_row() -> None:
    def fake_search(artist: str, *, limit: int) -> list[SearchResult]:
        return [_song(f"{artist}-1", uploader=artist, views=1_000, likes=900)]

    result = build(
        ["A", "B", "C"],
        search=fake_search,
        fetch_details=lambda ids: {vid: _details(900) for vid in ids},
    )

    podium_ids = {s.video_id for s in result.podium}
    assert podium_ids  # bục không rỗng
    for row in result.rows:
        row_ids = {s.video_id for s in row.songs}
        overlap = row_ids & podium_ids
        # Bài của nghệ sĩ đó nếu lọt bục thì vẫn phải còn trong hàng của nó.
        if any(vid.startswith(row.artist + "-") for vid in podium_ids):
            assert overlap


# --- pick_podium: public entry point for recomputing after merging cache+fresh --


def test_pick_podium_orders_by_score_not_view_count() -> None:
    """Bridge sẽ ghép hàng từ bộ đệm + kết quả mới rồi gọi `pick_podium()` thẳng,
    không đi qua `build()` -- nên yêu cầu 'xếp theo tỉ lệ like/view, không phải
    lượt xem' phải đúng ở CHÍNH lối vào công khai này, không chỉ bên trong build()."""
    ranked_per_artist = {
        "Alpha": [_song("v1", views=10_000_000, likes=5_000)],   # score thấp
        "Beta": [_song("v2", views=1_000, likes=800)],              # score cao nhất
        "Gamma": [_song("v3", views=500_000, likes=100)],           # score thấp nhất
    }

    podium_ids = [s.video_id for s in pick_podium(ranked_per_artist)]

    assert podium_ids == ["v2", "v1", "v3"]  # theo score, không theo view_count


def test_pick_podium_matches_the_podium_build_produces_internally() -> None:
    """`pick_podium()` phải là đúng một lối vào công khai cho cùng một thuật
    toán mà `build()` dùng nội bộ -- không phải một cài đặt song song có thể
    trôi dạt khỏi nhau theo thời gian."""

    def fake_search(artist: str, *, limit: int) -> list[SearchResult]:
        return [
            _song(f"{artist}-1", uploader=artist, views=1_000, likes=900),
            _song(f"{artist}-2", uploader=artist, views=1_000, likes=890),
        ]

    fetch_details = lambda ids: {vid: _details(900 if vid.endswith("-1") else 890) for vid in ids}  # noqa: E731

    result = build(["A", "B", "C"], search=fake_search, fetch_details=fetch_details)

    ranked_per_artist = {row.artist: row.songs for row in result.rows}
    recomputed = pick_podium(ranked_per_artist)

    assert recomputed == result.podium


def test_pick_podium_with_empty_input_returns_empty_list() -> None:
    assert pick_podium({}) == []


# --- payload round trip -----------------------------------------------------------


def test_payload_round_trip() -> None:
    songs = [
        _song("a", views=100, likes=10, uploader="Foo"),
        _song("b", views=200, likes=20, uploader="Bar"),
    ]

    assert from_payload(to_payload(songs)) == songs


def test_from_payload_tolerates_old_cache_rows_missing_new_fields() -> None:
    """Cache 24h trong SQLite chắc chắn sẽ có bản ghi từ một phiên bản
    SearchResult cũ hơn -- thiếu field mới không được làm ném lỗi."""
    old_rows = [
        {
            "video_id": "a",
            "title": "t",
            "uploader": "u",
            "duration_ms": 1000,
            "url": "https://example.com",
            "thumbnail": "https://example.com/thumb.jpg",
            # thiếu view_count, like_count (field mới hơn)
        }
    ]

    results = from_payload(old_rows)

    assert len(results) == 1
    assert results[0].video_id == "a"
    assert results[0].view_count == 0
    assert results[0].like_count == 0


def test_from_payload_skips_rows_missing_required_fields_without_raising() -> None:
    bad_rows = [{"video_id": "only-id"}]  # thiếu title, uploader... bắt buộc

    assert from_payload(bad_rows) == []


def test_from_payload_ignores_unknown_extra_fields() -> None:
    row = {
        "video_id": "a",
        "title": "t",
        "uploader": "u",
        "duration_ms": 1000,
        "url": "https://example.com",
        "thumbnail": "https://example.com/thumb.jpg",
        "view_count": 5,
        "like_count": 1,
        "some_field_removed_later": "junk",
    }

    results = from_payload([row])

    assert len(results) == 1
    assert results[0].video_id == "a"


def test_to_payload_produces_plain_dicts() -> None:
    songs = [_song("a")]
    payload = to_payload(songs)
    assert isinstance(payload, list)
    assert isinstance(payload[0], dict)
    assert payload[0]["video_id"] == "a"


# --- build: empty artist list ------------------------------------------------------


def test_build_with_empty_artist_list_returns_empty_recommendations() -> None:
    result = build([], search=lambda artist, **kw: [], fetch_details=lambda ids: {})
    assert result == Recommendations(podium=[], rows=[])


def test_podium_never_shows_the_same_video_twice() -> None:
    """Two differently-named "artists" can return the exact same video.

    Seen on the owner's real data: a mis-parsed library produced both "doodle"
    and "doodle (slowed" as artists, and the one video they share took both
    second and third place on the podium.
    """
    shared = _song("same", views=1_000_000, likes=100_000)
    other = _song("other", views=1_000_000, likes=10_000)

    podium = pick_podium({"doodle": [shared], "doodle (slowed": [shared], "third": [other]})

    assert [s.video_id for s in podium] == ["same", "other"]


# --- build: lọc nhạc khỏi video thường ------------------------------------------


def _shelf(artist: str, *videos: str):
    """A fake search that answers every artist with the same fixed ids."""
    return lambda a, **kw: [_song(v) for v in videos] if a == artist else []


def test_build_drops_videos_that_are_not_music() -> None:
    """A remix channel also posts vlogs; only the music belongs on the page.

    Seen on the owner's real page: the "InsiderForce" shelf was entirely
    military and business videos, because the search only matched the channel.
    """
    songs = {"m1": "Music", "v1": "Entertainment", "m2": "Music", "v2": "News"}

    def fake_search(artist, **kwargs):
        return [_song(v) for v in songs]

    result = build(
        ["Chan"],
        search=fake_search,
        fetch_details=lambda ids: {v: _details(100, songs[v]) for v in ids},
    )

    assert [s.video_id for s in result.rows[0].songs] == ["m1", "m2"]


def test_an_artist_with_no_music_at_all_loses_its_whole_shelf() -> None:
    def fake_search(artist, **kwargs):
        return [_song("v1"), _song("v2")]

    result = build(
        ["NotAMusician"],
        search=fake_search,
        fetch_details=lambda ids: {v: _details(100, "Entertainment") for v in ids},
    )

    assert result.rows == []
    assert result.podium == []


def test_a_totally_failed_fetch_keeps_everything_rather_than_blanking_the_page() -> None:
    """YouTube answers 429 when asked too often, and then no category is known.

    Dropping the unknowns as well would leave the user staring at an empty page
    every time the network gets strict -- worse than a few stray videos.
    """

    def fake_search(artist, **kwargs):
        return [_song("a"), _song("b")]

    result = build(
        ["Chan"],
        search=fake_search,
        fetch_details=lambda ids: {},          # nothing came back at all
    )

    assert [s.video_id for s in result.rows[0].songs] == ["a", "b"]


def test_a_mostly_successful_fetch_drops_the_few_unknowns() -> None:
    """The real symptom: one bad row survived because its category never arrived.

    When most videos DID answer, a silent one is a stray failure -- not a
    reason to relax the filter for it.
    """
    # Ít bài hơn hạn mức mỗi hàng, nếu không "mystery" bị cắt vì xếp chót chứ
    # không phải vì bộ lọc -- và test sẽ xanh kể cả khi bộ lọc hỏng.
    known = {f"m{i}": "Music" for i in range(3)}

    def fake_search(artist, **kwargs):
        return [_song(v, likes=50) for v in [*known, "mystery"]]

    result = build(
        ["Chan"],
        search=fake_search,
        fetch_details=lambda ids: {v: _details(10, known[v]) for v in ids if v in known},
    )

    assert "mystery" not in [s.video_id for s in result.rows[0].songs]


def test_music_only_can_be_turned_off() -> None:
    def fake_search(artist, **kwargs):
        return [_song("v1")]

    result = build(
        ["Chan"],
        search=fake_search,
        fetch_details=lambda ids: {"v1": _details(10, "Entertainment")},
        music_only=False,
    )

    assert [s.video_id for s in result.rows[0].songs] == ["v1"]


def test_build_reports_whether_the_filter_actually_ran() -> None:
    """Callers must be able to tell a filtered page from an unfiltered one.

    A page built while YouTube was rate-limiting is unfiltered; caching it for
    24 hours would lock in exactly the junk the filter exists to remove.
    """

    def fake_search(artist, **kwargs):
        return [_song("a"), _song("b")]

    blocked = build(["Chan"], search=fake_search, fetch_details=lambda ids: {})
    healthy = build(
        ["Chan"],
        search=fake_search,
        fetch_details=lambda ids: {v: _details(10, "Music") for v in ids},
    )

    assert blocked.filtered is False
    assert healthy.filtered is True


# --- bục theo mức yêu thích -----------------------------------------------------


def test_podium_takes_two_from_very_favourite_and_one_from_favourite() -> None:
    """Luật chủ dự án: hạng 1-2 lấy trong "rất yêu thích", hạng 3 trong "yêu thích"."""
    ranked = {
        "V1": [_song("v1", views=1000, likes=500)],
        "V2": [_song("v2", views=1000, likes=400)],
        "F1": [_song("f1", views=1000, likes=900)],   # điểm cao nhất, vẫn chỉ hạng 3
        "N1": [_song("n1", views=1000, likes=999)],   # điểm cao nhất tuyệt đối
    }
    tiers = {"V1": "very", "V2": "very", "F1": "fav", "N1": "normal"}

    podium = pick_podium(ranked, tiers=tiers)

    assert [s.video_id for s in podium] == ["v1", "v2", "f1"]


def test_normal_tier_never_reaches_the_podium() -> None:
    ranked = {
        "V1": [_song("v1", views=1000, likes=100)],
        "N1": [_song("n1", views=1000, likes=999)],
        "N2": [_song("n2", views=1000, likes=998)],
    }
    tiers = {"V1": "very", "N1": "normal", "N2": "normal"}

    podium = pick_podium(ranked, tiers=tiers)

    assert [s.video_id for s in podium] == ["v1"]     # thà bục một chỗ còn hơn sai


def test_podium_falls_back_within_the_upper_tiers() -> None:
    # Không có "yêu thích": chỗ thứ ba lấy thêm từ "rất yêu thích".
    ranked = {
        "V1": [_song("v1", views=1000, likes=500), _song("v1b", views=1000, likes=300)],
        "V2": [_song("v2", views=1000, likes=400)],
    }
    tiers = {"V1": "very", "V2": "very"}

    podium = pick_podium(ranked, tiers=tiers)

    assert [s.video_id for s in podium] == ["v1", "v2", "v1b"]


def test_build_labels_each_row_with_its_tier() -> None:
    def fake_search(artist, **kwargs):
        return [_song(f"{artist}-1")]

    result = build(
        ["V", "N"],
        search=fake_search,
        fetch_details=lambda ids: {v: _details(10, "Music") for v in ids},
        tiers={"V": "very", "N": "normal"},
    )

    assert {r.artist: r.tier for r in result.rows} == {"V": "very", "N": "normal"}
