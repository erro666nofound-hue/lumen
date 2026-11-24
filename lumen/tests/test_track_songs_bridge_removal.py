"""Critical tests: TrackSongsBridge removal only affects playlist membership.

⚠️ CRITICAL: removeTrack() and removeSelected() only remove from playlist
membership. They NEVER delete the Track from the library or delete the mp3 file.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402

from lumen.bridge.track_songs_bridge import TrackSongsBridge  # noqa: E402
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
    conn = db.connect(tmp_path / "library.db")
    return TrackRepository(conn)


@pytest.fixture
def bridge(repo: PlaylistRepository) -> TrackSongsBridge:
    bridge = TrackSongsBridge(repo, track_repo)
    bridge._kept_repo = repo
    return bridge


def test_remove_selected_deletes_the_copy_this_track_owned(
    qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
) -> None:
    """removeSelected() removes only from playlist membership, not from library."""
    playlist = repo.create("RemovalTest")
    track = track_repo.add(make_track(title="TestSong"))
    repo.add_track(playlist.id, track.id)

    bridge.setPlaylist(playlist.id)
    bridge.setSelectionMode(True)
    bridge.toggleSelected(track.id)

    removed_count = bridge.removeSelected()
    assert removed_count == 1
    assert bridge.count == 0

    # LUẬT ĐÃ ĐỔI: mỗi track giữ bản sao riêng, nên xoá khỏi track là xoá THẬT.
    # Chỉ gỡ thành viên mà để lại dòng thì tải lại đúng bài đó sẽ va vào bản cũ
    # và báo "bài đã có trong track" — lỗi chủ dự án gặp.
    assert track_repo.get(track.id) is None


def test_remove_track_deletes_the_copy_this_track_owned(
    qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
) -> None:
    """removeTrack() xoá hẳn bản sao mà track này sở hữu."""
    playlist = repo.create("RemovalTest2")
    track = track_repo.add(make_track(title="AnotherSong"))
    repo.add_track(playlist.id, track.id)

    bridge.setPlaylist(playlist.id)
    result = bridge.removeTrack(track.id)

    assert result is True
    assert bridge.count == 0
    assert track_repo.get(track.id) is None


def test_remove_from_one_playlist_leaves_other_playlist_intact(
    qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
) -> None:
    """Removing from p1 doesn't affect the same track in p2."""
    p1 = repo.create("Playlist1")
    p2 = repo.create("Playlist2")
    track = track_repo.add(make_track(title="SharedTrack"))
    repo.add_track(p1.id, track.id)
    repo.add_track(p2.id, track.id)

    bridge.setPlaylist(p1.id)
    bridge.removeTrack(track.id)

    # p1 should not have the track
    assert bridge.count == 0

    # But p2 should still have it
    p2_tracks = repo.tracks(p2.id)
    assert len(p2_tracks) == 1


def test_a_song_shared_with_another_track_is_only_unlisted(
    qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
) -> None:
    """Xoá khỏi track A không được phá track B đang dùng chung dòng đó."""
    a = repo.create("A")
    b = repo.create("B")
    song = track_repo.add(make_track(title="Shared"))
    repo.add_track(a.id, song.id)
    repo.add_track(b.id, song.id)

    bridge.setPlaylist(a.id)
    assert bridge.removeTrack(song.id) is True

    assert track_repo.get(song.id) is not None
    assert [t.id for t in repo.tracks(b.id)] == [song.id]


def test_deleting_then_re_adding_the_same_song_works(
    qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
) -> None:
    """Đúng kịch bản chủ dự án gặp: xoá bài rồi tải lại chính bài đó.

    Trước đây dòng và file mp3 ở lại nên lần thêm sau va vào bản cũ.
    """
    playlist = repo.create("Cozy")
    song = track_repo.add(make_track(title="Song", source_id="vid123"))
    repo.add_track(playlist.id, song.id)

    bridge.setPlaylist(playlist.id)
    bridge.removeTrack(song.id)

    # Không còn dấu vết nào của bài cũ -> thêm lại được y như lần đầu.
    assert [t.source_id for t in repo.tracks(playlist.id)] == []
    fresh = track_repo.add(make_track(title="Song", source_id="vid123"))
    assert repo.add_track(playlist.id, fresh.id) is True
