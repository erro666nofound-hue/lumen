"""Tests for PlaylistsBridge (user-created playlists).

This file tests the Qt model that exposes the sidebar's list of playlists,
with operations to create/rename/delete/add tracks.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402

from lumen.bridge.playlist_bridge import PlaylistsBridge  # noqa: E402
from lumen.core import db  # noqa: E402
from lumen.core.repository import PlaylistRepository, TrackRepository  # noqa: E402
from tests.conftest import make_track  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QGuiApplication:
    return QGuiApplication.instance() or QGuiApplication([])


@pytest.fixture
def repo(tmp_path: Path) -> PlaylistRepository:
    conn = db.connect(tmp_path / "library.db")
    return PlaylistRepository(conn)


@pytest.fixture
def track_repo(tmp_path: Path) -> TrackRepository:
    # Use the same temp database as PlaylistRepository
    conn = db.connect(tmp_path / "library.db")
    return TrackRepository(conn)


@pytest.fixture
def bridge(repo: PlaylistRepository) -> PlaylistsBridge:
    bridge = PlaylistsBridge(repo)
    # Keep strong reference to prevent garbage collection
    bridge._kept_repo = repo
    return bridge


class TestPlaylistsBridgeBasics:
    """Test empty state, count, rowCount."""

    def test_empty_on_init(self, qapp, bridge: PlaylistsBridge) -> None:
        assert bridge.count == 0
        assert bridge.rowCount() == 0

    def test_create_returns_positive_id(self, qapp, bridge: PlaylistsBridge) -> None:
        playlist_id = bridge.create("Gaming")
        assert playlist_id > 0
        assert bridge.count == 1

    def test_create_signal_emitted_once_with_correct_id(self, qapp, bridge: PlaylistsBridge) -> None:
        signals: list[int] = []
        bridge.playlistCreated.connect(signals.append)

        playlist_id = bridge.create("Study")

        assert signals == [playlist_id]

    def test_create_empty_string_returns_minus_one(self, qapp, bridge: PlaylistsBridge) -> None:
        result = bridge.create("")
        assert result == -1
        assert bridge.count == 0

    def test_create_blank_string_returns_minus_one(self, qapp, bridge: PlaylistsBridge) -> None:
        result = bridge.create("   ")
        assert result == -1
        assert bridge.count == 0

    def test_create_blank_emits_error(self, qapp, bridge: PlaylistsBridge) -> None:
        errors: list[str] = []
        bridge.errorOccurred.connect(errors.append)

        bridge.create("")

        assert len(errors) == 1

    def test_create_strips_whitespace(self, qapp, bridge: PlaylistsBridge) -> None:
        playlist_id = bridge.create("  Study  ")
        name = bridge.nameFor(playlist_id)
        assert name == "Study"


class TestPlaylistsBridgeData:
    """Test roleNames, data retrieval, name."""

    def test_name_role_correct(self, qapp, bridge: PlaylistsBridge) -> None:
        playlist_id = bridge.create("Gaming")
        index = bridge.index(0, 0)
        name = bridge.data(index, bridge.NameRole)
        assert name == "Gaming"

    def test_track_count_role_zero_initially(self, qapp, bridge: PlaylistsBridge) -> None:
        playlist_id = bridge.create("Empty")
        index = bridge.index(0, 0)
        track_count = bridge.data(index, bridge.TrackCountRole)
        assert track_count == 0

    def test_nameFor_returns_correct_name(self, qapp, bridge: PlaylistsBridge) -> None:
        playlist_id = bridge.create("Rock")
        name = bridge.nameFor(playlist_id)
        assert name == "Rock"

    def test_nameFor_nonexistent_returns_empty(self, qapp, bridge: PlaylistsBridge) -> None:
        name = bridge.nameFor(9999)
        assert name == ""


class TestPlaylistsBridgeRename:
    """Test rename operation."""

    def test_rename_succeeds(self, qapp, bridge: PlaylistsBridge) -> None:
        playlist_id = bridge.create("OldName")
        result = bridge.rename(playlist_id, "NewName")
        assert result is True
        assert bridge.nameFor(playlist_id) == "NewName"

    def test_rename_blank_returns_false(self, qapp, bridge: PlaylistsBridge) -> None:
        playlist_id = bridge.create("Original")
        result = bridge.rename(playlist_id, "")
        assert result is False
        assert bridge.nameFor(playlist_id) == "Original"

    def test_rename_nonexistent_returns_false(self, qapp, bridge: PlaylistsBridge) -> None:
        result = bridge.rename(9999, "NewName")
        assert result is False


class TestPlaylistsBridgeDuplicateName:
    """F-5 §1: cửa giao diện phải từ chối tên đã có, và NÓI cho người dùng biết."""

    def test_create_trung_ten_tra_ve_am_mot(self, qapp, bridge: PlaylistsBridge) -> None:
        bridge.create("Chill")
        seen: list[str] = []
        bridge.errorOccurred.connect(seen.append)

        assert bridge.create("Chill") == -1
        assert bridge.count == 1
        # Popup ở Sidebar chỉ đóng khi id >= 0, nên id âm là thứ giữ chữ vừa gõ.
        assert seen and "Chill" in seen[0]

    def test_create_khoang_trang_thua_van_bi_bat(self, qapp, bridge: PlaylistsBridge) -> None:
        """Bridge cắt khoảng trắng TRƯỚC khi so, nếu không "Chill " lọt qua cửa."""
        bridge.create("Chill")
        assert bridge.create("  Chill  ") == -1
        assert bridge.count == 1

    def test_rename_trung_ten_tra_ve_false(self, qapp, bridge: PlaylistsBridge) -> None:
        bridge.create("Chill")
        other = bridge.create("Gym")
        seen: list[str] = []
        bridge.errorOccurred.connect(seen.append)

        assert bridge.rename(other, "Chill") is False
        assert bridge.nameFor(other) == "Gym"
        assert seen and "Chill" in seen[0]

    def test_rename_ve_chinh_no_van_true(self, qapp, bridge: PlaylistsBridge) -> None:
        playlist_id = bridge.create("Chill")
        assert bridge.rename(playlist_id, "Chill") is True
        assert bridge.nameFor(playlist_id) == "Chill"


class TestPlaylistsBridgeRemove:
    """Test delete operation."""

    def test_remove_succeeds(self, qapp, bridge: PlaylistsBridge) -> None:
        playlist_id = bridge.create("ToDelete")
        assert bridge.count == 1

        result = bridge.remove(playlist_id)

        assert result is True
        assert bridge.count == 0

    def test_remove_nonexistent_returns_false(self, qapp, bridge: PlaylistsBridge) -> None:
        result = bridge.remove(9999)
        assert result is False

    def test_remove_nonexistent_no_crash(self, qapp, bridge: PlaylistsBridge) -> None:
        # Should not raise an exception
        bridge.remove(9999)


class TestPlaylistsBridgeAddSong:
    """Test adding tracks to playlists.

    CRITICAL: addSong() only adds to playlist membership, it NEVER deletes the Track.
    """

    def test_add_song_first_time_succeeds(
        self, qapp, bridge: PlaylistsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        playlist_id = bridge.create("Music")
        track = track_repo.add(make_track(title="Song A"))

        result = bridge.addSong(playlist_id, track.id)

        assert result is True

    def test_add_song_duplicate_returns_false(
        self, qapp, bridge: PlaylistsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        playlist_id = bridge.create("Music")
        track = track_repo.add(make_track(title="Song B"))
        bridge.addSong(playlist_id, track.id)

        # Add same song again
        result = bridge.addSong(playlist_id, track.id)

        assert result is False

    def test_add_song_duplicate_no_error_signal(
        self, qapp, bridge: PlaylistsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        errors: list[str] = []
        bridge.errorOccurred.connect(errors.append)

        playlist_id = bridge.create("Music")
        track = track_repo.add(make_track(title="Song C"))
        bridge.addSong(playlist_id, track.id)

        # Add same song again
        bridge.addSong(playlist_id, track.id)

        # Should NOT have any error signal (duplicate is not an error condition)
        assert len(errors) == 0

    def test_add_song_increases_track_count(
        self, qapp, bridge: PlaylistsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        playlist_id = bridge.create("Music")
        track = track_repo.add(make_track(title="Song D"))

        bridge.addSong(playlist_id, track.id)

        index = bridge.index(0, 0)
        track_count = bridge.data(index, bridge.TrackCountRole)
        assert track_count == 1

    def test_add_song_emits_contents_changed(
        self, qapp, bridge: PlaylistsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        signals: list[int] = []
        bridge.contentsChanged.connect(signals.append)

        playlist_id = bridge.create("Music")
        track = track_repo.add(make_track(title="Song E"))

        bridge.addSong(playlist_id, track.id)

        assert signals == [playlist_id]


class TestPlaylistRemoveCleansUp:
    """Deleting a track used to leave its rows and its mp3 files behind forever."""

    @pytest.fixture(autouse=True)
    def _fake_music_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # remove() deletes the track's FOLDER, and paths.track_dir() reads the
        # real XDG music dir. Without this the suite would reach into the
        # owner's actual music library (CLAUDE.md forbids it outright).
        monkeypatch.setenv("XDG_MUSIC_DIR", str(tmp_path / "music"))

    def test_remove_deletes_the_songs_and_their_files(
        self, qapp, bridge, repo, track_repo, tmp_path: Path
    ) -> None:
        song_file = tmp_path / "only.mp3"
        song_file.write_bytes(b"fake")
        playlist = repo.create("Solo")
        song = track_repo.add(make_track(title="Only", file_path=str(song_file)))
        repo.add_track(playlist.id, song.id)
        bridge.refresh()

        assert bridge.remove(playlist.id) is True

        assert track_repo.get(song.id) is None
        assert not song_file.exists()

    def test_remove_keeps_a_song_that_lives_in_another_track_too(
        self, qapp, bridge, repo, track_repo, tmp_path: Path
    ) -> None:
        song_file = tmp_path / "shared.mp3"
        song_file.write_bytes(b"fake")
        doomed = repo.create("Doomed")
        keeper = repo.create("Keeper")
        song = track_repo.add(make_track(title="Shared", file_path=str(song_file)))
        repo.add_track(doomed.id, song.id)
        repo.add_track(keeper.id, song.id)
        bridge.refresh()

        bridge.remove(doomed.id)

        assert track_repo.get(song.id) is not None
        assert song_file.exists()

    def test_remove_reports_false_for_a_track_that_is_not_there(self, qapp, bridge) -> None:
        assert bridge.remove(9999) is False


class TestFirstPlayable:
    """Space lúc chưa nạp bài nào chạy track đầu tiên CÓ BÀI, theo thứ tự thanh bên."""

    def test_khong_co_track_nao(self, qapp, bridge: PlaylistsBridge) -> None:
        assert bridge.firstPlayable() == -1

    def test_bo_qua_track_rong(
        self, qapp, bridge: PlaylistsBridge, track_repo: TrackRepository
    ) -> None:
        bridge.create("Rỗng")
        second = bridge.create("Có bài")
        third = bridge.create("Cũng có bài")
        bridge.addSong(second, track_repo.add(make_track(title="Song A")).id)
        bridge.addSong(third, track_repo.add(make_track(title="Song B")).id)

        assert bridge.firstPlayable() == second
