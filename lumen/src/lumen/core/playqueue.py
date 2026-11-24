from __future__ import annotations

import random
from enum import Enum
from typing import Sequence


class RepeatMode(str, Enum):
    """Playback repeat behavior: OFF (stop at end), ALL (loop), ONE (repeat current)."""

    OFF = "off"
    ALL = "all"
    ONE = "one"


class PlayQueue:
    """Pure-Python play queue with shuffle and repeat modes. Operates only on track IDs."""

    def __init__(self, rng: random.Random | None = None) -> None:
        """Initialize an empty play queue with optional seeded RNG for shuffle tests."""
        self._ids: tuple[int, ...] = ()
        self._order: list[int] = []
        self._pos: int = -1
        self._shuffle: bool = False
        self._repeat: RepeatMode = RepeatMode.OFF
        self._rng = rng if rng is not None else random.Random()

    @property
    def count(self) -> int:
        """Total number of tracks in the queue."""
        return len(self._ids)

    @property
    def current_id(self) -> int | None:
        """Track ID currently playing, or None if queue is empty."""
        if self._pos < 0 or self._pos >= len(self._order):
            return None
        return self._ids[self._order[self._pos]]

    @property
    def current_index(self) -> int:
        """Index of current track in the original list, or -1 if empty."""
        current = self.current_id
        if current is None:
            return -1
        return self._ids.index(current)

    @property
    def ids(self) -> tuple[int, ...]:
        """Original list of track IDs in the order user added them."""
        return self._ids

    @property
    def has_next(self) -> bool:
        """Whether calling advance() would succeed."""
        if not self._ids:
            return False
        if self._repeat == RepeatMode.ALL:
            return True
        if self._pos < len(self._order) - 1:
            return True
        return False

    @property
    def has_previous(self) -> bool:
        """Whether calling go_back() would succeed in changing the current track."""
        if not self._ids:
            return False
        if self._repeat == RepeatMode.ALL:
            return True
        if self._pos > 0:
            return True
        return False

    @property
    def repeat(self) -> RepeatMode:
        """Current repeat mode."""
        return self._repeat

    @repeat.setter
    def repeat(self, value: RepeatMode) -> None:
        """Set the repeat mode."""
        self._repeat = value

    @property
    def shuffle(self) -> bool:
        """Whether shuffle is enabled."""
        return self._shuffle

    @shuffle.setter
    def shuffle(self, enabled: bool) -> None:
        """Enable or disable shuffle without changing the current track."""
        if enabled == self._shuffle:
            return

        if enabled:
            # Turn shuffle ON: randomize the rest of the queue, keep current at index 0
            if self._pos >= 0 and self._order:
                current_idx = self._order[self._pos]
                rest = [idx for i, idx in enumerate(self._order) if i != self._pos]
                self._rng.shuffle(rest)
                self._order = [current_idx] + rest
                self._pos = 0
        else:
            # Turn shuffle OFF: restore original order, keep current as current
            if self._order:
                current_idx = self._order[self._pos]
                self._order = list(range(len(self._ids)))
                self._pos = self._order.index(current_idx)

        self._shuffle = enabled

    def set_items(self, ids: Sequence[int], start_id: int | None = None) -> int | None:
        """Replace the queue with new track IDs. Remove duplicates, keep first occurrence."""
        # Remove duplicates while preserving order (keep first occurrence)
        seen: set[int] = set()
        unique_ids: list[int] = []
        for track_id in ids:
            if track_id not in seen:
                unique_ids.append(track_id)
                seen.add(track_id)

        self._ids = tuple(unique_ids)

        if not self._ids:
            self._order = []
            self._pos = -1
            return None

        # Determine starting track
        if start_id is not None and start_id in self._ids:
            start_idx = self._ids.index(start_id)
        else:
            start_idx = 0

        # Create play order
        if self._shuffle:
            # Shuffle with current track at position 0
            other_indices = [i for i in range(len(self._ids)) if i != start_idx]
            self._rng.shuffle(other_indices)
            self._order = [start_idx] + other_indices
            self._pos = 0
        else:
            self._order = list(range(len(self._ids)))
            self._pos = start_idx

        return self.current_id

    def reorder(self, ids: Sequence[int]) -> None:
        """Rearrange the queue to a new order WITHOUT interrupting the current song.

        `set_items` would do the same job and then some — but it restarts the
        song and, worse, throws away a shuffle sequence the listener is in the
        middle of. Dragging a row in the open track must not stop the music.

        Songs the caller forgot are kept, at the end, in their old order: a
        queue is what is actually playing, and silently dropping a song out of
        it is the kind of loss nobody reports because nobody sees it happen.
        """
        if not self._ids:
            return

        seen: set[int] = set()
        wanted: list[int] = []
        for track_id in ids:
            if track_id in self._ids and track_id not in seen:
                wanted.append(track_id)
                seen.add(track_id)
        leftovers = [i for i in self._ids if i not in seen]
        new_ids = tuple(wanted + leftovers)
        if new_ids == self._ids:
            return

        current = self.current_id
        # `_order` holds indices INTO `_ids`, so moving the ids around under it
        # would silently repoint every step of the shuffle. Read the sequence
        # out as ids first, then look the ids up in their new places.
        shuffled_ids = [self._ids[i] for i in self._order]
        at = {track_id: index for index, track_id in enumerate(new_ids)}
        self._ids = new_ids

        if self._shuffle:
            self._order = [at[i] for i in shuffled_ids if i in at]
        else:
            # Not shuffling means "play them in the order on screen", and the
            # order on screen is exactly what just changed.
            self._order = list(range(len(new_ids)))

        if current is None:
            self._pos = -1 if not self._order else 0
            return
        target = at[current]
        self._pos = self._order.index(target)

    def advance(self, *, manual: bool = False) -> int | None:
        """Move to next track. manual=False means song ended (respect ONE mode)."""
        if not self._ids or self._pos < 0:
            return None

        # Auto-advance when song ends: repeat ONE loops the same song
        if not manual and self._repeat == RepeatMode.ONE:
            return self.current_id

        # Move to next position
        next_pos = self._pos + 1

        if next_pos >= len(self._order):
            # At the end of queue
            if self._repeat == RepeatMode.OFF:
                return None  # Stop, don't change position
            else:  # ALL or ONE
                self._pos = 0
                return self.current_id

        self._pos = next_pos
        return self.current_id

    def go_back(self) -> int | None:
        """Move to previous track, or replay current if at the start."""
        if not self._ids or self._pos < 0:
            return None

        if self._pos == 0:
            # At the start
            if self._repeat == RepeatMode.ALL:
                self._pos = len(self._order) - 1
                return self.current_id
            else:
                # Stay at current (replay from start)
                return self.current_id

        self._pos -= 1
        return self.current_id

    def jump_to(self, track_id: int) -> int | None:
        """Jump to a specific track ID in the queue."""
        if track_id not in self._ids:
            return None

        # Find the track in _ids
        target_idx = self._ids.index(track_id)

        # Find where this track appears in the play order
        try:
            play_pos = self._order.index(target_idx)
            self._pos = play_pos
            return self.current_id
        except ValueError:
            return None

    def remove(self, track_id: int) -> None:
        """Remove a track from the queue. Update current track if needed."""
        if track_id not in self._ids:
            return

        # Find the index to remove
        remove_idx = self._ids.index(track_id)

        # Remove from IDs
        self._ids = tuple(i for i in self._ids if i != track_id)

        if not self._ids:
            self._order = []
            self._pos = -1
            return

        # Update order: remove the index, but adjust all indices > remove_idx
        new_order: list[int] = []
        for idx in self._order:
            if idx == remove_idx:
                continue
            if idx > remove_idx:
                new_order.append(idx - 1)
            else:
                new_order.append(idx)

        self._order = new_order

        # Fix current position
        if self._pos >= len(self._order):
            # Was at or after the end, move to last
            self._pos = len(self._order) - 1
        elif self._pos < 0 and self._order:
            self._pos = 0

    def clear(self) -> None:
        """Remove all tracks from the queue."""
        self._ids = ()
        self._order = []
        self._pos = -1
