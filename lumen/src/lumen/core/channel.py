"""Ask YouTube who actually uploaded a video.

The library's `artist` column is a GUESS: it comes from splitting a video
title on " - ", which silently flips whenever a channel writes "Song - Artist"
instead of "Artist - Song". The owner's own library is full of examples
("Hikari - Clovis Reyes & VDYCD" became artist "Hikari"), and the discovery
page keys off artist names, so the guess has to be corrected.

Uses YouTube's public oEmbed endpoint rather than yt-dlp: it answers in ~0.2s
against yt-dlp's ~1.6s full extraction, and the channel name is all we need.
No Qt, no SQL -- the caller picks the thread.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger(__name__)

_OEMBED = "https://www.youtube.com/oembed"
_TIMEOUT_S = 8


def fetch_channel(video_id: str) -> str:
    """Return the uploading channel's name, or "" when it cannot be read."""
    if not video_id:
        return ""
    query = urllib.parse.urlencode(
        {"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"}
    )
    try:
        with urllib.request.urlopen(f"{_OEMBED}?{query}", timeout=_TIMEOUT_S) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        # Deleted, private, or simply offline. Not knowing is a normal outcome.
        log.debug("No channel name for %s", video_id, exc_info=True)
        return ""
    return str(payload.get("author_name") or "").strip()


def fetch_channels(video_ids: list[str], *, workers: int = 6) -> dict[str, str]:
    """Look several up at once; ids that fail are simply absent from the result."""
    if not video_ids:
        return {}
    found: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for video_id, name in zip(video_ids, pool.map(fetch_channel, video_ids)):
            if name:
                found[video_id] = name
    return found


def avatar_of_video(video_id: str) -> tuple[str, str]:
    """(tên kênh, link ảnh đại diện) suy từ MỘT video của kênh đó.

    Hai bước, vì không bước nào một mình đủ: video cho `channel_url`, còn ảnh
    đại diện chỉ có khi bóc chính trang kênh. Mỗi bước ~1-2s nên kết quả phải
    được đệm lại (xem bảng `artist_avatars`).

    Trong đống ảnh kênh trả về, phần lớn là ẢNH BÌA (rộng ~6:1). Ảnh đại diện là
    cái VUÔNG — lọc theo tỉ lệ chứ không lấy cái đầu tiên.
    """
    import yt_dlp

    video_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extractor_args": {"youtube": {"player_client": ["android_vr"]}},
    }
    try:
        with yt_dlp.YoutubeDL(video_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
    except Exception:
        log.warning("Cannot read channel of video %s", video_id, exc_info=True)
        return "", ""

    info = info or {}
    name = str(info.get("channel") or info.get("uploader") or "").strip()
    channel_url = info.get("channel_url") or info.get("uploader_url")
    if not channel_url:
        return name, ""

    channel_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "playlist_items": "1",
    }
    # Thử "/about" TRƯỚC: link kênh trần lắm khi rơi vào tab video và chỉ trả về
    # ảnh của các VIDEO (toàn 16:9), không có ảnh kênh nào. Đã đo trên một kênh
    # thật: link trần cho 4 ảnh không cái nào vuông, "/about" cho 9 ảnh trong đó
    # có ảnh đại diện 900px.
    for url in (channel_url.rstrip("/") + "/about", channel_url):
        try:
            with yt_dlp.YoutubeDL(channel_opts) as ydl:
                channel = ydl.extract_info(url, download=False) or {}
        except Exception:
            log.debug("Cannot read channel page %s", url, exc_info=True)
            continue
        found = _square_thumbnail(channel.get("thumbnails") or [])
        if found:
            return name, found
    return name, ""


def _square_thumbnail(thumbnails: list) -> str:
    """Ảnh VUÔNG lớn nhất — ảnh đại diện. Ảnh bìa kênh rộng ~6:1, phải loại."""
    best = ""
    best_size = 0
    for thumb in thumbnails:
        width, height = thumb.get("width") or 0, thumb.get("height") or 0
        if not width or not height or abs(width - height) > width * 0.1:
            continue
        if width > best_size:
            best, best_size = str(thumb.get("url") or ""), width
    return best
