"""Regressions for three selection bugs found by reading TrackSongsBridge.

All three come from the same confusion: the model keeps TWO lists — every song
in the track, and the subset the search box currently shows. Selection and the
delete-confirmation dialog must talk about the FULL list; only the grid talks
about the filtered one. Getting that backwards silently loses selections or,
worse, deletes more songs than the warning listed.
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
def wired(tmp_path: Path) -> tuple[TrackSongsBridge, PlaylistRepository, TrackRepository, list[int]]:
    """A bridge on an open track holding Alpha / Beta / Gamma, in that order."""
    conn = db.connect(tmp_path / "library.db")
    playlists, tracks = PlaylistRepository(conn), TrackRepository(conn)
    playlist = playlists.create("Selection")
    ids = [tracks.add(make_track(title=name)).id for name in ("Alpha", "Beta", "Gamma")]
    for track_id in ids:
        playlists.add_track(playlist.id, track_id)
    bridge = TrackSongsBridge(playlists, tracks)
    bridge.setPlaylist(playlist.id)
    # Strong references: a collected bridge silently reports default values.
    bridge._kept = (conn, playlists, tracks)
    return bridge, playlists, tracks, ids


class TestSelectionSurvivesSearch:
    def test_selection_survives_being_filtered_out(self, qapp, wired) -> None:
        bridge, _playlists, _tracks, ids = wired
        bridge.setSelectionMode(True)
        bridge.toggleSelected(ids[0])   # Alpha
        bridge.toggleSelected(ids[2])   # Gamma
        assert bridge.selectedCount == 2

        bridge.setSearch("beta")        # hides both selected songs
        assert bridge.count == 1
        assert bridge.selectedCount == 2, "typing in the search box must not deselect songs"

        bridge.setSearch("")
        assert bridge.selectedCount == 2

    def test_selection_dropped_when_song_really_leaves_the_track(self, qapp, wired) -> None:
        """The intersection still has to do its real job: forget departed songs."""
        bridge, playlists, _tracks, ids = wired
        bridge.setSelectionMode(True)
        bridge.toggleSelected(ids[0])
        assert bridge.selectedCount == 1

        playlists.remove_track(bridge.playlistId, ids[0])
        bridge.refresh()

        assert bridge.selectedCount == 0


class TestConfirmDialogListsWhatItDeletes:
    def test_selected_titles_include_songs_hidden_by_search(self, qapp, wired) -> None:
        bridge, _playlists, _tracks, ids = wired
        bridge.setSelectionMode(True)
        bridge.toggleSelected(ids[0])   # Alpha
        bridge.toggleSelected(ids[2])   # Gamma
        bridge.setSearch("beta")        # both selections now hidden

        assert sorted(bridge.selectedTitles()) == ["Alpha", "Gamma"]

    def test_removal_count_matches_what_the_dialog_listed(self, qapp, wired) -> None:
        """The warning and the deletion must never disagree — that is the whole point."""
        bridge, _playlists, _tracks, ids = wired
        bridge.setSelectionMode(True)
        bridge.toggleSelected(ids[0])
        bridge.toggleSelected(ids[2])
        bridge.setSearch("beta")

        listed = bridge.selectedTitles()
        removed = bridge.removeSelected()

        assert removed == len(listed) == 2


class TestToggleSelectedIgnoresStrangers:
    def test_unknown_id_is_not_selectable(self, qapp, wired) -> None:
        bridge, _playlists, _tracks, _ids = wired
        bridge.setSelectionMode(True)
        bridge.toggleSelected(999_999)
        assert bridge.selectedCount == 0

    def test_nothing_selectable_with_no_open_track(self, qapp, tmp_path: Path) -> None:
        conn = db.connect(tmp_path / "empty.db")
        bridge = TrackSongsBridge(PlaylistRepository(conn), TrackRepository(conn))
        bridge.toggleSelected(1)
        assert bridge.selectedCount == 0
