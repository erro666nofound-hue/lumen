"""Recognize and normalize YouTube video URLs pasted by the user into the app.

Pure parsing -- no network, no yt-dlp call here. This module only decides
"is this a YouTube video link, and if so what's its canonical form". Actual
metadata/download happens elsewhere (core/downloader.py), which is expected
to feed off :class:`VideoRef`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

from .errors import InvalidUrlError

# Exactly 11 chars, YouTube's base64url-ish id alphabet.
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

# Hosts we accept, after lowercasing and stripping a leading "www.".
_ALLOWED_HOSTS = {"youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}

_PATH_KINDS = ("shorts", "embed", "live")

_INVALID_MESSAGE = "Link này không phải link YouTube hợp lệ. Hãy dán lại link video YouTube."


@dataclass(frozen=True, slots=True)
class VideoRef:
    """A resolved reference to a single YouTube video."""

    video_id: str
    canonical_url: str
    is_short: bool


def _reject(detail: str) -> None:
    raise InvalidUrlError(detail, user_message=_INVALID_MESSAGE)


def _normalize_raw(raw: str) -> str:
    text = raw.strip()
    if len(text) >= 2 and text.startswith("<") and text.endswith(">"):
        text = text[1:-1].strip()
    if "://" not in text:
        text = f"https://{text}"
    return text


def _extract_video_id(host: str, path: str, query: str) -> tuple[str | None, bool]:
    """Return (video_id, is_short) for a validated YouTube host, or (None, False) if unknown shape."""
    segments = [seg for seg in path.split("/") if seg]

    if host == "youtu.be":
        if not segments:
            return None, False
        return segments[0], False

    if not segments:
        return None, False

    if segments[0] == "watch":
        params = parse_qs(query)
        values = params.get("v")
        if not values:
            return None, False
        return values[0], False

    if segments[0] in _PATH_KINDS and len(segments) >= 2:
        return segments[1], segments[0] == "shorts"

    return None, False


def parse_url(raw: str) -> VideoRef:
    """Parse a user-pasted string into a VideoRef, or raise InvalidUrlError with a Vietnamese message."""
    if not isinstance(raw, str):
        _reject(f"Expected str, got {type(raw).__name__}")

    text = raw.strip()
    if not text:
        _reject("Empty input")

    text = _normalize_raw(text)

    parts = urlsplit(text)

    if parts.scheme not in ("http", "https"):
        _reject(f"Unsupported scheme: {parts.scheme!r}")

    host = parts.netloc.split(":")[0].lower()
    if host.startswith("www."):
        host = host[4:]

    if host not in _ALLOWED_HOSTS:
        _reject(f"Unsupported host: {host!r}")

    video_id, is_short = _extract_video_id(host, parts.path, parts.query)

    if video_id is None or not _VIDEO_ID_RE.match(video_id):
        _reject(f"Could not find a valid video id in {text!r}")

    return VideoRef(video_id=video_id, canonical_url=watch_url(video_id), is_short=is_short)


def watch_url(video_id: str) -> str:
    """Return the canonical watch URL for a YouTube video id."""
    # Một chỗ duy nhất biết hình dạng của link. `sync_songs` cũng cần nó: bài
    # đồng bộ về mà ảnh chụp thiếu link thì vẫn dựng lại được từ mã video.
    return f"https://www.youtube.com/watch?v={video_id}"


def is_youtube_url(raw: str) -> bool:
    """Return True if raw parses as a YouTube video URL, without raising."""
    try:
        parse_url(raw)
    except InvalidUrlError:
        return False
    return True
