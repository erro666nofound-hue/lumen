"""Turn messy yt-dlp video titles into clean (title, artist) pairs.

yt-dlp hands back whatever the uploader typed into the video title, which is
usually full of "(Official Video)", "[MV]", trailing "| Official MV" tags and
similar clutter. This module strips that clutter so the rest of the app (and
eventually the recommendation lookup, which keys off the artist name) works
with something a human would call a clean title/artist.

Pure string processing -- no I/O, no network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Individual noise *words*. A bracketed group, or a trailing chunk of the
# title, is considered pure noise (and dropped) only when every token inside
# it is one of these -- that's what lets "(Full HD)" go but "(Full Album)"
# stay, without hardcoding every possible phrase combination.
_NOISE_WORDS = {
    "official",
    "music",
    "video",
    "audio",
    "lyric",
    "lyrics",
    "visualizer",
    "mv",
    "m/v",
    "hd",
    "4k",
    "hq",
    "oficial",
    "officiel",
    "clip",
    "remastered",
    "explicit",
    "free",
    "download",
    "full",
}

_BRACKET_RE = re.compile(r"[\(\[]\s*([^()\[\]]*?)\s*[\)\]]")

# One trailing "word" (letters/digits/slash, so "M/V" survives as one token)
# preceded by whitespace/pipe/dash/quote separators, anchored at the end.
_TRAILING_TOKEN_RE = re.compile(r"(?:^|[\s|\"'\-–—])([A-Za-z0-9/]+)$")
_TRAILING_SEP_RE = re.compile(r"[\s|\"'\-–—]+$")
_LEADING_SEP_RE = re.compile(r"^[\s|\"'\-–—]+")


_QUOTE_PAIRS = (("'", "'"), ('"', '"'), ("‘", "’"), ("“", "”"))

_UPLOADER_TOPIC_RE = re.compile(r"(?i)\s*-\s*topic$")
_UPLOADER_OFFICIAL_RE = re.compile(r"(?i)\s*official$")
_UPLOADER_VEVO_RE = re.compile(r"(?i)vevo$")

_DASH_RUN_RE = re.compile(r"-{2,}")
_WHITESPACE_RE = re.compile(r"\s+")

_FORBIDDEN_FILENAME_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f\x7f]')


@dataclass(frozen=True, slots=True)
class TrackNaming:
    """Cleaned-up (title, artist) pair derived from raw yt-dlp metadata."""

    title: str
    artist: str


def _is_noise_token(token: str) -> bool:
    return token.lower().strip(".,") in _NOISE_WORDS


def _bracket_is_noise(content: str) -> bool:
    tokens = content.split()
    if not tokens:
        return True  # an empty "()" carries no information, safe to drop
    return all(_is_noise_token(tok) for tok in tokens)


def _strip_noise_brackets(text: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        return "" if _bracket_is_noise(match.group(1)) else match.group(0)

    return _BRACKET_RE.sub(_replace, text)


def _strip_trailing_noise(text: str) -> str:
    current = text.strip()
    while True:
        match = _TRAILING_TOKEN_RE.search(current)
        if not match or not _is_noise_token(match.group(1)):
            return current
        current = current[: match.start(1)]
        current = _TRAILING_SEP_RE.sub("", current)


def _strip_wrapping_quotes(text: str) -> str:
    if len(text) < 2:
        return text
    for open_q, close_q in _QUOTE_PAIRS:
        if text.startswith(open_q) and text.endswith(close_q):
            return text[len(open_q) : len(text) - len(close_q)].strip()
    return text


def _trim_stray_separators(text: str) -> str:
    text = _LEADING_SEP_RE.sub("", text)
    text = _TRAILING_SEP_RE.sub("", text)
    return text.strip()


def clean_title(raw: str) -> str:
    """Strip "(Official Video)"-style noise from a raw video title."""
    original = raw.strip()
    if not original:
        return original

    text = _strip_noise_brackets(original)
    text = _WHITESPACE_RE.sub(" ", text).strip()

    previous = None
    while previous != text:
        previous = text
        text = _strip_trailing_noise(text)
        text = _strip_wrapping_quotes(text)
        text = _trim_stray_separators(text)

    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text if text else original


def _clean_uploader(uploader: str) -> str:
    name = uploader.strip()
    name = _UPLOADER_TOPIC_RE.sub("", name)
    name = _UPLOADER_OFFICIAL_RE.sub("", name)
    name = _UPLOADER_VEVO_RE.sub("", name)
    return name.strip()





def derive_naming(
    *,
    video_title: str,
    uploader: str | None = None,
    yt_artist: str | None = None,
    yt_track: str | None = None,
) -> TrackNaming:
    """(tên bài, nghệ sĩ) cho một video.

    LUẬT: tên bài = ĐÚNG tiêu đề video, nghệ sĩ = KÊNH đã đăng. Không tách,
    không đoán.

    Bản trước tách tiêu đề dạng "A - B" rồi cố đoán vế nào là nghệ sĩ, dựa vào
    tên kênh và vào thư viện của người dùng. Nó sai thường xuyên và sai theo cả
    hai chiều — "discopled - zachz winner (SLOWED + REVERB)" ra tên bài
    "zachz winner", "Hikari - Clovis Reyes & VDYCD" ra nghệ sĩ "Hikari". Mỗi
    lần chữa một ca lại đẻ ra ca khác, vì tiêu đề YouTube là chữ TỰ DO: không
    có quy tắc nào đúng cho mọi kênh.

    Lấy nguyên tiêu đề thì đôi khi dài, nhưng LUÔN LUÔN đúng cái người dùng
    nhìn thấy trên YouTube. Còn kênh là dữ liệu có cấu trúc, không phải suy
    đoán. Trang khám phá đã lọc theo hạng mục nhạc và theo mức yêu thích, nên
    không cần tên nghệ sĩ "đẹp" để chạy đúng.

    `yt_artist`/`yt_track` vẫn được ưu tiên khi CÓ: đó là siêu dữ liệu nhạc do
    chính YouTube gắn, không phải chữ tự do.
    """
    fallback_title = video_title.strip()

    if yt_artist and yt_artist.strip() and yt_track and yt_track.strip():
        return TrackNaming(
            title=clean_title(yt_track.strip()) or fallback_title,
            artist=yt_artist.strip(),
        )

    channel = _clean_uploader(uploader) if uploader else ""
    return TrackNaming(
        title=clean_title(video_title) or fallback_title,
        artist=channel or "Unknown Artist",
    )


def sanitize_filename(name: str, max_length: int = 80) -> str:
    """Turn a track name into a safe filename component (no path separators, no control chars)."""
    cleaned = _FORBIDDEN_FILENAME_RE.sub("", name.strip())
    cleaned = _WHITESPACE_RE.sub("-", cleaned.strip())
    # Removing a forbidden character can leave neighbouring separators touching
    # ("AC/DC - Back" -> "ACDC---Back"). The user browses ~/Music/Lumen by hand,
    # so collapse runs of dashes into one.
    cleaned = _DASH_RUN_RE.sub("-", cleaned)
    cleaned = cleaned[:max_length]
    cleaned = cleaned.rstrip(".-")
    return cleaned if cleaned else "track"
