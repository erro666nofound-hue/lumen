"""Audio playback through libmpv. Zero Qt — see CLAUDE.md muc 2.

THREADING CONTRACT — read before touching anything here.

mpv runs its own event thread. Every listener callback registered on this
class (`finished`, `failed`) is invoked FROM THAT THREAD, never from the
thread that built the Player. A listener must therefore do nothing but hand
the news over to its own thread; the Qt bridge turns each one into a queued
signal. Never call back into this class from inside a listener — libmpv
serialises commands against its event loop and will deadlock.

Every method here is meant to be called from the owning (Qt main) thread.

Position is deliberately NOT pushed through a listener: mpv fires `time-pos`
dozens of times a second, which would flood the event loop for no gain. The
bridge polls `position_ms` on a timer instead.
"""

from __future__ import annotations

import logging
from typing import Callable, Protocol

from .errors import PlayerError

log = logging.getLogger(__name__)

# The only two end-file reasons that mean "the song ended". Everything else
# (file replaced, core shutting down, stream redirect) is bookkeeping.
_REASON_EOF = 0
_REASON_ERROR = 4

# Whole percent, matching both mpv and config.volume so neither needs converting.
_VOLUME_MIN = 0
_VOLUME_MAX = 100

# mpv rejects speed <= 0 outright (measured: setting 0.0 raises). The UI slider
# still shows a 0x..3x range because that reads naturally to a person; values
# below the floor just clamp here rather than erroring.
_SPEED_MIN = 0.05
_SPEED_MAX = 3.0


class PlayerBackend(Protocol):
    """What the bridge may assume about a playback engine.

    Lets the bridge be tested against a fake with no audio hardware.
    """

    def set_listener(
        self,
        *,
        finished: Callable[[], None] | None = None,
        failed: Callable[[str], None] | None = None,
    ) -> None: ...
    def load(self, path: str, *, autoplay: bool = True) -> None: ...
    def resume(self) -> None: ...
    def pause(self) -> None: ...
    def stop(self) -> None: ...
    def seek_ms(self, position_ms: int) -> None: ...
    def set_volume(self, volume: int) -> None: ...
    def set_speed(self, rate: float) -> None: ...
    def shutdown(self) -> None: ...
    @property
    def position_ms(self) -> int: ...
    @property
    def duration_ms(self) -> int: ...
    @property
    def is_playing(self) -> bool: ...
    @property
    def has_file(self) -> bool: ...
    # No volume/speed getters: PlaybackController is the source of truth for both.


class MpvPlayer:
    """A libmpv instance configured for gapless local audio playback."""

    def __init__(self, *, volume: int = 80, speed: float = 1.0) -> None:
        # Imported here, not at module scope: an import error must surface as a
        # PlayerError the app can show, not as a crash before logging is up.
        try:
            import mpv
        except ImportError as exc:  # pragma: no cover - depends on system packages
            raise PlayerError(
                f"python-mpv is not available: {exc}",
                user_message="Thiếu thư viện phát nhạc (python-mpv).",
            ) from exc

        self._volume = int(_clamp(volume, _VOLUME_MIN, _VOLUME_MAX))
        self._speed = _clamp(speed, _SPEED_MIN, _SPEED_MAX)
        self._has_file = False
        self._on_finished: Callable[[], None] | None = None
        self._on_failed: Callable[[str], None] | None = None

        try:
            self._mpv = mpv.MPV(
                video="no",          # audio only; also stops embedded cover art
                ytdl=False,          # Lumen downloads its own files; mpv must not fetch
                idle="yes",          # stay alive between songs instead of shutting down
                audio_display="no",
                volume=self._volume,
                speed=self._speed,
                log_handler=_log_from_mpv,
                loglevel="error",
            )
        except Exception as exc:
            raise PlayerError(
                f"Cannot start libmpv: {exc}",
                user_message="Không khởi động được trình phát nhạc.",
            ) from exc

        # Registered once, for the lifetime of the instance. Runs on mpv's thread.
        @self._mpv.event_callback("end-file")
        def _on_end_file(event) -> None:  # pragma: no cover - needs a real mpv
            self._handle_end_file(event)

        self._end_file_handler = _on_end_file
        log.info("libmpv ready (%s)", self._mpv.mpv_version)

    # -- listener -------------------------------------------------------------

    def set_listener(
        self,
        *,
        finished: Callable[[], None] | None = None,
        failed: Callable[[str], None] | None = None,
    ) -> None:
        """Register the callbacks invoked from mpv's thread. See module docstring."""
        self._on_finished = finished
        self._on_failed = failed

    def _handle_end_file(self, event) -> None:
        """Translate an mpv end-file event into at most one listener call."""
        reason = getattr(event.data, "reason", None)
        if reason == _REASON_EOF:
            self._has_file = False
            if self._on_finished is not None:
                self._on_finished()
        elif reason == _REASON_ERROR:
            self._has_file = False
            if self._on_failed is not None:
                self._on_failed("Không phát được file này.")
        # Any other reason: file replaced or core going down — do not advance.

    # -- transport ------------------------------------------------------------

    def load(self, path: str, *, autoplay: bool = True) -> None:
        """Load a local audio file, replacing whatever was playing."""
        try:
            # Pause is set BEFORE loadfile so a preloaded file stays silent.
            self._mpv.pause = not autoplay
            self._mpv.play(path)
            self._has_file = True
        except Exception as exc:
            self._has_file = False
            raise PlayerError(
                f"Cannot load {path!r}: {exc}", user_message="Không mở được file nhạc."
            ) from exc

    def resume(self) -> None:
        """Unpause. Does nothing when no file is loaded."""
        if not self._has_file:
            return
        self._set("pause", False)

    def pause(self) -> None:
        """Pause playback, keeping the file and position."""
        if not self._has_file:
            return
        self._set("pause", True)

    def stop(self) -> None:
        """Unload the current file. Fires no finished callback."""
        self._has_file = False
        try:
            self._mpv.command("stop")
        except Exception:
            log.exception("mpv stop failed")

    def seek_ms(self, position_ms: int) -> None:
        """Jump to an absolute position in the current file."""
        if not self._has_file:
            return
        target = max(0, position_ms) / 1000.0
        try:
            self._mpv.seek(target, reference="absolute")
        except Exception:
            # A seek past the end, or one issued while the file is still
            # opening, is not worth tearing the app down over.
            log.warning("Seek to %d ms failed", position_ms, exc_info=True)

    def set_volume(self, volume: int) -> None:
        """Set output volume as a whole percentage, 0..100."""
        self._volume = int(_clamp(volume, _VOLUME_MIN, _VOLUME_MAX))
        self._set("volume", self._volume)

    def set_speed(self, rate: float) -> None:
        """Set playback rate. See _SPEED_MIN for why 0 is not accepted."""
        self._speed = _clamp(rate, _SPEED_MIN, _SPEED_MAX)
        self._set("speed", self._speed)

    def shutdown(self) -> None:
        """Terminate the mpv core. Safe to call twice; never call from a listener."""
        self._on_finished = None
        self._on_failed = None
        self._has_file = False
        try:
            self._mpv.terminate()
        except Exception:
            log.exception("mpv terminate failed")

    # -- state ----------------------------------------------------------------

    @property
    def position_ms(self) -> int:
        return _seconds_to_ms(self._get("time_pos"))

    @property
    def duration_ms(self) -> int:
        return _seconds_to_ms(self._get("duration"))

    @property
    def is_playing(self) -> bool:
        return self._has_file and not bool(self._get("pause"))

    @property
    def has_file(self) -> bool:
        return self._has_file

    # -- mpv access -----------------------------------------------------------

    def _get(self, name: str) -> object | None:
        """Read an mpv property, returning None instead of raising when unavailable."""
        try:
            return getattr(self._mpv, name)
        except Exception:
            return None  # reading time-pos/duration while idle legitimately fails

    def _set(self, name: str, value: object) -> None:
        """Write an mpv property, logging rather than raising on failure."""
        try:
            setattr(self._mpv, name, value)
        except Exception:
            log.warning("Cannot set mpv property %s=%r", name, value, exc_info=True)


def _clamp(value: float, lo: float, hi: float) -> float:
    """Clamp value into [lo, hi]. Shared by volume and speed, same shape."""
    return max(lo, min(hi, value))


def _seconds_to_ms(value: object | None) -> int:
    """Convert an mpv float-seconds property into whole milliseconds, 0 when unset."""
    if not isinstance(value, (int, float)):
        return 0
    return max(0, int(value * 1000))


def _log_from_mpv(level: str, component: str, message: str) -> None:  # pragma: no cover
    """Route libmpv's own log lines into the app log instead of stderr."""
    log.debug("mpv[%s/%s] %s", level, component, message.strip())
