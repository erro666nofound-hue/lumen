"""Tests for PlayerBridge queue navigation, auto-advance, and listen tracking."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402

from lumen.bridge.library_bridge import LibraryBridge  # noqa: E402
from lumen.bridge.player_bridge import PlayerBridge  # noqa: E402
from lumen.core import db  # noqa: E402
from lumen.core.playback import PlaybackController, LISTEN_MS  # noqa: E402
from lumen.core.repository import TrackRepository  # noqa: E402
from tests.conftest import make_track  # noqa: E402


class FakeBackend:
    """Fake audio backend for PlayerBridge queue tests."""

    def __init__(self) -> None:
        self._listener_finished: Callable[[], None] | None = None
        self._listener_failed: Callable[[str], None] | None = None
        self._position_ms = 0
        self._duration_ms = 0
        self._is_playing = False
        self._has_file = False
        self._volume = 80
        self._speed = 1.0

    def set_listener(
        self, *, finished: Callable[[], None] | None = None, failed: Callable[[str], None] | None = None
    ) -> None:
        self._listener_finished = finished
        self._listener_failed = failed

    def load(self, path: str, *, autoplay: bool = True) -> None:
        self._has_file = True
        self._position_ms = 0
        self._is_playing = autoplay

    def resume(self) -> None:
        self._is_playing = True

    def pause(self) -> None:
        self._is_playing = False

    def stop(self) -> None:
        self._has_file = False
        self._is_playing = False

    def seek_ms(self, position_ms: int) -> None:
        self._position_ms = position_ms

    def set_volume(self, volume: int) -> None:
        self._volume = volume

    def set_speed(self, rate: float) -> None:
        self._speed = rate

    def shutdown(self) -> None:
        pass

    @property
    def position_ms(self) -> int:
        return self._position_ms

    @property
    def duration_ms(self) -> int:
        return self._duration_ms

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    @property
    def has_file(self) -> bool:
        return self._has_file

    def set_state(self, position_ms: int = None, duration_ms: int = None, is_playing: bool = None) -> None:
        if position_ms is not None:
            self._position_ms = position_ms
        if duration_ms is not None:
            self._duration_ms = duration_ms
        if is_playing is not None:
            self._is_playing = is_playing

    def emit_finished(self) -> None:
        if self._listener_finished is not None:
            self._listener_finished()

    def emit_failed(self, message: str) -> None:
        if self._listener_failed is not None:
            self._listener_failed(message)


@pytest.fixture(scope="module")
def qapp() -> QGuiApplication:
    return QGuiApplication.instance() or QGuiApplication([])


@pytest.fixture
def library(tmp_path: Path) -> LibraryBridge:
    conn = db.connect(tmp_path / "library.db")
    return LibraryBridge(TrackRepository(conn))


@pytest.fixture
def backend() -> FakeBackend:
    return FakeBackend()


@pytest.fixture
def player_bridge(backend: FakeBackend, library: LibraryBridge) -> PlayerBridge:
    controller = PlaybackController(backend, volume=80)
    bridge = PlayerBridge(controller, library)
    bridge._kept_backend = backend
    bridge._kept_library = library
    return bridge


class TestPlayerBridgeAutoAdvance:
    def test_finish_advances_to_next_track(
        self, qapp, player_bridge: PlayerBridge, library: LibraryBridge, tmp_path: Path
    ) -> None:
        track2 = make_track(file_path=str(tmp_path / "track2.mp3"))
        track1 = make_track(file_path=str(tmp_path / "track1.mp3"))
        (tmp_path / "track1.mp3").write_bytes(b"fake")
        (tmp_path / "track2.mp3").write_bytes(b"fake")
        stored2 = library.add_track(track2)
        stored1 = library.add_track(track1)

        player_bridge.playPlaylist(1, library.ordered_track_ids(), stored1.id)
        backend = player_bridge._controller._backend
        assert isinstance(backend, FakeBackend)

        backend.emit_finished()
        QGuiApplication.processEvents()

        assert player_bridge.trackId == stored2.id

    def test_finish_with_repeat_off_stops_at_end(
        self, qapp, player_bridge: PlayerBridge, library: LibraryBridge, tmp_path: Path
    ) -> None:
        track = make_track(file_path=str(tmp_path / "only.mp3"))
        (tmp_path / "only.mp3").write_bytes(b"fake")
        stored = library.add_track(track)

        player_bridge.playPlaylist(1, library.ordered_track_ids(), stored.id)
        player_bridge._controller.cycle_repeat()
        player_bridge._controller.cycle_repeat()
        player_bridge._controller.cycle_repeat()

        backend = player_bridge._controller._backend
        assert isinstance(backend, FakeBackend)
        backend.emit_finished()
        QGuiApplication.processEvents()

        assert player_bridge.isPlaying is False
        assert player_bridge.hasTrack is True


class TestPlayerBridgeListenCredit:
    def test_listen_counted_at_threshold(
        self, qapp, player_bridge: PlayerBridge, library: LibraryBridge, tmp_path: Path
    ) -> None:
        track = make_track(duration_ms=180_000, file_path=str(tmp_path / "test.mp3"))
        (tmp_path / "test.mp3").write_bytes(b"fake")
        stored = library.add_track(track)

        player_bridge.playPlaylist(1, library.ordered_track_ids(), stored.id)
        player_bridge._controller._position_ms = LISTEN_MS

        player_bridge._creditListen()

        updated = library.track_for(stored.id)
        assert updated is not None
        assert updated.play_count == 1

    def test_listen_only_credited_once(
        self, qapp, player_bridge: PlayerBridge, library: LibraryBridge, tmp_path: Path
    ) -> None:
        track = make_track(duration_ms=180_000, file_path=str(tmp_path / "test.mp3"))
        (tmp_path / "test.mp3").write_bytes(b"fake")
        stored = library.add_track(track)

        player_bridge.playPlaylist(1, library.ordered_track_ids(), stored.id)
        player_bridge._controller._position_ms = LISTEN_MS

        player_bridge._creditListen()
        player_bridge._creditListen()

        updated = library.track_for(stored.id)
        assert updated is not None
        assert updated.play_count == 1


class TestPlayerBridgeTrackRemoved:
    def test_removed_track_stops_playback_if_current(
        self, qapp, player_bridge: PlayerBridge, library: LibraryBridge, tmp_path: Path
    ) -> None:
        track = make_track(file_path=str(tmp_path / "test.mp3"))
        (tmp_path / "test.mp3").write_bytes(b"fake")
        stored = library.add_track(track)

        player_bridge.playPlaylist(1, library.ordered_track_ids(), stored.id)
        library.removeTrack(stored.id)

        assert player_bridge.hasTrack is False

    def test_removed_track_advances_if_not_current(
        self, qapp, player_bridge: PlayerBridge, library: LibraryBridge, tmp_path: Path
    ) -> None:
        track1 = make_track(file_path=str(tmp_path / "track1.mp3"))
        track2 = make_track(file_path=str(tmp_path / "track2.mp3"))
        (tmp_path / "track1.mp3").write_bytes(b"fake")
        (tmp_path / "track2.mp3").write_bytes(b"fake")
        stored1 = library.add_track(track1)
        stored2 = library.add_track(track2)

        player_bridge.playPlaylist(1, library.ordered_track_ids(), stored1.id)
        initial_id = player_bridge.trackId

        library.removeTrack(stored2.id)

        assert player_bridge.trackId == initial_id


class TestPlayerBridgeReorder:
    """Kéo đổi thứ tự trong track đang phát -> hàng đợi đi theo, nhạc không đứt."""

    def _three_songs(self, library: LibraryBridge, tmp_path: Path) -> list[int]:
        ids = []
        for name in ("mot", "hai", "ba"):
            (tmp_path / f"{name}.mp3").write_bytes(b"fake")
            stored = library.add_track(
                make_track(title=name, file_path=str(tmp_path / f"{name}.mp3"))
            )
            ids.append(stored.id)
        return ids

    def test_the_next_song_follows_the_drag(
        self, qapp, player_bridge: PlayerBridge, library: LibraryBridge, tmp_path: Path
    ) -> None:
        ids = self._three_songs(library, tmp_path)
        player_bridge.playPlaylist(7, ids, ids[0])

        player_bridge.onSongsReordered(7, [ids[0], ids[2], ids[1]])
        backend = player_bridge._controller._backend
        assert isinstance(backend, FakeBackend)
        backend.emit_finished()
        QGuiApplication.processEvents()

        assert player_bridge.trackId == ids[2]

    def test_the_song_playing_right_now_is_not_restarted(
        self, qapp, player_bridge: PlayerBridge, library: LibraryBridge, tmp_path: Path
    ) -> None:
        """Kéo một hàng mà nhạc nhảy về đầu bài thì cú kéo còn tệ hơn lỗi cũ."""
        ids = self._three_songs(library, tmp_path)
        player_bridge.playPlaylist(7, ids, ids[1])
        backend = player_bridge._controller._backend
        assert isinstance(backend, FakeBackend)
        backend.set_state(position_ms=5000)

        player_bridge.onSongsReordered(7, [ids[2], ids[1], ids[0]])

        assert player_bridge.trackId == ids[1]
        assert backend.position_ms == 5000
        # Và con trỏ hàng đợi phải ĐỨNG ĐÚNG bài đang kêu. Dựng lại hàng đợi
        # bằng một phép ĐẶT thì bài đang phát vẫn kêu, nhưng con trỏ nhảy về
        # đầu danh sách — không có gì trên màn hình nói ra, tới lúc hết bài mới
        # lòi: nó phát lại đúng bài vừa nghe xong.
        backend.emit_finished()
        QGuiApplication.processEvents()
        assert player_bridge.trackId == ids[0]

    def test_a_drag_in_another_track_leaves_the_queue_alone(
        self, qapp, player_bridge: PlayerBridge, library: LibraryBridge, tmp_path: Path
    ) -> None:
        """Track đang mở không nhất thiết là track đang phát (xem scopePlaylistId)."""
        ids = self._three_songs(library, tmp_path)
        player_bridge.playPlaylist(7, ids, ids[0])

        player_bridge.onSongsReordered(9, [ids[2], ids[1], ids[0]])
        backend = player_bridge._controller._backend
        assert isinstance(backend, FakeBackend)
        backend.emit_finished()
        QGuiApplication.processEvents()

        assert player_bridge.trackId == ids[1]


class TestUpNextAndJump:
    def _three(self, library: LibraryBridge, tmp_path: Path) -> list[int]:
        ids = []
        for name in ("a", "b", "c"):
            (tmp_path / f"{name}.mp3").write_bytes(b"fake")
            ids.append(library.add_track(make_track(file_path=str(tmp_path / f"{name}.mp3"))).id)
        return ids

    def test_up_next_lists_the_rest_of_the_queue_wrapping_round(
        self, qapp, player_bridge: PlayerBridge, library: LibraryBridge, tmp_path: Path
    ) -> None:
        a, b, c = self._three(library, tmp_path)
        player_bridge.playPlaylist(1, [a, b, c], b)
        assert [row["id"] for row in player_bridge.upNext(5)] == [c, a]
        assert len(player_bridge.upNext(1)) == 1

    def test_jump_to_plays_that_song_and_keeps_the_queue(
        self, qapp, player_bridge: PlayerBridge, library: LibraryBridge, tmp_path: Path
    ) -> None:
        a, b, c = self._three(library, tmp_path)
        player_bridge.playPlaylist(1, [a, b, c], a)
        player_bridge.jumpTo(c)
        assert player_bridge.trackId == c
        assert [row["id"] for row in player_bridge.upNext(5)] == [a, b]
