"""Drive yt-dlp to fetch YouTube audio as tagged mp3 files. No SQL, no Qt."""

from __future__ import annotations

import logging
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import mutagen
import yt_dlp
from mutagen.id3 import APIC, ID3, TIT2, TPE1
from mutagen.mp3 import MP3

from lumen.core import tools
from lumen.core.errors import (
    DownloadError,
    ExtractionError,
    NetworkError,
    UnsupportedSourceError,
)
from lumen.core.metadata import derive_naming, sanitize_filename
from lumen.core.youtube import parse_url

log = logging.getLogger(__name__)

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}

_NETWORK_MARKERS = (
    "temporary failure in name resolution",
    "name or service not known",
    "failed to resolve",
    "getaddrinfo failed",
    "network is unreachable",
    "connection refused",
    "connection reset",
    "connection aborted",
    "no route to host",
    "timed out",
    "urlerror",
)

_EXTRACTION_MARKERS = (
    "video unavailable",
    "private video",
    "this video is unavailable",
    "removed by the user",
    "account associated with this video has been terminated",
    "not available in your country",
    "blocked it in your country",
    "age-restricted",
    "sign in to confirm",
    "members-only",
    "no video formats found",
    "unable to extract",
    "content isn't available",
)


class DownloadCancelled(DownloadError):
    """Raised when a download is aborted mid-flight via should_cancel()."""

    pass


class _CancelledByUser(Exception):
    """Internal signal raised from the progress hook to unwind yt-dlp early."""

    pass


@dataclass(frozen=True, slots=True)
class VideoInfo:
    """Metadata probed from a YouTube video before any download happens."""

    video_id: str
    url: str
    title: str
    uploader: str | None
    artist: str | None
    track: str | None
    duration_ms: int
    thumbnail_url: str | None
    is_live: bool


@dataclass(frozen=True, slots=True)
class DownloadResult:
    """Outcome of a completed download: final file paths and resolved naming."""

    video_id: str
    source_url: str
    title: str
    artist: str
    # Kênh đăng, y như YouTube trả về. Trang khám phá dùng nó để suy ra nghệ sĩ
    # thay vì tin vào phép tách "A - B" (phép đó lật ngược khi kênh đặt tên bài
    # trước nghệ sĩ).
    uploader: str
    duration_ms: int
    file_path: Path
    cover_path: Path | None


@dataclass(frozen=True, slots=True)
class Progress:
    """A single progress update meant to be shown as-is in the UI."""

    stage: str
    fraction: float
    detail: str


# YouTube chặn luồng audio của một số video theo "player client" mà yt-dlp giả lập.
# Video vẫn lấy được metadata bình thường nhưng tải xuống thì nhận HTTP 403.
# Không có client nào đúng cho mọi video, và yt-dlp KHÔNG tự đổi client khi tải hỏng —
# nó chọn format tốt nhất từ client đầu rồi mới chết. Nên ta phải tự thử lại cả lần tải.
# Đo trên thực tế: "Never Gonna Give You Up" 403 với client mặc định, tải được với web_embedded.
_PLAYER_CLIENT_FALLBACKS: tuple[str | None, ...] = (None, "web_embedded", "tv", "android")

# Dấu hiệu cho biết đổi player client có thể cứu được; lỗi khác thì thử lại vô ích.
_CLIENT_RETRYABLE_MARKERS = (
    "403",
    "forbidden",
    "requested format is not available",
    "unable to download video data",
)


def _is_client_retryable(exc: Exception) -> bool:
    """True when the failure looks like YouTube refusing this particular player client."""
    message = str(exc).lower()
    return any(marker in message for marker in _CLIENT_RETRYABLE_MARKERS)


class _YtdlpLogger:
    """Route yt-dlp's own chatter into the app log instead of the terminal.

    ``quiet`` alone does not silence yt-dlp: it still paints its own progress
    bar, which interleaves with the app's output and, in a GUI process, just
    scribbles over the terminal the user launched from. Giving it a logger plus
    ``noprogress`` keeps every message where it can actually be read later.
    """

    def debug(self, msg: str) -> None:
        # yt-dlp routes both debug and info here; info lines start with "[".
        log.debug("yt-dlp: %s", msg.strip())

    def info(self, msg: str) -> None:
        log.debug("yt-dlp: %s", msg.strip())

    def warning(self, msg: str) -> None:
        log.warning("yt-dlp: %s", msg.strip())

    def error(self, msg: str) -> None:
        log.error("yt-dlp: %s", msg.strip())


class Downloader:
    """Fetch a YouTube video as a tagged mp3 file using yt-dlp as a Python module."""

    def __init__(self, *, music_dir: Path, covers_dir: Path, bitrate: str = "192") -> None:
        self._music_dir = music_dir
        self._covers_dir = covers_dir
        self._bitrate = bitrate

    @property
    def music_dir(self) -> Path:
        """Where a download with no `target_dir` lands.

        Đường lấp dòng chỗ trống bằng cách CHÉP trên đĩa hỏi câu này để bỏ file
        vào đúng chỗ mà đường tải sẽ bỏ nó vào — hai đường cùng một dòng, khác
        thư mục thì thành hai kiểu thư viện tuỳ hôm ấy chép hay tải.
        """
        return self._music_dir

    def probe(self, url: str) -> VideoInfo:
        """Fetch video metadata without downloading anything."""
        ref = parse_url(url)

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "noprogress": True,
            "logger": _YtdlpLogger(),
            "skip_download": True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                raw = ydl.extract_info(ref.canonical_url, download=False)
        except Exception as exc:  # yt-dlp raises many undocumented exception types
            raise self._map_error(exc) from exc

        if raw is None:
            raise ExtractionError(
                f"yt-dlp returned no info for {ref.canonical_url}",
                user_message="Không thể lấy thông tin video này.",
            )

        info = VideoInfo(
            video_id=raw.get("id") or ref.video_id,
            url=raw.get("webpage_url") or ref.canonical_url,
            title=raw.get("title") or "",
            uploader=raw.get("uploader"),
            artist=raw.get("artist"),
            track=raw.get("track"),
            duration_ms=int(round((raw.get("duration") or 0) * 1000)),
            thumbnail_url=raw.get("thumbnail"),
            is_live=bool(raw.get("is_live")),
        )

        if info.is_live:
            raise UnsupportedSourceError(
                f"Live video is not supported: {info.video_id}",
                user_message="Video đang phát trực tiếp, Lumen chưa hỗ trợ tải loại video này.",
            )

        return info

    def download(
        self,
        url: str,
        *,
        target_dir: Path | None = None,
        on_progress: Callable[[Progress], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> DownloadResult:
        """Probe, download, convert to mp3, and tag a YouTube video end to end.

        ``target_dir`` overrides where the mp3 (and its transient thumbnail)
        land; it defaults to the shared library music dir when omitted.
        """

        def emit(stage: str, fraction: float, detail: str) -> None:
            if on_progress is not None:
                on_progress(Progress(stage=stage, fraction=fraction, detail=detail))

        emit("probing", -1.0, "Đang lấy thông tin video...")
        info = self.probe(url)

        naming = derive_naming(
            video_title=info.title,
            uploader=info.uploader,
            yt_artist=info.artist,
            yt_track=info.track,
        )

        dest_dir = target_dir if target_dir is not None else self._music_dir
        base_name = f"{sanitize_filename(f'{naming.artist} - {naming.title}')}-{info.video_id}"
        final_mp3_path = dest_dir / f"{base_name}.mp3"
        outtmpl = str(dest_dir / f"{base_name}.%(ext)s")

        dest_dir.mkdir(parents=True, exist_ok=True)

        def hook(status: dict) -> None:
            if should_cancel is not None and should_cancel():
                raise _CancelledByUser()
            state = status.get("status")
            if state == "downloading":
                total = status.get("total_bytes") or status.get("total_bytes_estimate")
                downloaded = status.get("downloaded_bytes") or 0
                fraction = (downloaded / total) if total else -1.0
                emit("downloading", fraction, "Đang tải âm thanh...")
            elif state == "finished":
                emit("converting", -1.0, "Đang chuyển đổi sang MP3...")

        ydl_opts = {
            "format": "bestaudio/best",
            # Bản đóng gói không có ffmpeg trong PATH — phải chỉ đường tường minh,
            # không thì yt-dlp tải xong rồi chết ở bước chuyển sang mp3.
            "ffmpeg_location": tools.ffmpeg_path(),
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": self._bitrate,
                }
            ],
            "writethumbnail": True,
            "quiet": True,
            "noplaylist": True,
            "no_warnings": True,
            "noprogress": True,
            "logger": _YtdlpLogger(),
            "outtmpl": outtmpl,
            "progress_hooks": [hook],
        }

        last_error: Exception | None = None
        for attempt, player_client in enumerate(_PLAYER_CLIENT_FALLBACKS):
            attempt_opts = dict(ydl_opts)
            if player_client is not None:
                attempt_opts["extractor_args"] = {"youtube": {"player_client": [player_client]}}
                log.info(
                    "Retrying %s with player_client=%s after: %s",
                    info.video_id, player_client, last_error,
                )
                emit("downloading", -1.0, "Đang thử lại bằng cách khác...")
            try:
                with yt_dlp.YoutubeDL(attempt_opts) as ydl:
                    ydl.extract_info(info.url, download=True)
            except _CancelledByUser:
                self._cleanup_stray_files(base_name, dest_dir)
                raise DownloadCancelled(
                    f"Download cancelled for {info.video_id}",
                    user_message="Đã huỷ tải xuống.",
                ) from None
            except Exception as exc:
                last_error = exc
                # Half-written files from the failed attempt would confuse the next one.
                self._cleanup_stray_files(base_name, dest_dir)
                if _is_client_retryable(exc) and attempt + 1 < len(_PLAYER_CLIENT_FALLBACKS):
                    continue
                raise self._map_error(exc) from exc
            else:
                last_error = None
                break

        if not final_mp3_path.exists():
            self._cleanup_stray_files(base_name, dest_dir)
            raise DownloadError(
                f"Expected output file missing: {final_mp3_path}",
                user_message="Tải xuống thất bại: không tìm thấy file kết quả.",
            )

        emit("tagging", -1.0, "Đang gắn thẻ và ảnh bìa...")
        cover_path = self._finalize_cover(base_name, info.video_id, dest_dir)
        self._tag_mp3(final_mp3_path, naming.title, naming.artist, cover_path)
        self._cleanup_stray_files(base_name, dest_dir, keep={final_mp3_path})

        emit("done", 1.0, "Hoàn tất.")

        return DownloadResult(
            video_id=info.video_id,
            source_url=info.url,
            title=naming.title,
            artist=naming.artist,
            uploader=(info.uploader or "").strip(),
            duration_ms=info.duration_ms,
            file_path=final_mp3_path,
            cover_path=cover_path,
        )

    def _finalize_cover(self, base_name: str, video_id: str, source_dir: Path) -> Path | None:
        """Move the downloaded thumbnail into covers_dir as jpg, or return None."""
        thumbnail = next(
            (
                path
                for path in sorted(source_dir.glob(f"{base_name}.*"))
                if path.suffix.lower() in _IMAGE_SUFFIXES
            ),
            None,
        )
        if thumbnail is None:
            return None

        self._covers_dir.mkdir(parents=True, exist_ok=True)
        cover_path = self._covers_dir / f"{video_id}.jpg"

        try:
            if thumbnail.suffix.lower() in {".jpg", ".jpeg"}:
                shutil.copyfile(thumbnail, cover_path)
            else:
                result = subprocess.run(
                    [tools.ffmpeg_path(), "-y", "-i", str(thumbnail), str(cover_path)],
                    capture_output=True,
                    timeout=30,
                    check=False,
                )
                if result.returncode != 0 or not cover_path.exists():
                    log.warning(
                        "ffmpeg thumbnail conversion failed for %s: %s",
                        video_id,
                        result.stderr.decode(errors="replace"),
                    )
                    return None
        except (OSError, subprocess.SubprocessError) as exc:
            log.warning("Failed to produce cover image for %s: %s", video_id, exc)
            return None
        finally:
            thumbnail.unlink(missing_ok=True)

        return cover_path

    def _tag_mp3(self, path: Path, title: str, artist: str, cover_path: Path | None) -> None:
        """Embed title, artist, and cover art into the mp3's ID3 tags."""
        try:
            audio = MP3(str(path), ID3=ID3)
            if audio.tags is None:
                audio.add_tags()
            tags = audio.tags
            tags.delall("TIT2")
            tags.add(TIT2(encoding=3, text=title))
            tags.delall("TPE1")
            tags.add(TPE1(encoding=3, text=artist))
            if cover_path is not None and cover_path.exists():
                tags.delall("APIC")
                tags.add(
                    APIC(
                        encoding=3,
                        mime="image/jpeg",
                        type=3,
                        desc="Cover",
                        data=cover_path.read_bytes(),
                    )
                )
            audio.save()
        except (mutagen.MutagenError, OSError) as exc:
            log.warning("Failed to tag %s: %s", path, exc)

    def _cleanup_stray_files(
        self, base_name: str, source_dir: Path, *, keep: frozenset[Path] = frozenset()
    ) -> None:
        """Remove leftover .part/.webm/.m4a/thumbnail/etc files for a given base name."""
        for path in source_dir.glob(f"{base_name}.*"):
            if path in keep:
                continue
            try:
                path.unlink()
            except OSError as exc:
                log.warning("Failed to remove stray file %s: %s", path, exc)

    def _map_error(self, exc: Exception) -> DownloadError:
        """Translate a yt-dlp/library exception into a typed Lumen error."""
        if isinstance(exc, DownloadError):
            return exc

        text = str(exc).lower()
        if any(marker in text for marker in _NETWORK_MARKERS):
            return NetworkError(
                str(exc),
                user_message="Lỗi kết nối mạng. Vui lòng kiểm tra Internet và thử lại.",
            )
        if any(marker in text for marker in _EXTRACTION_MARKERS):
            return ExtractionError(
                str(exc),
                user_message="Không thể lấy video này (riêng tư, đã bị xoá, hoặc bị chặn theo khu vực).",
            )
        return DownloadError(
            str(exc),
            user_message="Tải xuống thất bại. Vui lòng thử lại sau.",
        )
