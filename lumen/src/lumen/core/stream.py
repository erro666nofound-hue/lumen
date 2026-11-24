"""Resolve a YouTube video into a direct audio URL that mpv can play.

This is what "nghe thử" (preview) runs on: nothing is downloaded, nothing is
written to the library, mpv just opens the audio stream the way it opens a
local file. No Qt, no SQL -- the caller decides which thread this blocks.

Doing the resolving here rather than letting mpv's own ytdl hook do it buys
two things: the wait becomes visible to the UI (it is a few seconds), and one
failure mode -- "the video is gone" -- surfaces as a normal LumenError instead
of a silent dead player.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import yt_dlp

from lumen.core.errors import LumenError

log = logging.getLogger(__name__)

_BASE_OPTIONS = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "format": "bestaudio/best",
    "noplaylist": True,
}

# Thứ tự thử các "player client" của YouTube. ĐÃ ĐO trên máy này:
#   android_vr  12/12 yêu cầu liên tiếp thành công, ~1.4s/bài, opus audio-only
#   mặc định    12/12 nhưng ~2.0s/bài
#   web_safari  trả luồng ghép cả video, và trượt khi bị hỏi dồn
#   tv          trả format 18 (có cả video) -- phí băng thông cho việc chỉ nghe
# YouTube còn bật kiểm tra chống bot ("Sign in to confirm you're not a bot")
# khi bị hỏi dồn dập, và cú chặn đó dính theo IP chứ không theo video --
# nên khi client đầu trượt thì thử client sau, không kết luận ngay là hỏng.
_CLIENTS: tuple[dict, ...] = (
    {"extractor_args": {"youtube": {"player_client": ["android_vr"]}}},
    {},
)


@dataclass(frozen=True)
class StreamInfo:
    """One playable audio stream, plus what the player bar needs to label it."""

    url: str
    title: str
    uploader: str
    duration_ms: int
    # Ảnh bìa cho thanh phát. Là URL https chứ không phải đường dẫn trên máy --
    # nghe thử không tải gì về cả.
    thumbnail: str = ""


def resolve(video_id: str) -> StreamInfo:
    """Return a directly playable audio URL for one video id.

    Blocks on the network for a few seconds -- call it from a worker thread.
    The URL is short-lived (YouTube signs it with an expiry), so resolve right
    before playing rather than caching it.
    """
    if not video_id:
        raise LumenError("Không có video để nghe thử.")

    watch_url = f"https://www.youtube.com/watch?v={video_id}"
    info = None
    for client in _CLIENTS:
        try:
            with yt_dlp.YoutubeDL({**_BASE_OPTIONS, **client}) as ydl:
                info = ydl.extract_info(watch_url, download=False)
        except Exception as exc:                   # yt-dlp raises many shapes
            log.debug("Client %s could not resolve %s: %s", client or "default", video_id, exc)
            continue
        if (info or {}).get("url"):
            break
    else:
        info = None

    url = (info or {}).get("url")
    if not url:
        log.warning("No client could resolve a stream for %s", video_id)
        raise LumenError("Không nghe thử được bài này.")

    return StreamInfo(
        url=url,
        title=info.get("title") or "",
        uploader=info.get("uploader") or info.get("channel") or "",
        duration_ms=int((info.get("duration") or 0) * 1000),
        thumbnail=info.get("thumbnail") or f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",
    )
