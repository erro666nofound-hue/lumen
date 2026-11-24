"""Search YouTube by free text using yt-dlp. No downloads, no Qt.

Feeds the "type a song name" flow in the download tool and the artist
discovery page. Pure lookup: this module never touches the
database and never decides what gets downloaded -- callers hand a chosen
:class:`SearchResult`'s ``url`` straight to ``Downloads.add`` (see
``bridge/download_bridge.py``), the exact same path a pasted link takes.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Sequence
from dataclasses import dataclass, replace
from typing import Any

# Import ở đầu module, giống core/downloader.py. yt-dlp dù sao cũng đã được
# nạp lúc khởi động vì downloader import nó, nên import chậm ở đây không mua
# thêm được gì; để ở đầu file thì rõ ràng hơn.
import yt_dlp

from .errors import NetworkError

log = logging.getLogger(__name__)

# Cộng vào mẫu số khi tính điểm — xem SearchResult.score.
_SCORE_SMOOTHING = 50_000

_WATCH_URL = "https://www.youtube.com/watch?v={}"


_SEARCH_ERROR_MESSAGE = "Không tìm được trên YouTube. Kiểm tra kết nối mạng."


@dataclass(frozen=True, slots=True)
class SearchResult:
    """One YouTube video returned by a text search."""

    video_id: str
    title: str
    uploader: str
    duration_ms: int
    url: str
    thumbnail: str
    view_count: int = 0
    # 0 nghĩa là CHƯA BIẾT, không phải "không ai like". Tìm kiếm dạng phẳng
    # không trả lượt like (đã đo: luôn None), phải trích đầy đủ từng video mới
    # có — xem fetch_likes().
    like_count: int = 0

    @property
    def score(self) -> float:
        """Điểm xếp hạng: tỉ lệ like/view, có giảm chấn cho video ít lượt xem.

        Chỉ xét lượt like thì video nhiều view luôn thắng; chỉ xét lượt xem thì
        video cũ nổi tiếng luôn thắng. Tỉ lệ mới nói được "bao nhiêu người xem
        thì thích", nhưng tỉ lệ trần lại thổi phồng video 100 view / 50 like,
        nên cộng hằng số làm mượt vào mẫu số: video ít view bị kéo về 0, video
        nhiều view thì hằng số này gần như không ảnh hưởng.
        """
        if self.like_count <= 0 or self.view_count <= 0:
            return 0.0
        return self.like_count / (self.view_count + _SCORE_SMOOTHING)


class _YtdlpLogger:
    """Route yt-dlp's own chatter into the app log instead of the terminal.

    Same rationale as ``downloader._YtdlpLogger``: without a logger yt-dlp
    paints its own progress output, which has no place in a GUI process.
    """

    def debug(self, msg: str) -> None:
        # yt-dlp routes both debug and info here; info lines start with "[".
        log.debug("yt-dlp(search): %s", msg.strip())

    def info(self, msg: str) -> None:
        log.debug("yt-dlp(search): %s", msg.strip())

    def warning(self, msg: str) -> None:
        log.warning("yt-dlp(search): %s", msg.strip())

    def error(self, msg: str) -> None:
        log.error("yt-dlp(search): %s", msg.strip())


def thumbnail_url(video_id: str) -> str:
    """Ảnh nhỏ cố định của YouTube cho một video.

    KHÔNG dùng `entry["thumbnails"][0]` như trước: yt-dlp trả về ảnh `hq720`
    (360x202, kèm query string dài), đã đo mất HƠN 6 GIÂY mới tải xong nên
    người dùng thấy danh sách trống ảnh. `mqdefault.jpg` là 320x180, luôn tồn
    tại, và nhẹ hơn hẳn.
    """
    return f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"


def _to_result(entry: dict[str, Any] | None) -> SearchResult | None:
    """Parse one raw yt-dlp search entry, or None if it is unusable."""
    if entry is None:
        return None
    video_id = entry.get("id")
    title = entry.get("title")
    if not video_id or not title:
        return None
    # ytsearch trả về cả KÊNH và playlist, không riêng video. Id kênh bắt đầu
    # bằng "UC" và id video luôn dài đúng 11 ký tự, nên lọc bằng hình dạng id.
    # Đã gặp thật: một id kênh lọt vào fetch_likes và yt-dlp nổ "Video
    # unavailable" giữa lúc dựng trang khám phá.
    if entry.get("ie_key") not in (None, "Youtube") or len(video_id) != 11:
        return None

    duration = entry.get("duration")
    duration_ms = int(round(duration * 1000)) if duration is not None else 0

    uploader = entry.get("uploader") or entry.get("channel") or ""

    return SearchResult(
        video_id=video_id,
        title=title,
        uploader=uploader,
        duration_ms=duration_ms,
        url=f"https://www.youtube.com/watch?v={video_id}",
        thumbnail=thumbnail_url(video_id),
        view_count=int(entry.get("view_count") or 0),
    )


def search(query: str, *, limit: int = 12) -> list[SearchResult]:
    """Search YouTube for a text query. Network call -- never on the Qt thread."""
    text = query.strip()
    if not text:
        return []

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "skip_download": True,
        # Without this, yt-dlp fully resolves EVERY result (one extra request
        # per video) before returning anything, turning one search into tens
        # of seconds. Flat mode gives us id/title/uploader/duration/thumbnail
        # straight from the search results page, which is all we render.
        "extract_flat": "in_playlist",
        "logger": _YtdlpLogger(),
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch{limit}:{text}", download=False)
    except Exception as exc:  # yt-dlp raises many undocumented exception types
        log.warning("YouTube search failed for %r: %s", text, exc)
        raise NetworkError(str(exc), user_message=_SEARCH_ERROR_MESSAGE) from exc

    if info is None:
        return []

    entries = info.get("entries") or []
    results: list[SearchResult] = []
    for entry in entries:
        result = _to_result(entry)
        if result is not None:
            results.append(result)
    return results


@dataclass(frozen=True, slots=True)
class VideoDetails:
    """Những gì chỉ lần trích ĐẦY ĐỦ mới biết được về một video."""

    like_count: int = 0
    # Hạng mục YouTube tự gán: "Music", "Entertainment", "Education"...
    # Đây là cách đáng tin duy nhất để tách nhạc khỏi video thường, vì rất
    # nhiều kênh vừa đăng bản remix vừa đăng vlog/tin tức trên cùng một kênh.
    category: str = ""

def fetch_likes(video_ids: Sequence[str], *, workers: int = 6) -> dict[str, int]:
    """Chỉ lượt like, cho nơi nào không quan tâm phần còn lại (ô tìm kiếm)."""
    return {vid: d.like_count for vid, d in fetch_details(video_ids, workers=workers).items() if d.like_count}


def fetch_details(video_ids: Sequence[str], *, workers: int = 6) -> dict[str, VideoDetails]:
    """Lấy lượt like VÀ hạng mục cho từng video. Network call -- never on the Qt thread.

    Tách khỏi search() có chủ đích, vì đây là PHA HAI chậm: tìm kiếm dạng phẳng
    xong trong ~1.5s nhưng không có lượt like, còn trích đầy đủ mất ~1.6s MỖI
    video (đo được: 6 video song song vẫn mất 7.2s vì YouTube giới hạn tốc độ).
    Chặn chờ cả 12 video là ~14s — không chấp nhận được. Nên tầng trên hiện kết
    quả ngay sau pha một rồi mới xếp lại khi pha hai về.

    Video nào lỗi thì bỏ qua, không ném: thiếu điểm của một bài không được làm
    hỏng cả danh sách.
    """
    ids = [v for v in video_ids if v]
    if not ids:
        return {}

    # Trích ĐẦY ĐỦ (không extract_flat) — đó chính là chỗ có lượt like.
    # Dựng trong hàm vì cần _YtdlpLogger, khai báo bên dưới trong file.
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "skip_download": True,
        "logger": _YtdlpLogger(),
        # Client "android_vr" trả lời nhanh hơn hẳn client mặc định (đã đo:
        # ~1.4s so với ~2.0s mỗi video) và ít bị YouTube hỏi "bạn có phải bot
        # không" khi bị gọi dồn. Trang khám phá gọi hàm này hàng chục lần một
        # lượt nên chênh lệch đó cộng lại thành hàng chục giây.
        "extractor_args": {"youtube": {"player_client": ["android_vr"]}},
    }

    def one(video_id: str) -> tuple[str, VideoDetails]:
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(_WATCH_URL.format(video_id), download=False) or {}
            categories = info.get("categories") or []
            return video_id, VideoDetails(
                like_count=int(info.get("like_count") or 0),
                category=str(categories[0]) if categories else "",
            )
        except Exception:
            log.warning("Cannot read details for %s", video_id, exc_info=True)
            return video_id, VideoDetails()

    with ThreadPoolExecutor(max_workers=min(workers, len(ids))) as pool:
        return dict(pool.map(one, ids))


def rank(results: Sequence[SearchResult], likes: dict[str, int] | None = None) -> list[SearchResult]:
    """Xếp kết quả tìm kiếm theo thứ tự tốt nhất hiện biết.

    Chưa có lượt like (pha một) thì lượt xem là tất cả những gì ta biết, xếp
    theo nó. Có lượt like rồi thì xếp theo `score` — tỉ lệ like/view có giảm
    chấn. Luật xếp hạng nằm ở `core` chứ không ở bridge: đó là nghiệp vụ, và ở
    đây thì test được bằng pytest thuần.
    """
    if not likes:
        return sorted(results, key=lambda r: -r.view_count)
    merged = [replace(r, like_count=likes.get(r.video_id, r.like_count)) for r in results]
    return sorted(merged, key=lambda r: -r.score)
