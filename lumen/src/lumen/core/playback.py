"""Playback policy: what is loaded, what plays next, when a listen counts.

Zero Qt (CLAUDE.md muc 2). Everything here is plain Python, so the whole of
Lumen's playback behaviour can be tested with pytest and a fake backend —
no window, no audio device, no mpv.

This class does NOT know the library exists. It is handed whole `Track`
objects and lists of ids by the bridge, which is the only layer allowed to
read the database.
"""

from __future__ import annotations

import logging
from typing import Sequence

from .models import Track
from .player import PlayerBackend
from .playqueue import PlayQueue, RepeatMode

log = logging.getLogger(__name__)

# A listen only counts once the track has really been listened to, not the
# instant it starts. Otherwise skipping through ten songs would teach the
# recommendation engine that you love all ten.
LISTEN_MS = 30_000

REPEAT_CYCLE = (RepeatMode.OFF, RepeatMode.ALL, RepeatMode.ONE)

# The slider goes 0..3 because that reads naturally to a person. The backend
# floors the actual applied rate higher (mpv rejects 0) — see core/player.py.
SPEED_MIN = 0.0
SPEED_MAX = 3.0


class PlaybackController:
    """Owns the audio backend, the play queue, and the current track."""

    def __init__(
        self,
        backend: PlayerBackend,
        *,
        queue: PlayQueue | None = None,
        volume: int = 80,
        speed: float = 1.0,
    ) -> None:
        self._backend = backend
        self._queue = queue if queue is not None else PlayQueue()
        self._track: Track | None = None
        self._playing = False
        self._position_ms = 0
        self._duration_ms = 0
        self._volume = _clamp_percent(volume)
        self._speed = max(SPEED_MIN, min(SPEED_MAX, float(speed)))
        self._listen_credited = False
        backend.set_volume(self._volume)
        backend.set_speed(self._speed)

    # -- state ----------------------------------------------------------------

    @property
    def track(self) -> Track | None:
        return self._track

    @property
    def playing(self) -> bool:
        return self._playing

    @property
    def position_ms(self) -> int:
        return self._position_ms

    @property
    def duration_ms(self) -> int:
        return self._duration_ms

    @property
    def volume(self) -> int:
        return self._volume

    @property
    def speed(self) -> float:
        return self._speed

    @property
    def repeat(self) -> str:
        return self._queue.repeat.value

    @property
    def shuffle(self) -> bool:
        return self._queue.shuffle

    @property
    def queue(self) -> PlayQueue:
        return self._queue

    # -- commands -------------------------------------------------------------

    def set_listener(self, **callbacks: object) -> None:
        """Pass end-of-track callbacks straight to the backend. See core/player.py."""
        self._backend.set_listener(**callbacks)  # type: ignore[arg-type]

    def set_queue(self, ids: Sequence[int], start_id: int | None = None) -> int | None:
        """Replace the queue, returning the id that should play first."""
        return self._queue.set_items(ids, start_id=start_id)

    def reorder_queue(self, ids: Sequence[int]) -> None:
        """Rearrange the queue in place; the song playing right now keeps playing."""
        self._queue.reorder(ids)

    def start(self, track: Track) -> None:
        """Load and play a track. Raises PlayerError when the backend refuses."""
        self._backend.load(track.file_path, autoplay=True)
        self._track = track
        self._playing = True
        self._position_ms = 0
        # The database duration is a placeholder until mpv decodes the real one.
        self._duration_ms = track.duration_ms
        self._listen_credited = False

    def toggle(self) -> bool:
        """Flip play/pause; returns the new playing state."""
        if self._track is None:
            return False
        if self._playing:
            self._backend.pause()
        else:
            self._backend.resume()
        self._playing = not self._playing
        return self._playing

    def next_id(self, *, manual: bool) -> int | None:
        """Id of the next track, or None at the end of the queue."""
        return self._queue.advance(manual=manual)

    def previous_id(self) -> int | None:
        """Id of the previous track, or None when there is nowhere to go back to."""
        return self._queue.go_back()

    def seek(self, position_ms: int) -> None:
        """Jump to an absolute position and show it immediately."""
        if self._track is None:
            return
        # int() is not decoration: QML hands over a JS double, and letting a
        # float leak in makes positionMs (declared int) read back as a float.
        target = max(0, int(position_ms))
        self._backend.seek_ms(target)
        # Shown without waiting for the next poll, so the seek bar does not
        # snap back under the cursor for a quarter of a second.
        self._position_ms = target

    def set_volume(self, percent: int) -> bool:
        """Set volume 0..100; returns True when it actually changed."""
        percent = _clamp_percent(percent)
        if percent == self._volume:
            return False
        self._volume = percent
        self._backend.set_volume(percent)
        return True

    def set_speed(self, rate: float) -> bool:
        """Set playback rate 0..3; returns True when it actually changed."""
        rate = max(SPEED_MIN, min(SPEED_MAX, float(rate)))
        if rate == self._speed:
            return False
        self._speed = rate
        self._backend.set_speed(rate)
        return True

    def cycle_repeat(self) -> None:
        """Step through off -> all -> one."""
        index = REPEAT_CYCLE.index(self._queue.repeat)
        self._queue.repeat = REPEAT_CYCLE[(index + 1) % len(REPEAT_CYCLE)]

    def set_repeat(self, mode: str) -> bool:
        """Set repeat mode directly by name; returns True when it changed.

        Unknown values are ignored rather than raised -- the sidebar's play
        button just wants "turn list-repeat on" without needing to know the
        RepeatMode enum exists.
        """
        try:
            parsed = RepeatMode(mode)
        except ValueError:
            return False
        if parsed == self._queue.repeat:
            return False
        self._queue.repeat = parsed
        return True

    def toggle_shuffle(self) -> None:
        """Shuffle the queue without changing what is playing right now."""
        self._queue.shuffle = not self._queue.shuffle

    def pause_at_end(self) -> None:
        """Stop advancing but keep the last track on display."""
        self._backend.pause()
        self._playing = False

    def stop(self) -> None:
        """Unload the current track and clear all playback state."""
        self._backend.stop()
        self._track = None
        self._playing = False
        self._position_ms = 0
        self._duration_ms = 0
        self._listen_credited = False

    def drop(self, track_id: int) -> None:
        """Forget a track that no longer exists in the library."""
        self._queue.remove(track_id)

    def rename(self, track_id: int, display_name: str) -> bool:
        """Relabel the playing track; returns False when that is not the one playing.

        The controller keeps its OWN copy of the Track, taken when playback
        started, so a rename in the library does not reach it on its own — the
        player bar would keep the old name until the next song. Only
        `display_name` moves: `real_name` belongs to YouTube (QĐ-019), and the
        file on disk is not touched by a rename at all.
        """
        if self._track is None or self._track.id != track_id:
            return False
        self._track.display_name = display_name
        return True

    def fail(self) -> None:
        """Mark playback as stopped after the backend reported an error."""
        self._playing = False

    def shutdown(self) -> None:
        """Tear down the backend. Called once, on app exit."""
        self._backend.shutdown()

    # -- polling --------------------------------------------------------------

    def poll(self) -> bool:
        """Read position/duration off the backend; True when either changed."""
        position = self._backend.position_ms
        duration = self._backend.duration_ms or self._duration_ms
        if position == self._position_ms and duration == self._duration_ms:
            return False
        self._position_ms = position
        self._duration_ms = duration
        return True

    def take_listen_credit(self, *, force: bool = False) -> int | None:
        """Return the track id to count as listened, once — None otherwise.

        `force` is for a track that ended naturally: reaching the end is proof
        enough, whatever the threshold says.
        """
        if self._listen_credited or self._track is None or self._track.id is None:
            return None
        if not force and self._position_ms < self._listen_threshold_ms():
            return None
        self._listen_credited = True
        return self._track.id

    def _listen_threshold_ms(self) -> int:
        """Half the track, capped at LISTEN_MS, so short songs still count."""
        if self._duration_ms <= 0:
            return LISTEN_MS
        return min(LISTEN_MS, self._duration_ms // 2)


def _clamp_percent(value: int) -> int:
    """Clamp a percentage into 0..100."""
    return max(0, min(100, int(value)))
