"""Coverage for DownloadBridge.addToPlaylist: per-track folders, copy-not-redownload.

Companion to tests/test_download_bridge.py (read that one first for the
threading-contract rationale). This file exercises the newer "same YouTube
video can live in several tracks" behaviour: a fresh download goes into the
target track's own folder, a video already in the library gets copied
instead of re-fetched, and duplicate-in-this-playlist is rejected without
touching the network.
"""

from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from lumen.bridge.download_bridge import DownloadBridge  # noqa: E402
from lumen.bridge.library_bridge import LibraryBridge  # noqa: E402
from lumen.core import db, paths  # noqa: E402
from lumen.core.downloader import DownloadResult  # noqa: E402
from lumen.core.library_files import copy_into, duplicate_into  # noqa: E402
from lumen.core.repository import PlaylistRepository, TrackRepository  # noqa: E402
from tests.conftest import make_track  # noqa: E402

VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
VIDEO_ID = "dQw4w9WgXcQ"


@pytest.fixture(scope="module")
def qapp() -> QGuiApplication:
    return QGuiApplication.instance() or QGuiApplication([])


class _FakeDownloader:
    """Stands in for Downloader; writes a fake mp3 into whatever target_dir it is given."""

    def __init__(self) -> None:
        self.calls: list[Path | None] = []
        # Đường lấp dòng chỗ trống hỏi downloader "file rơi vào thư mục nào"
        # để CHÉP vào đúng chỗ đó (CB-036). Fake phải trả lời được, nếu không
        # nó không còn giống cái nó đang đóng thế.
        self.music_dir = Path(tempfile.mkdtemp())

    def download(self, url, *, target_dir=None, on_progress=None,
                     should_cancel=None, known_artists=None):
        self.calls.append(target_dir)
        out_dir = target_dir if target_dir is not None else Path.cwd()
        out_dir.mkdir(parents=True, exist_ok=True)
        media = out_dir / "fake.mp3"
        media.write_bytes(b"\x00fake-audio")
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


class _NeverCalledDownloader:
    """Fails the test loudly if the download path is ever reached."""

    def download(self, *args, **kwargs):
        raise AssertionError("downloader.download() should not run for a copy-from-library path")


@pytest.fixture
def conn(tmp_path: Path):
    return db.connect(tmp_path / "library.db")


@pytest.fixture
def library(conn) -> LibraryBridge:
    return LibraryBridge(TrackRepository(conn))


@pytest.fixture
def playlist_repository(conn) -> PlaylistRepository:
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


def test_download_into_empty_playlist_lands_in_track_folder(
    qapp, library, playlist_repository, tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(paths, "music_dir", lambda: tmp_path / "Music")
    playlist = playlist_repository.create("Roadtrip")
    downloader = _FakeDownloader()
    bridge = DownloadBridge(downloader, library, playlist_repository)
    added: list[int] = []
    bridge.trackAdded.connect(added.append)

    bridge.addToPlaylist(VIDEO_URL, playlist.id)
    assert _pump_until(lambda: bool(added))

    tracks = playlist_repository.tracks(playlist.id)
    assert len(tracks) == 1
    assert tracks[0].source_id == VIDEO_ID
    expected_dir = tmp_path / "Music" / "Roadtrip"
    assert Path(tracks[0].file_path).parent == expected_dir
    assert Path(tracks[0].file_path).exists()


def test_same_song_twice_into_same_playlist_is_blocked(
    qapp, library, playlist_repository, tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(paths, "music_dir", lambda: tmp_path / "Music")
    playlist = playlist_repository.create("Roadtrip")
    bridge = DownloadBridge(_FakeDownloader(), library, playlist_repository)
    added: list[int] = []
    bridge.trackAdded.connect(added.append)
    bridge.addToPlaylist(VIDEO_URL, playlist.id)
    assert _pump_until(lambda: bool(added))

    errors: list[str] = []
    bridge.errorOccurred.connect(errors.append)
    bridge.addToPlaylist(VIDEO_URL, playlist.id)

    assert len(errors) == 1
    assert "track" in errors[0]
    assert len(playlist_repository.tracks(playlist.id)) == 1


def test_song_already_in_library_is_copied_not_redownloaded(
    qapp, library, playlist_repository, tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(paths, "music_dir", lambda: tmp_path / "Music")
    source_playlist = playlist_repository.create("Chill")
    target_playlist = playlist_repository.create("Workout")

    bridge = DownloadBridge(_FakeDownloader(), library, playlist_repository)
    first_added: list[int] = []
    bridge.trackAdded.connect(first_added.append)
    bridge.addToPlaylist(VIDEO_URL, source_playlist.id)
    assert _pump_until(lambda: bool(first_added))

    original_track = playlist_repository.tracks(source_playlist.id)[0]
    original_path = Path(original_track.file_path)
    assert original_path.exists()

    # Swap in a downloader that blows up if it is ever invoked, proving the
    # second add takes the copy path instead of hitting the network again.
    bridge2 = DownloadBridge(_NeverCalledDownloader(), library, playlist_repository)
    notices: list[str] = []
    bridge2.noticeOccurred.connect(notices.append)
    added2: list[int] = []
    bridge2.trackAdded.connect(added2.append)

    bridge2.addToPlaylist(VIDEO_URL, target_playlist.id)
    assert _pump_until(lambda: bool(added2))

    assert notices, "expected a 'copied from library' notice"
    assert "tải lại" in notices[0] or "thư viện" in notices[0]

    target_track = playlist_repository.tracks(target_playlist.id)[0]
    assert target_track.source_id == original_track.source_id
    assert target_track.file_path != original_track.file_path
    assert Path(target_track.file_path).exists()
    assert original_path.exists(), "the original library file must survive the copy"


def test_copy_into_adds_numeric_suffix_when_a_different_file_occupies_the_name(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source_file = source_dir / "song.mp3"
    source_file.write_bytes(b"real audio bytes")

    target_dir = tmp_path / "target"
    target_dir.mkdir()
    unrelated_file = target_dir / "song.mp3"
    unrelated_file.write_bytes(b"totally different bytes")

    result_path = copy_into(source_file, target_dir)

    assert result_path != unrelated_file
    assert result_path.exists()
    assert result_path.read_bytes() == b"real audio bytes"
    # The pre-existing, unrelated file must not have been clobbered.
    assert unrelated_file.read_bytes() == b"totally different bytes"


def test_copy_into_is_idempotent_when_the_same_file_is_already_there(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source_file = source_dir / "song.mp3"
    source_file.write_bytes(b"same bytes")

    target_dir = tmp_path / "target"

    first = copy_into(source_file, target_dir)
    second = copy_into(source_file, target_dir)

    assert first == second
    assert first.read_bytes() == b"same bytes"


def test_download_runs_off_main_thread_even_for_playlist_downloads(
    qapp, library, playlist_repository, tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(paths, "music_dir", lambda: tmp_path / "Music")
    playlist = playlist_repository.create("Roadtrip")
    threads_seen: set[int] = set()

    class _RecordingDownloader:
        def download(self, url, *, target_dir=None, on_progress=None,
                     should_cancel=None, known_artists=None):
            threads_seen.add(threading.get_ident())
            return _FakeDownloader().download(url, target_dir=target_dir)

    bridge = DownloadBridge(_RecordingDownloader(), library, playlist_repository)
    added: list[int] = []
    bridge.trackAdded.connect(added.append)
    bridge.addToPlaylist(VIDEO_URL, playlist.id)
    assert _pump_until(lambda: bool(added))

    assert threading.get_ident() not in threads_seen


def test_readding_a_song_whose_file_is_already_there_reuses_the_row(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Không được báo "bài đã có" khi file còn sót lại trong thư mục track.

    `file_path` là UNIQUE. Chép một bài vào thư mục track mà ở đó đã có sẵn
    đúng file đó (bản sót từ lần xoá cũ) từng làm việc thêm nổ và báo sai — việc
    đúng là dùng lại chính dòng đang giữ file đó.
    """
    monkeypatch.setenv("XDG_MUSIC_DIR", str(tmp_path / "music"))
    conn = db.connect(tmp_path / "library.db")
    library = LibraryBridge(TrackRepository(conn))
    playlists = PlaylistRepository(conn)
    bridge = DownloadBridge(_NeverCalledDownloader(), library, playlists)

    playlist = playlists.create("Cozy")
    folder = paths.track_dir("Cozy")
    folder.mkdir(parents=True, exist_ok=True)
    song_file = folder / "already-there.mp3"
    song_file.write_bytes(b"fake")
    # Dòng đã giữ file, nhưng KHÔNG thuộc track nào (đúng trạng thái sót lại).
    orphan = library.add_track(
        make_track(title="Sót lại", source_id=VIDEO_ID, file_path=str(song_file))
    )

    errors: list[str] = []
    bridge.errorOccurred.connect(errors.append)
    bridge.addToPlaylist(f"https://www.youtube.com/watch?v={VIDEO_ID}", playlist.id)

    assert errors == []
    assert [t.id for t in playlists.tracks(playlist.id)] == [orphan.id]


def test_duplicate_into_van_chep_du_file_y_het_da_nam_san_o_dich(tmp_path: Path) -> None:
    """Khác `copy_into` đúng ở đây, và đây là chỗ CB-036 cần.

    Dòng `tracks` vừa nhân bản cho track thứ hai phải có bản băng của RIÊNG nó:
    `file_path` là UNIQUE, nên trả về đường dẫn của dòng kia là lấp không được.
    """
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source_file = source_dir / "song.mp3"
    source_file.write_bytes(b"real audio bytes")

    ban_sao = duplicate_into(source_file, source_dir)

    assert ban_sao != source_file, "copy_into ở đây sẽ trả về chính file cũ"
    assert ban_sao.read_bytes() == source_file.read_bytes()
    assert source_file.exists(), "bản gốc phải sống sót"
    assert copy_into(source_file, source_dir) == source_file, "còn copy_into thì không"
