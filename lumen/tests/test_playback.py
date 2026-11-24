"""Tests for PlaybackController with a fake backend (no audio hardware needed)."""

from __future__ import annotations

import pytest

from lumen.core.playback import PlaybackController
from lumen.core.playqueue import PlayQueue
from tests.conftest import FakeBackend, make_track


@pytest.fixture
def backend() -> FakeBackend:
    return FakeBackend()


@pytest.fixture
def queue() -> PlayQueue:
    return PlayQueue()


@pytest.fixture
def controller(backend: FakeBackend, queue: PlayQueue) -> PlaybackController:
    c = PlaybackController(backend, queue=queue, volume=80)
    backend.calls.clear()  # Clear init calls before test runs
    return c


class TestPlaybackStart:
    def test_start_loads_track_and_sets_state(self, controller: PlaybackController, backend: FakeBackend) -> None:
        track = make_track(title="Test Song", duration_ms=180_000)
        controller.start(track)

        assert backend.calls[0] == ("load", track.file_path, True)
        assert controller.track is track
        assert controller.playing is True
        assert controller.position_ms == 0
        assert controller.duration_ms == 180_000


class TestPlaybackToggle:
    def test_toggle_returns_false_when_no_track(self, controller: PlaybackController) -> None:
        result = controller.toggle()
        assert result is False
        assert controller.playing is False

    def test_toggle_pauses_when_playing(self, controller: PlaybackController, backend: FakeBackend) -> None:
        track = make_track()
        controller.start(track)
        backend.calls.clear()

        result = controller.toggle()

        assert result is False
        assert controller.playing is False
        assert ("pause",) in backend.calls

    def test_toggle_resumes_when_paused(self, controller: PlaybackController, backend: FakeBackend) -> None:
        track = make_track()
        controller.start(track)
        controller.toggle()  # pause
        backend.calls.clear()

        result = controller.toggle()

        assert result is True
        assert controller.playing is True
        assert ("resume",) in backend.calls


class TestPlaybackPoll:
    def test_poll_returns_false_when_nothing_changed(self, controller: PlaybackController) -> None:
        track = make_track(duration_ms=180_000)
        controller.start(track)
        changed = controller.poll()
        assert changed is False

    def test_poll_detects_position_change(self, controller: PlaybackController, backend: FakeBackend) -> None:
        track = make_track()
        controller.start(track)
        backend.set_state(position_ms=5_000)

        changed = controller.poll()

        assert changed is True
        assert controller.position_ms == 5_000

    def test_poll_detects_duration_change(self, controller: PlaybackController, backend: FakeBackend) -> None:
        track = make_track(duration_ms=180_000)
        controller.start(track)
        backend.set_state(duration_ms=182_500)

        changed = controller.poll()

        assert changed is True
        assert controller.duration_ms == 182_500

    def test_poll_keeps_old_duration_when_backend_returns_zero(
        self, controller: PlaybackController, backend: FakeBackend
    ) -> None:
        """mpv returns 0 for duration while still decoding; should not reset."""
        track = make_track(duration_ms=180_000)
        controller.start(track)
        backend.set_state(duration_ms=0)

        controller.poll()

        assert controller.duration_ms == 180_000


class TestPlaybackSeek:
    def test_seek_updates_position_immediately(self, controller: PlaybackController, backend: FakeBackend) -> None:
        track = make_track()
        controller.start(track)

        controller.seek(30_000)

        assert controller.position_ms == 30_000
        assert ("seek", 30_000) in backend.calls

    def test_seek_clamps_negative_position(self, controller: PlaybackController) -> None:
        track = make_track()
        controller.start(track)

        controller.seek(-5_000)

        assert controller.position_ms == 0

    def test_seek_without_track_does_nothing(self, controller: PlaybackController, backend: FakeBackend) -> None:
        controller.seek(10_000)

        assert backend.calls == []


class TestPlaybackVolume:
    def test_set_volume_returns_true_when_changed(self, controller: PlaybackController) -> None:
        result = controller.set_volume(50)
        assert result is True
        assert controller.volume == 50

    def test_set_volume_returns_false_when_same(self, controller: PlaybackController) -> None:
        result = controller.set_volume(80)
        assert result is False

    def test_set_volume_clamps_to_range(self, controller: PlaybackController) -> None:
        controller.set_volume(150)
        assert controller.volume == 100

        controller.set_volume(-10)
        assert controller.volume == 0


class TestPlaybackSpeed:
    def test_set_speed_returns_true_when_changed(self, controller: PlaybackController) -> None:
        result = controller.set_speed(1.5)
        assert result is True
        assert controller.speed == 1.5

    def test_set_speed_returns_false_when_same(self, controller: PlaybackController) -> None:
        result = controller.set_speed(1.0)
        assert result is False

    def test_set_speed_clamps_to_range(self, controller: PlaybackController) -> None:
        controller.set_speed(10.0)
        assert controller.speed == 3.0

        controller.set_speed(-1.0)
        assert controller.speed == 0.0

    def test_set_speed_calls_backend(self, controller: PlaybackController, backend: FakeBackend) -> None:
        controller.set_speed(2.0)
        assert ("speed", 2.0) in backend.calls

    def test_init_applies_initial_speed_to_backend(self, backend: FakeBackend, queue: PlayQueue) -> None:
        PlaybackController(backend, queue=queue, speed=1.75)
        assert ("speed", 1.75) in backend.calls


class TestPlaybackStop:
    def test_stop_clears_state(self, controller: PlaybackController, backend: FakeBackend) -> None:
        track = make_track()
        controller.start(track)
        controller._position_ms = 50_000

        controller.stop()

        assert controller.track is None
        assert controller.playing is False
        assert controller.position_ms == 0
        assert ("stop",) in backend.calls


class TestPlaybackQueue:
    def test_set_queue_replaces_items(self, controller: PlaybackController) -> None:
        ids = [1, 2, 3]
        start_id = controller.set_queue(ids, start_id=2)

        assert start_id == 2
        assert controller.queue.ids == (1, 2, 3)

    def test_drop_track_removes_from_queue(self, controller: PlaybackController) -> None:
        ids = [1, 2, 3]
        controller.set_queue(ids)
        controller.drop(2)

        assert 2 not in controller.queue.ids


class TestRenameThePlayingTrack:
    """Bản sao Track ở đây phải theo được tên mới, mà chỉ đúng ô `display_name`."""

    def test_doi_ten_bai_dang_phat(self, controller: PlaybackController) -> None:
        controller.start(make_track(id=7, title="ten cu"))

        assert controller.rename(7, "ten moi") is True
        assert controller.track.title == "ten moi"

    def test_khong_dung_toi_ten_that_cua_youtube(self, controller: PlaybackController) -> None:
        """`real_name` là của YouTube, lần tải lại sau còn làm mới nó (QĐ-019)."""
        controller.start(make_track(id=7, title="ten cu"))

        controller.rename(7, "ten moi")

        assert controller.track.real_name == "ten cu"
        assert controller.track.display_name == "ten moi"

    def test_bai_khac_thi_tra_ve_False(self, controller: PlaybackController) -> None:
        controller.start(make_track(id=7, title="ten cu"))

        assert controller.rename(8, "ten moi") is False
        assert controller.track.title == "ten cu"

    def test_khong_phat_gi_thi_tra_ve_False(self, controller: PlaybackController) -> None:
        assert controller.rename(7, "ten moi") is False
