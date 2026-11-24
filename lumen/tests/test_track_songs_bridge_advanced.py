"""Advanced tests for TrackSongsBridge: removal and playing track highlight.

This file tests removal of tracks from playlists and highlighting the
currently playing track.
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
def bridge(repo: PlaylistRepository, track_repo: TrackRepository) -> TrackSongsBridge:
    bridge = TrackSongsBridge(repo, track_repo)
    # Keep strong references to prevent garbage collection
    bridge._kept_repo = repo
    return bridge


class TestTrackSongsSearch:
    """Test filtering by title and artist."""

    def test_set_search_filters_by_title(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        playlist = repo.create("SearchTest")
        t1 = track_repo.add(make_track(title="Apples"))
        t2 = track_repo.add(make_track(title="Bananas"))
        repo.add_track(playlist.id, t1.id)
        repo.add_track(playlist.id, t2.id)

        bridge.setPlaylist(playlist.id)
        bridge.setSearch("Apples")

        assert bridge.count == 1
        ids = bridge.orderedIds()
        assert ids == [t1.id]

    def test_set_search_filters_by_artist(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        playlist = repo.create("ArtistSearch")
        # `source_id` là BẮT BUỘC ở đây: bài không có nó là bài nhập từ đĩa, và
        # cột tác giả của bài đó luôn là "Custom mp3" chứ không phải tag (QĐ-025).
        t1 = track_repo.add(make_track(title="Song1", artist="Beatles", source_id="beatles1"))
        t2 = track_repo.add(make_track(title="Song2", artist="Rolling Stones", source_id="stones1"))
        repo.add_track(playlist.id, t1.id)
        repo.add_track(playlist.id, t2.id)

        bridge.setPlaylist(playlist.id)
        bridge.setSearch("Beatles")

        assert bridge.count == 1

    def test_set_search_case_insensitive(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        playlist = repo.create("CaseTest")
        t = track_repo.add(make_track(title="SHOUTING"))
        repo.add_track(playlist.id, t.id)

        bridge.setPlaylist(playlist.id)
        bridge.setSearch("shouting")

        assert bridge.count == 1

    def test_clear_search_shows_all(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        playlist = repo.create("ClearSearch")
        t1 = track_repo.add(make_track(title="Alice"))
        t2 = track_repo.add(make_track(title="Bob"))
        repo.add_track(playlist.id, t1.id)
        repo.add_track(playlist.id, t2.id)

        bridge.setPlaylist(playlist.id)
        bridge.setSearch("Alice")
        assert bridge.count == 1

        bridge.setSearch("")
        assert bridge.count == 2

    def test_ordered_ids_returns_visible_only(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        playlist = repo.create("FilteredOrder")
        t1 = track_repo.add(make_track(title="Visible"))
        t2 = track_repo.add(make_track(title="Hidden"))
        repo.add_track(playlist.id, t1.id)
        repo.add_track(playlist.id, t2.id)

        bridge.setPlaylist(playlist.id)
        bridge.setSearch("Visible")

        ids = bridge.orderedIds()
        assert ids == [t1.id]


class TestTrackSongsRemovalEdgeCases:
    """Test removal edge cases (see test_track_songs_bridge_removal.py for critical verification)."""

    def test_remove_selected_returns_count(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        playlist = repo.create("CountTest")
        t1 = track_repo.add(make_track(title="Song1"))
        t2 = track_repo.add(make_track(title="Song2"))
        repo.add_track(playlist.id, t1.id)
        repo.add_track(playlist.id, t2.id)

        bridge.setPlaylist(playlist.id)
        bridge.setSelectionMode(True)
        bridge.toggleSelected(t1.id)
        bridge.toggleSelected(t2.id)

        count = bridge.removeSelected()
        assert count == 2

    def test_remove_track_nonexistent_returns_false(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository
    ) -> None:
        playlist = repo.create("NonexistentTest")
        bridge.setPlaylist(playlist.id)

        result = bridge.removeTrack(9999)
        assert result is False

    def test_on_playlist_contents_changed_only_refreshes_current(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        p1 = repo.create("Current")
        p2 = repo.create("Other")
        t1 = track_repo.add(make_track(title="TrackA"))
        repo.add_track(p1.id, t1.id)

        bridge.setPlaylist(p1.id)
        assert bridge.count == 1

        # Add track to p1 via repository
        t2 = track_repo.add(make_track(title="TrackB"))
        repo.add_track(p1.id, t2.id)
        bridge.onPlaylistContentsChanged(p1.id)

        assert bridge.count == 2

    def test_on_playlist_contents_changed_ignores_other_playlists(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        p1 = repo.create("Current")
        p2 = repo.create("Other")
        t1 = track_repo.add(make_track(title="TrackA"))
        repo.add_track(p1.id, t1.id)

        bridge.setPlaylist(p1.id)
        assert bridge.count == 1

        # Add track to p2 (not current)
        t2 = track_repo.add(make_track(title="TrackB"))
        repo.add_track(p2.id, t2.id)
        bridge.onPlaylistContentsChanged(p2.id)

        # p1's count should not change
        assert bridge.count == 1


class TestTrackSongsPlayingHighlight:
    """Test highlighting the currently playing track."""

    def test_set_playing_marks_row(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        playlist = repo.create("PlayingTest")
        t1 = track_repo.add(make_track(title="Song1"))
        t2 = track_repo.add(make_track(title="Song2"))
        repo.add_track(playlist.id, t1.id)
        repo.add_track(playlist.id, t2.id)

        bridge.setPlaylist(playlist.id)
        bridge.set_playing(bridge.playlistId, t1.id)

        # Check via data role
        idx1 = bridge.index(0, 0)
        idx2 = bridge.index(1, 0)
        assert bridge.data(idx1, bridge.IsPlayingRole) is True
        assert bridge.data(idx2, bridge.IsPlayingRole) is False

    def test_set_playing_changes_highlight(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        playlist = repo.create("ChangePlayingTest")
        t1 = track_repo.add(make_track(title="Song1"))
        t2 = track_repo.add(make_track(title="Song2"))
        repo.add_track(playlist.id, t1.id)
        repo.add_track(playlist.id, t2.id)

        bridge.setPlaylist(playlist.id)
        bridge.set_playing(bridge.playlistId, t1.id)

        idx1 = bridge.index(0, 0)
        assert bridge.data(idx1, bridge.IsPlayingRole) is True

        bridge.set_playing(bridge.playlistId, t2.id)
        assert bridge.data(idx1, bridge.IsPlayingRole) is False

        idx2 = bridge.index(1, 0)
        assert bridge.data(idx2, bridge.IsPlayingRole) is True


class TestTrackSongsScopeIsolation:
    """The bug the project owner called "sai nặng": one song, two places, both on fire.

    The same YouTube song exists as a SEPARATE row per track (each track owns its
    folder), but a row can also be shared -- and the library lists everything. So
    the highlight must key on the playback SCOPE as well as the song id.
    """

    def test_same_song_in_other_track_stays_dark(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        song = track_repo.add(make_track(title="Shared"))
        track_a = repo.create("A")
        track_b = repo.create("B")
        repo.add_track(track_a.id, song.id)
        repo.add_track(track_b.id, song.id)

        # Playing inside track A...
        bridge.setPlaylist(track_a.id)
        bridge.set_playing(track_a.id, song.id)
        assert bridge.data(bridge.index(0, 0), bridge.IsPlayingRole) is True

        # ...must leave the very same song dark when track B is opened.
        bridge.setPlaylist(track_b.id)
        assert bridge.data(bridge.index(0, 0), bridge.IsPlayingRole) is False

    def test_returning_to_the_playing_track_lights_up_again(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        song = track_repo.add(make_track(title="Shared"))
        track_a = repo.create("A")
        track_b = repo.create("B")
        repo.add_track(track_a.id, song.id)
        repo.add_track(track_b.id, song.id)

        bridge.setPlaylist(track_a.id)
        bridge.set_playing(track_a.id, song.id)
        bridge.setPlaylist(track_b.id)
        bridge.setPlaylist(track_a.id)

        assert bridge.data(bridge.index(0, 0), bridge.IsPlayingRole) is True

    def test_library_scope_never_lights_a_track(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        # scope -1 = not inside any track (the library, or a preview).
        song = track_repo.add(make_track(title="Shared"))
        playlist = repo.create("A")
        repo.add_track(playlist.id, song.id)

        bridge.setPlaylist(playlist.id)
        bridge.set_playing(-1, song.id)

        assert bridge.data(bridge.index(0, 0), bridge.IsPlayingRole) is False
