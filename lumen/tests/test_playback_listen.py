"""Tests for PlaybackController listen credit and repeat/shuffle features."""

from __future__ import annotations

import pytest

from lumen.core.playback import PlaybackController, LISTEN_MS
from lumen.core.playqueue import PlayQueue, RepeatMode
from tests.conftest import FakeBackend, make_track


@pytest.fixture
def backend() -> FakeBackend:
    return FakeBackend()


@pytest.fixture
def queue() -> PlayQueue:
    return PlayQueue()


@pytest.fixture
def controller(backend: FakeBackend, queue: PlayQueue) -> PlaybackController:
    return PlaybackController(backend, queue=queue, volume=80)


class TestPlaybackListenCredit:
    def test_listen_credit_returns_none_below_threshold(self, controller: PlaybackController) -> None:
        track = make_track(duration_ms=180_000)
        controller.start(track)
        controller._position_ms = LISTEN_MS - 1

        credit = controller.take_listen_credit()
        assert credit is None

    def test_listen_credit_returns_track_id_at_threshold(self, controller: PlaybackController) -> None:
        track = make_track(duration_ms=180_000, id=42)
        controller.start(track)
        controller._position_ms = LISTEN_MS

        credit = controller.take_listen_credit()
        assert credit == 42

    def test_listen_credit_counts_only_once(self, controller: PlaybackController) -> None:
        track = make_track(duration_ms=180_000, id=42)
        controller.start(track)
        controller._position_ms = LISTEN_MS

        assert controller.take_listen_credit() == 42
        assert controller.take_listen_credit() is None

    def test_listen_credit_resets_on_new_track(self, controller: PlaybackController) -> None:
        track1 = make_track(duration_ms=180_000, id=1)
        controller.start(track1)
        controller._position_ms = LISTEN_MS
        controller.take_listen_credit()

        track2 = make_track(duration_ms=180_000, id=2)
        controller.start(track2)
        controller._position_ms = LISTEN_MS

        assert controller.take_listen_credit() == 2

    def test_listen_credit_half_duration_for_short_tracks(self, controller: PlaybackController) -> None:
        """For a 40-second track, threshold is 20 seconds (half), not 30."""
        track = make_track(duration_ms=40_000, id=99)
        controller.start(track)
        controller._position_ms = 20_000

        credit = controller.take_listen_credit()
        assert credit == 99

    def test_listen_credit_force_skips_threshold(self, controller: PlaybackController) -> None:
        track = make_track(duration_ms=180_000, id=42)
        controller.start(track)
        controller._position_ms = 1_000  # well below threshold

        credit = controller.take_listen_credit(force=True)
        assert credit == 42

    def test_listen_credit_returns_none_when_no_track(self, controller: PlaybackController) -> None:
        credit = controller.take_listen_credit()
        assert credit is None


class TestPlaybackRepeatAndShuffle:
    def test_cycle_repeat_goes_off_all_one(self, controller: PlaybackController) -> None:
        assert controller.repeat == RepeatMode.OFF.value

        controller.cycle_repeat()
        assert controller.repeat == RepeatMode.ALL.value

        controller.cycle_repeat()
        assert controller.repeat == RepeatMode.ONE.value

        controller.cycle_repeat()
        assert controller.repeat == RepeatMode.OFF.value

    def test_toggle_shuffle(self, controller: PlaybackController) -> None:
        assert controller.shuffle is False

        controller.toggle_shuffle()
        assert controller.shuffle is True

        controller.toggle_shuffle()
        assert controller.shuffle is False
