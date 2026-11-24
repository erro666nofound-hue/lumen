"""Threading-contract tests for DownloadBridge.

These use a fake downloader on purpose: the point is not that yt-dlp works
(tests/test_downloader.py covers that), it is that whatever the worker thread
does, every model mutation and every database write still lands on the main
thread. That rule is invisible at runtime until it corrupts something, so it
gets a test of its own.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from lumen.bridge.download_bridge import (  # noqa: E402
    STATE_FAILED,
    DownloadBridge,
)
from lumen.bridge.library_bridge import LibraryBridge  # noqa: E402
from lumen.core import db  # noqa: E402
from lumen.core.downloader import DownloadCancelled, DownloadResult  # noqa: E402
from lumen.core.errors import NetworkError  # noqa: E402
from lumen.core.repository import PlaylistRepository, TrackRepository  # noqa: E402

VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
VIDEO_ID = "dQw4w9WgXcQ"


@pytest.fixture(scope="module")
def qapp() -> QGuiApplication:
    return QGuiApplication.instance() or QGuiApplication([])


class _FakeDownloader:
    """Stands in for Downloader; records which thread it ran on."""

    def __init__(self, tmp_path: Path, *, raise_error: Exception | None = None) -> None:
        self.tmp_path = tmp_path
        # Đường lấp dòng chỗ trống hỏi downloader "file rơi vào thư mục nào"
        # để CHÉP vào đúng chỗ đó (CB-036). Fake phải trả lời được, nếu không
        # nó không còn giống cái nó đang đóng thế.
        self.music_dir = tmp_path
        self.raise_error = raise_error
        self.ran_on_thread: int | None = None

    def download(self, url, *, target_dir=None, on_progress=None,
                     should_cancel=None, known_artists=None):
        self.ran_on_thread = threading.get_ident()
        if should_cancel is not None and should_cancel():
            raise DownloadCancelled("cancelled")
        if self.raise_error is not None:
            raise self.raise_error
        media = self.tmp_path / "fake.mp3"
        media.write_bytes(b"\x00")
        return DownloadResult(
            video_id=VIDEO_ID,
            source_url=url,
            title="Never Gonna Give You Up",
            artist="Rick Astley",
            uploader="Rick Astley",
            duration_ms=213_000,
            file_path=media,
            cover_path=None,
        )


@pytest.fixture
def library(tmp_path: Path) -> LibraryBridge:
    conn = db.connect(tmp_path / "library.db")
    return LibraryBridge(TrackRepository(conn))


@pytest.fixture
def playlist_repository(tmp_path: Path) -> PlaylistRepository:
    # Same db file as `library`: db.connect() re-opens it happily since the
    # schema is already migrated, and these tests never touch playlist rows.
    conn = db.connect(tmp_path / "library.db")
    return PlaylistRepository(conn)


def _pump_until(predicate, timeout_ms: int = 5000) -> bool:
    """Run a real event loop until predicate() is true or the timeout expires."""
    loop = QEventLoop()
    ticker = QTimer()
    ticker.setInterval(10)
    ticker.timeout.connect(lambda: loop.quit() if predicate() else None)
    guard = QTimer()
    guard.setSingleShot(True)
    guard.timeout.connect(loop.quit)
    ticker.start()
    guard.start(timeout_ms)
    loop.exec()
    ticker.stop()
    guard.stop()
    return predicate()


def test_download_runs_off_main_thread_but_reports_on_it(qapp, library, playlist_repository, tmp_path) -> None:
    downloader = _FakeDownloader(tmp_path)
    bridge = DownloadBridge(downloader, library, playlist_repository)

    signal_threads: set[int] = set()
    bridge.dataChanged.connect(lambda *_: signal_threads.add(threading.get_ident()))
    added: list[int] = []
    bridge.trackAdded.connect(added.append)

    bridge.add(VIDEO_URL)
    assert _pump_until(lambda: bool(added)), "download never completed"

    main_thread = threading.get_ident()
    assert downloader.ran_on_thread is not None
    assert downloader.ran_on_thread != main_thread, "download must not block the UI thread"
    assert signal_threads <= {main_thread}, "model was mutated from a worker thread"
    assert library.count == 1


def test_finished_download_is_written_to_the_library(qapp, library, playlist_repository, tmp_path) -> None:
    bridge = DownloadBridge(_FakeDownloader(tmp_path), library, playlist_repository)
    added: list[int] = []
    bridge.trackAdded.connect(added.append)

    bridge.add(VIDEO_URL)
    assert _pump_until(lambda: bool(added))

    index = library.index(0, 0)
    assert library.data(index, library.TitleRole) == "Never Gonna Give You Up"
    assert library.data(index, library.ArtistRole) == "Rick Astley"
    assert library.data(index, library.DurationTextRole) == "3:33"


def test_duplicate_url_is_rejected_before_any_work_starts(qapp, library, playlist_repository, tmp_path) -> None:
    bridge = DownloadBridge(_FakeDownloader(tmp_path), library, playlist_repository)
    added: list[int] = []
    bridge.trackAdded.connect(added.append)
    bridge.add(VIDEO_URL)
    assert _pump_until(lambda: bool(added))

    errors: list[str] = []
    bridge.errorOccurred.connect(errors.append)
    bridge.add(VIDEO_URL)
    assert errors == ["Bài này đã có trong thư viện."]
    assert library.count == 1


def test_invalid_url_reports_an_error_and_queues_nothing(qapp, library, playlist_repository, tmp_path) -> None:
    bridge = DownloadBridge(_FakeDownloader(tmp_path), library, playlist_repository)
    errors: list[str] = []
    bridge.errorOccurred.connect(errors.append)

    bridge.add("https://vimeo.com/12345")

    assert len(errors) == 1
    assert bridge.count == 0


def test_download_failure_surfaces_a_user_message(qapp, library, playlist_repository, tmp_path) -> None:
    downloader = _FakeDownloader(tmp_path, raise_error=NetworkError("boom", user_message="Mất mạng."))
    bridge = DownloadBridge(downloader, library, playlist_repository)
    errors: list[str] = []
    bridge.errorOccurred.connect(errors.append)

    bridge.add(VIDEO_URL)
    assert _pump_until(lambda: bool(errors))

    assert errors == ["Mất mạng."]
    assert library.count == 0
    assert bridge.data(bridge.index(0, 0), bridge.StateRole) == STATE_FAILED


def test_failed_job_can_be_retried(qapp, library, playlist_repository, tmp_path) -> None:
    downloader = _FakeDownloader(tmp_path, raise_error=NetworkError("boom", user_message="Mất mạng."))
    bridge = DownloadBridge(downloader, library, playlist_repository)
    errors: list[str] = []
    bridge.errorOccurred.connect(errors.append)
    bridge.add(VIDEO_URL)
    assert _pump_until(lambda: bool(errors))

    downloader.raise_error = None
    added: list[int] = []
    bridge.trackAdded.connect(added.append)
    bridge.retry(bridge.data(bridge.index(0, 0), bridge.JobIdRole))

    assert _pump_until(lambda: bool(added))
    assert library.count == 1


class TestPendingIsScopedToOneTrack:
    """Bài đang tải vào track Cozy KHÔNG được hiện ở mọi track khác.

    Dải tiến độ cũ đọc cả model tải nên track nào cũng thấy thanh chạy — chủ
    dự án báo đúng chỗ này.
    """

    def test_pending_for_only_returns_that_playlist(
        self, qapp, library, playlist_repository, tmp_path: Path
    ) -> None:
        bridge = DownloadBridge(_FakeDownloader(tmp_path), library, playlist_repository)
        cozy = playlist_repository.create("Cozy").id
        other = playlist_repository.create("Ambient").id
        bridge.addToPlaylist("https://www.youtube.com/watch?v=aaaaaaaaaaa", cozy)
        bridge.addToPlaylist("https://www.youtube.com/watch?v=bbbbbbbbbbb", other)

        assert len(bridge.pendingFor(cozy)) == 1
        assert len(bridge.pendingFor(other)) == 1
        assert bridge.pendingFor(9999) == []

    def test_is_downloading_into_is_per_playlist(
        self, qapp, library, playlist_repository, tmp_path: Path
    ) -> None:
        bridge = DownloadBridge(_FakeDownloader(tmp_path), library, playlist_repository)
        cozy = playlist_repository.create("Cozy").id
        other = playlist_repository.create("Ambient").id
        bridge.addToPlaylist("https://www.youtube.com/watch?v=aaaaaaaaaaa", cozy)

        assert bridge.isDownloadingInto(cozy) is True
        assert bridge.isDownloadingInto(other) is False

    def test_a_library_download_belongs_to_no_playlist(
        self, qapp, library, playlist_repository, tmp_path: Path
    ) -> None:
        bridge = DownloadBridge(_FakeDownloader(tmp_path), library, playlist_repository)
        cozy = playlist_repository.create("Cozy").id
        bridge.add("https://www.youtube.com/watch?v=ccccccccccc")

        assert bridge.pendingFor(cozy) == []
        assert bridge.isDownloadingInto(cozy) is False
