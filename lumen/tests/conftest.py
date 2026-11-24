from __future__ import annotations

import itertools
import sqlite3
import time
from pathlib import Path
from typing import Callable, Iterator

import pytest

from lumen.core import db
from lumen.core.models import Track
from lumen.core.playqueue import PlayQueue
from lumen.core.repository import PlaylistRepository, TrackRepository

_file_counter = itertools.count(1)


@pytest.fixture(autouse=True)
def _never_touch_the_real_library(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make it IMPOSSIBLE for a test to open the user's real music database.

    `db.connect()` with no argument opens ~/.local/share/lumen/library.db — the
    real thing, with the user's real songs in it. One stray no-arg call from a
    test (or from a throwaway script someone runs with pytest) silently mutates
    it. That has already happened once: four songs vanished from the library
    while their mp3 files sat untouched on disk, and it took a rescan to undo.

    Autouse and unconditional on purpose: a guard you must remember to opt into
    is not a guard. Tests that want a database must pass an explicit path.
    """
    real_connect = db.connect

    def guarded(path: Path | None = None) -> sqlite3.Connection:
        if path is None:
            raise RuntimeError(
                "db.connect() without a path opens the REAL library. "
                "Pass an explicit path, e.g. db.connect(tmp_path / 'library.db')."
            )
        return real_connect(path)

    monkeypatch.setattr(db, "connect", guarded)


def make_track(**overrides: object) -> Track:
    """Build a valid Track with a unique file_path, overridable via kwargs.

    `title=` là BÍ DANH của `real_name=`. Từ v10 một bài mang hai tên (QĐ-019),
    nhưng bài vừa tải về thì chưa ai đặt tên riêng, nên tên nhìn thấy chính là
    tên thật — và 90 chỗ gọi cũ vẫn đọc đúng nghĩa. Test nào cần phân biệt hai
    tên thì truyền thẳng `real_name=` / `display_name=`.
    """
    if "title" in overrides:
        overrides["real_name"] = overrides.pop("title")
    n = next(_file_counter)
    defaults: dict[str, object] = {
        "real_name": f"Track {n}",
        "artist": "Test Artist",
        "duration_ms": 180_000,
        "file_path": f"/music/track-{n}.mp3",
        "added_at": int(time.time()),
    }
    defaults.update(overrides)
    return Track(**defaults)  # type: ignore[arg-type]


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """Provide a migrated SQLite connection backed by a temp-dir database file."""
    connection = db.connect(tmp_path / "library.db")
    yield connection
    connection.close()


@pytest.fixture
def tracks(conn: sqlite3.Connection) -> TrackRepository:
    """Provide a TrackRepository bound to the test connection."""
    return TrackRepository(conn)


@pytest.fixture
def playlists(conn: sqlite3.Connection) -> PlaylistRepository:
    """Provide a PlaylistRepository bound to the test connection."""
    return PlaylistRepository(conn)


class FakeBackend:
    """Fake audio player backend with call tracking for testing PlaybackController."""

    def __init__(self) -> None:
        self._listener_finished: Callable[[], None] | None = None
        self._listener_failed: Callable[[str], None] | None = None
        self._position_ms = 0
        self._duration_ms = 0
        self._is_playing = False
        self._has_file = False
        self._volume = 80
        self._speed = 1.0
        self.calls: list[tuple] = []

    def set_listener(
        self, *, finished: Callable[[], None] | None = None, failed: Callable[[str], None] | None = None
    ) -> None:
        self._listener_finished = finished
        self._listener_failed = failed

    def load(self, path: str, *, autoplay: bool = True) -> None:
        self.calls.append(("load", path, autoplay))
        self._has_file = True
        self._position_ms = 0
        self._is_playing = autoplay

    def resume(self) -> None:
        self.calls.append(("resume",))
        self._is_playing = True

    def pause(self) -> None:
        self.calls.append(("pause",))
        self._is_playing = False

    def stop(self) -> None:
        self.calls.append(("stop",))
        self._has_file = False
        self._is_playing = False

    def seek_ms(self, position_ms: int) -> None:
        self.calls.append(("seek", position_ms))
        self._position_ms = position_ms

    def set_volume(self, volume: int) -> None:
        self.calls.append(("volume", volume))
        self._volume = volume

    def set_speed(self, rate: float) -> None:
        self.calls.append(("speed", rate))
        self._speed = rate

    def shutdown(self) -> None:
        self.calls.append(("shutdown",))

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


@pytest.fixture(autouse=True)
def _never_read_the_real_desktop_palette(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The real dynsle palette must not leak into theme tests; tests opt in by patching."""
    from lumen.core import paths

    monkeypatch.setattr(paths, "dynsle_colors_path", lambda: tmp_path / "no-dynsle" / "colors.json")
