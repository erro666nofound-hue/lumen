"""Tests for lumen.core.downloader. No network: yt_dlp.YoutubeDL is replaced by a fake."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import pytest
import yt_dlp

from lumen.core.downloader import (
    DownloadCancelled,
    DownloadResult,
    Downloader,
    Progress,
    VideoInfo,
)
from lumen.core.errors import (
    DownloadError,
    ExtractionError,
    NetworkError,
    UnsupportedSourceError,
)
from lumen.core.metadata import sanitize_filename

VIDEO_ID = "dQw4w9WgXcQ"
URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"


def _probe_result(**overrides: object) -> dict:
    base = {
        "id": VIDEO_ID,
        "webpage_url": URL,
        "title": "Artist Name - Cool Song (Official Video)",
        "uploader": "Artist Name Official",
        "artist": None,
        "track": None,
        "duration": 213.7,
        "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
        "is_live": False,
    }
    base.update(overrides)
    return base


class _FakeYoutubeDL:
    """Stand-in for yt_dlp.YoutubeDL. Downloader only ever does
    ``yt_dlp.YoutubeDL(opts)`` then ``.extract_info(...)`` (as a context manager),
    so that's the entire surface this fake needs to cover.

    Behavior for a given test is set on the class *before* Downloader is
    invoked (the `fake_ydl` fixture resets everything between tests).
    """

    probe_result: dict | None = None
    probe_exception: Exception | None = None
    download_exception: Exception | None = None
    progress_events: list[dict] | None = None
    write_files: bool = True
    write_thumbnail_ext: str | None = ".jpg"
    thumbnail_bytes: bytes = b"fake-thumb-bytes"

    last_opts: dict | None = None

    def __init__(self, opts: dict) -> None:
        self.opts = dict(opts)
        type(self).last_opts = self.opts

    def __enter__(self) -> "_FakeYoutubeDL":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def extract_info(self, url: str, download: bool = False) -> dict:
        if not download:
            if self.probe_exception is not None:
                raise self.probe_exception
            return dict(self.probe_result or {})

        outtmpl = self.opts["outtmpl"]
        assert outtmpl.endswith(".%(ext)s"), "downloader must not use %(title)s-style outtmpl"
        base = outtmpl[: -len(".%(ext)s")]

        # Simulate yt-dlp's own in-progress temp file, so cancellation/error
        # cleanup has something real to remove.
        partial_path = Path(f"{base}.webm.part")
        partial_path.write_bytes(b"partial-bytes")

        hooks = self.opts.get("progress_hooks", [])
        events = self.progress_events
        if events is None:
            events = [
                {"status": "downloading", "downloaded_bytes": 50, "total_bytes": 100},
                {"status": "downloading", "downloaded_bytes": 100, "total_bytes": 100},
                {"status": "finished"},
            ]
        for event in events:
            for hook in hooks:
                hook(event)  # may raise the downloader's internal cancel signal

        if self.download_exception is not None:
            raise self.download_exception

        partial_path.unlink(missing_ok=True)

        if self.write_files:
            Path(f"{base}.mp3").write_bytes(b"fake-mp3-bytes-not-a-real-mp3")
            if self.write_thumbnail_ext:
                Path(f"{base}{self.write_thumbnail_ext}").write_bytes(self.thumbnail_bytes)

        return dict(self.probe_result or {})


@pytest.fixture
def fake_ydl(monkeypatch: pytest.MonkeyPatch) -> type[_FakeYoutubeDL]:
    _FakeYoutubeDL.probe_result = None
    _FakeYoutubeDL.probe_exception = None
    _FakeYoutubeDL.download_exception = None
    _FakeYoutubeDL.progress_events = None
    _FakeYoutubeDL.write_files = True
    _FakeYoutubeDL.write_thumbnail_ext = ".jpg"
    _FakeYoutubeDL.thumbnail_bytes = b"fake-thumb-bytes"
    _FakeYoutubeDL.last_opts = None
    monkeypatch.setattr(yt_dlp, "YoutubeDL", _FakeYoutubeDL)
    return _FakeYoutubeDL


@pytest.fixture
def downloader(tmp_path: Path) -> Downloader:
    music_dir = tmp_path / "music"
    covers_dir = tmp_path / "covers"
    music_dir.mkdir()
    covers_dir.mkdir()
    return Downloader(music_dir=music_dir, covers_dir=covers_dir, bitrate="192")


# --- probe() -----------------------------------------------------------


def test_probe_success_returns_video_info(fake_ydl, downloader):
    fake_ydl.probe_result = _probe_result()

    info = downloader.probe(URL)

    assert isinstance(info, VideoInfo)
    assert info.video_id == VIDEO_ID
    assert info.title == "Artist Name - Cool Song (Official Video)"
    assert info.uploader == "Artist Name Official"
    assert info.duration_ms == 213700
    assert info.is_live is False
    assert info.thumbnail_url == "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"


def test_probe_live_video_raises_unsupported_source_error(fake_ydl, downloader):
    fake_ydl.probe_result = _probe_result(is_live=True)

    with pytest.raises(UnsupportedSourceError) as exc_info:
        downloader.probe(URL)

    assert exc_info.value.user_message
    assert "trực tiếp" in exc_info.value.user_message


def test_probe_video_unavailable_maps_to_extraction_error(fake_ydl, downloader):
    fake_ydl.probe_exception = yt_dlp.utils.DownloadError(
        "ERROR: [youtube] dQw4w9WgXcQ: Video unavailable"
    )

    with pytest.raises(ExtractionError) as exc_info:
        downloader.probe(URL)

    assert exc_info.value.user_message
    assert "riêng tư" in exc_info.value.user_message or "xoá" in exc_info.value.user_message


def test_probe_dns_failure_maps_to_network_error(fake_ydl, downloader):
    fake_ydl.probe_exception = yt_dlp.utils.DownloadError(
        "<urlopen error [Errno -3] Temporary failure in name resolution>"
    )

    with pytest.raises(NetworkError) as exc_info:
        downloader.probe(URL)

    assert exc_info.value.user_message


def test_probe_unknown_error_maps_to_generic_download_error(fake_ydl, downloader):
    fake_ydl.probe_exception = RuntimeError("some totally unexpected internal yt-dlp failure")

    with pytest.raises(DownloadError) as exc_info:
        downloader.probe(URL)

    assert not isinstance(exc_info.value, (NetworkError, ExtractionError))


def test_probe_invalid_url_raises_before_touching_ydl(fake_ydl, downloader):
    from lumen.core.errors import InvalidUrlError

    with pytest.raises(InvalidUrlError):
        downloader.probe("https://example.com/not-youtube")

    assert fake_ydl.last_opts is None  # never even constructed a YoutubeDL


# --- download() ----------------------------------------------------------


def test_download_creates_mp3_with_sanitized_deterministic_name(fake_ydl, downloader):
    fake_ydl.probe_result = _probe_result()

    result = downloader.download(URL)

    assert isinstance(result, DownloadResult)
    assert result.video_id == VIDEO_ID
    # Tên bài giờ là NGUYÊN tiêu đề video (xem derive_naming) — không tách nữa.
    assert result.title == "Artist Name - Cool Song"
    assert result.artist == "Artist Name"
    assert result.duration_ms == 213700
    assert result.source_url == URL

    expected_base = sanitize_filename(f"{result.artist} - {result.title}")
    expected_name = f"{expected_base}-{VIDEO_ID}.mp3"
    assert result.file_path.name == expected_name
    assert result.file_path.exists()

    assert result.cover_path is not None
    assert result.cover_path == downloader._covers_dir / f"{VIDEO_ID}.jpg"
    assert result.cover_path.exists()

    # No .part/thumbnail/etc leftovers in music_dir once done.
    leftovers = [p for p in downloader._music_dir.iterdir() if p != result.file_path]
    assert leftovers == []


def test_download_tagging_failure_does_not_fail_the_download(fake_ydl, downloader, caplog):
    # The fake writes non-mp3 bytes, so mutagen tagging is guaranteed to fail --
    # this must be swallowed (logged) rather than propagated.
    fake_ydl.probe_result = _probe_result()

    with caplog.at_level(logging.WARNING):
        result = downloader.download(URL)

    assert result.file_path.exists()
    assert any("tag" in record.message.lower() for record in caplog.records)


def test_download_progress_reports_expected_stage_sequence(fake_ydl, downloader):
    fake_ydl.probe_result = _probe_result()
    stages: list[Progress] = []

    downloader.download(URL, on_progress=stages.append)

    stage_names = [p.stage for p in stages]
    assert stage_names[0] == "probing"
    assert stage_names[-1] == "done"
    for required in ("probing", "downloading", "converting", "tagging", "done"):
        assert required in stage_names
    assert (
        stage_names.index("probing")
        < stage_names.index("downloading")
        < stage_names.index("converting")
        < stage_names.index("tagging")
        < stage_names.index("done")
    )

    downloading_events = [p for p in stages if p.stage == "downloading"]
    assert downloading_events[0].fraction == pytest.approx(0.5)
    assert downloading_events[1].fraction == pytest.approx(1.0)
    assert stages[-1].fraction == pytest.approx(1.0)


def test_download_cancelled_raises_and_removes_partial_files(fake_ydl, downloader):
    fake_ydl.probe_result = _probe_result()
    calls = {"n": 0}

    def should_cancel() -> bool:
        calls["n"] += 1
        return calls["n"] >= 2  # cancel partway through the (fake) download

    with pytest.raises(DownloadCancelled) as exc_info:
        downloader.download(URL, should_cancel=should_cancel)

    assert exc_info.value.user_message
    assert list(downloader._music_dir.iterdir()) == []


def test_download_video_unavailable_maps_to_extraction_error_and_cleans_up(fake_ydl, downloader):
    fake_ydl.probe_result = _probe_result()
    fake_ydl.download_exception = yt_dlp.utils.DownloadError("ERROR: Video unavailable")

    with pytest.raises(ExtractionError):
        downloader.download(URL)

    assert list(downloader._music_dir.iterdir()) == []


def test_download_sanitizes_special_characters_in_title(fake_ydl, downloader):
    fake_ydl.probe_result = _probe_result(
        title="Cool Song / Part Two: The Sequel > Extended?",
        uploader="DJ Test",
        artist=None,
        track=None,
    )

    result = downloader.download(URL)

    forbidden_chars = set('\\/:*?"<>|')
    assert not (forbidden_chars & set(result.file_path.name))
    assert result.file_path.name.endswith(f"-{VIDEO_ID}.mp3")
    assert result.file_path.exists()


def _make_test_webp(tmp_path: Path) -> bytes:
    out = tmp_path / "seed-thumb.webp"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=red:s=16x16", "-frames:v", "1", str(out)],
        check=True,
        capture_output=True,
        timeout=30,
    )
    return out.read_bytes()


def test_download_converts_webp_thumbnail_to_jpg_cover(fake_ydl, downloader, tmp_path):
    fake_ydl.probe_result = _probe_result()
    fake_ydl.write_thumbnail_ext = ".webp"
    fake_ydl.thumbnail_bytes = _make_test_webp(tmp_path)

    result = downloader.download(URL)

    assert result.cover_path is not None
    assert result.cover_path.suffix == ".jpg"
    assert result.cover_path.exists()
    assert result.cover_path.read_bytes()[:2] == b"\xff\xd8"  # JPEG magic bytes
