"""Suy luận nghệ sĩ hay nghe từ thư viện người dùng rồi tìm bài liên quan trên
YouTube để dựng trang khám phá. Thuần Python: không
Qt, không sqlite, không tự gọi mạng — `search`/`fetch_likes` được TIÊM vào
thay vì import trực tiếp `youtube_search`, để test chạy offline bằng hàm giả
và để tầng bridge tự quyết định chạy trên luồng nào (xem CLAUDE.md mục 4).
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, fields
from typing import Any, Callable, Collection, Mapping, Sequence

from .tiers import (
    TIER_FAV,
    TIER_NORMAL,
    TIER_VERY,
    ArtistTier,
    artist_tiers,
    normalise_artist,
    select_shelves,
    tier_for,
    top_artists,
)
from .youtube_search import SearchResult, rank

# Tái xuất: "ai được đề xuất" và "đề xuất bài gì" là hai câu hỏi khác nhau nên
# ở hai file, nhưng nơi dùng chỉ cần biết một cửa duy nhất là discovery.
__all__ = [
    "ArtistRow",
    "ArtistTier",
    "Recommendations",
    "TIER_FAV",
    "TIER_NORMAL",
    "TIER_VERY",
    "artist_tiers",
    "build",
    "from_payload",
    "normalise_artist",
    "pick_podium",
    "select_shelves",
    "tier_for",
    "to_payload",
    "top_artists",
]

log = logging.getLogger(__name__)

# Bóc được hạng mục cho từ ngần này trở lên thì tin bộ lọc và loại luôn những
# video chưa biết hạng mục. Dưới ngưỡng nghĩa là mạng đang bị chặn, giữ lại tất.
_STRICT_COVERAGE = 0.6

@dataclass(frozen=True, slots=True)
class ArtistRow:
    """Một hàng của trang khám phá: nghệ sĩ + các bài đề xuất đã xếp hạng."""

    artist: str
    songs: list[SearchResult]
    tier: str = TIER_NORMAL


@dataclass(frozen=True, slots=True)
class Recommendations:
    """Kết quả dựng trang khám phá: bục Most Recommend + các hàng theo nghệ sĩ."""

    podium: list[SearchResult]
    rows: list[ArtistRow]
    # False = lượt bóc hụt quá nhiều nên bộ lọc nhạc KHÔNG chạy được (xem
    # _STRICT_COVERAGE). Kết quả vẫn dùng tạm được, nhưng nơi gọi đừng cất nó
    # vào bộ đệm 24 giờ: làm thế là khoá cứng một trang đầy video linh tinh.
    filtered: bool = True


def build(
    artists: Sequence[str],
    *,
    search: Callable[..., list[SearchResult]],
    fetch_details: Callable[..., dict[str, Any]],
    per_artist: int = 8,
    exclude_ids: Collection[str] = (),
    music_only: bool = True,
    tiers: Mapping[str, str] | None = None,
) -> Recommendations:
    """Tìm bài cho từng nghệ sĩ, xếp hạng, dựng bục + các hàng.

    `fetch_details` được gộp gọi ĐÚNG MỘT LẦN cho id của TOÀN BỘ nghệ sĩ, không
    gọi rời từng nghệ sĩ: đây là pha chậm nhất của youtube_search (~1.4s MỖI
    video), gọi rời sẽ nhân số lần chờ mạng lên vô ích khi trang có nhiều hàng.

    `music_only` lọc bỏ video KHÔNG phải nhạc. Rất nhiều kênh vừa đăng bản remix
    vừa đăng vlog/tin tức, nên tìm theo tên kênh thôi là kéo về cả đống thứ
    không liên quan (đã thấy thật: hàng "InsiderForce" toàn video quân sự).
    Video bóc hụt (YouTube trả 429 lúc bị gọi dày) thì KHÔNG biết hạng mục. Xử
    lý chúng tuỳ theo lần bóc này khoẻ hay yếu: bóc được phần lớn thì tin bộ lọc
    và loại luôn những cái chưa biết; bóc hụt gần hết thì giữ lại tất, vì trang
    trắng trơn còn tệ hơn lọt vài video không phải nhạc. Xem _STRICT_COVERAGE.
    """
    exclude = set(exclude_ids)
    per_artist_results: dict[str, list[SearchResult]] = {}

    for artist in artists:
        try:
            found = search(artist, limit=per_artist * 2)
        except Exception:
            # Một nghệ sĩ lỗi mạng/parse không được làm sập cả trang khám phá.
            log.warning("Tìm bài cho nghệ sĩ %r thất bại, bỏ qua", artist, exc_info=True)
            continue
        filtered = [r for r in found if r.video_id not in exclude]
        if filtered:
            per_artist_results[artist] = filtered

    if not per_artist_results:
        return Recommendations(podium=[], rows=[], filtered=True)

    all_ids = sorted({r.video_id for songs in per_artist_results.values() for r in songs})
    try:
        details = fetch_details(all_ids)
    except Exception:
        log.warning("Bóc chi tiết %d video thất bại, xếp theo view", len(all_ids), exc_info=True)
        details = {}

    likes = {vid: d.like_count for vid, d in details.items() if d.like_count}
    known = sum(1 for d in details.values() if getattr(d, "category", ""))
    strict = bool(all_ids) and known / len(all_ids) >= _STRICT_COVERAGE

    rows: list[ArtistRow] = []
    ranked_per_artist: dict[str, list[SearchResult]] = {}
    for artist, results in per_artist_results.items():
        if music_only:
            results = [
                r for r in results
                if _is_probably_music(details.get(r.video_id), strict=strict)
            ]
            if not results:
                continue
        ranked = rank(results, likes=likes)[:per_artist]
        if ranked:
            ranked_per_artist[artist] = ranked
            rows.append(ArtistRow(
                artist=artist,
                songs=ranked,
                tier=(tiers or {}).get(artist, TIER_NORMAL),
            ))

    return Recommendations(
        podium=_pick_podium(ranked_per_artist, tiers=tiers),
        rows=rows,
        filtered=not music_only or strict,
    )


def _is_probably_music(details: Any, *, strict: bool) -> bool:
    """Biết hạng mục thì phải đúng là nhạc; chưa biết thì tuỳ `strict`.

    `strict` bật khi lần bóc vừa rồi lấy được hạng mục cho phần lớn video —
    lúc đó một video "chưa biết" gần như chắc chắn là bóc trượt lẻ tẻ, loại đi
    an toàn. Khi cả lượt bóc đều hụt (YouTube giới hạn tốc độ) thì `strict` tắt
    và không loại gì, để trang vẫn có nội dung.
    """
    category = "" if details is None else getattr(details, "category", "")
    if not category:
        return not strict
    return category == "Music"


def pick_podium(
    ranked_per_artist: dict[str, list[SearchResult]],
    *,
    tiers: Mapping[str, str] | None = None,
) -> list[SearchResult]:
    """Bục top 1/2/3 tính lại từ các hàng đã có sẵn.

    Trang khám phá ghép hàng từ hai nguồn — nghệ sĩ còn trong bộ đệm và nghệ sĩ
    vừa lấy về — nên bục phải dựng được từ kết quả đã ghép, không chỉ từ một lần
    build() duy nhất.
    """
    return _pick_podium(ranked_per_artist, tiers=tiers)


def _pick_podium(
    ranked_per_artist: dict[str, list[SearchResult]],
    *,
    tiers: Mapping[str, str] | None = None,
) -> list[SearchResult]:
    """Top 3 điểm cao nhất, ưu tiên mỗi nghệ sĩ một bài.

    Duyệt một lượt qua toàn bộ bài (đã sắp theo `score` giảm dần): bài đầu
    tiên gặp của mỗi nghệ sĩ được ưu tiên vào bục trước; bài thứ hai trở đi
    của cùng nghệ sĩ bị dồn sang `leftover` và CHỈ dùng để lấp chỗ trống nếu
    không đủ 3 nghệ sĩ khác nhau — kể cả khi chỉ có đúng một nghệ sĩ, lúc đó
    bục là 3 bài hay nhất của chính nghệ sĩ ấy.
    """
    if tiers:
        return _pick_podium_by_tier(ranked_per_artist, tiers)

    pool = [(artist, song) for artist, songs in ranked_per_artist.items() for song in songs]
    pool.sort(key=lambda item: (-item[1].score, item[1].video_id))

    podium: list[SearchResult] = []
    used_artists: set[str] = set()
    # Hai "nghệ sĩ" khác tên vẫn trả về CÙNG một video (đã thấy trên dữ liệu
    # thật: "doodle" và "doodle (slowed" cùng ra một bài, chiếm cả hạng 2 lẫn
    # hạng 3). Bục có ba chỗ thì phải là ba bài khác nhau.
    used_videos: set[str] = set()
    leftover: list[SearchResult] = []

    for artist, song in pool:
        if len(podium) >= 3:
            break
        if song.video_id in used_videos:
            continue
        if artist in used_artists:
            leftover.append(song)
            continue
        podium.append(song)
        used_artists.add(artist)
        used_videos.add(song.video_id)

    for song in leftover:
        if len(podium) >= 3:
            break
        if song.video_id in used_videos:
            continue
        podium.append(song)
        used_videos.add(song.video_id)

    return podium


def _pick_podium_by_tier(
    ranked_per_artist: dict[str, list[SearchResult]], tiers: Mapping[str, str]
) -> list[SearchResult]:
    """Hai chỗ đầu cho "rất yêu thích", chỗ thứ ba cho "yêu thích".

    Bục là nơi trang tự tin nhất, nên chỉ mức yêu thích trở lên mới được lên —
    "bình thường" (1-3 bài, rất có thể chỉ nghe thoáng qua) không bao giờ.
    Mức nào thiếu thì mức còn lại lấp chỗ, nhưng không bao giờ lấp bằng
    "bình thường": thà bục hai chỗ còn hơn bục sai tinh thần.
    """
    def pool_of(tier: str) -> list[tuple[str, SearchResult]]:
        items = [
            (artist, song)
            for artist, songs in ranked_per_artist.items()
            if tiers.get(artist) == tier
            for song in songs
        ]
        items.sort(key=lambda item: (-item[1].score, item[1].video_id))
        return items

    very, fav = pool_of(TIER_VERY), pool_of(TIER_FAV)
    podium: list[SearchResult] = []
    used_artists: set[str] = set()
    used_videos: set[str] = set()

    def take(pool: list[tuple[str, SearchResult]], wanted: int) -> None:
        # Ưu tiên mỗi nghệ sĩ một bài; hết nghệ sĩ mới lấy bài thứ hai của người cũ.
        for allow_repeat in (False, True):
            for artist, song in pool:
                if len(podium) >= wanted:
                    return
                if song.video_id in used_videos:
                    continue
                if artist in used_artists and not allow_repeat:
                    continue
                podium.append(song)
                used_artists.add(artist)
                used_videos.add(song.video_id)

    take(very, 2)
    take(fav, 3)
    take(very, 3)      # "yêu thích" không đủ thì quay lại lấy thêm ở mức trên
    return podium


_RESULT_FIELDS = {f.name for f in fields(SearchResult)}


def to_payload(songs: list[SearchResult]) -> list[dict]:
    """Chuyển sang dict thuần để tầng trên cất vào SQLite (JSON, cache 24h)."""
    return [asdict(s) for s in songs]


def from_payload(rows: list[dict]) -> list[SearchResult]:
    """Đọc lại payload đã cất. Bỏ field lạ, bỏ qua bản ghi thiếu field bắt
    buộc một cách an toàn: dữ liệu đệm cũ có thể tới từ một phiên bản
    SearchResult khác (thiếu field mới, thừa field đã bỏ)."""
    results: list[SearchResult] = []
    for row in rows:
        kwargs = {key: value for key, value in row.items() if key in _RESULT_FIELDS}
        try:
            results.append(SearchResult(**kwargs))
        except TypeError:
            log.warning("Bỏ qua bản ghi cache hỏng: %r", row)
    return results
