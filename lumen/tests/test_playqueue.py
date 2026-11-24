"""Tests for the PlayQueue: basic state, properties, set_items, jump_to, clear."""

from __future__ import annotations

import pytest

from lumen.core.playqueue import PlayQueue, RepeatMode


class TestPlayQueueBasics:
	"""Basic state and property tests."""

	def test_empty_queue_properties(self) -> None:
		"""An empty queue has zero count and None current track."""
		queue = PlayQueue()
		assert queue.count == 0
		assert queue.current_id is None
		assert queue.current_index == -1
		assert queue.ids == ()

	def test_set_items_single_track(self) -> None:
		"""Setting a single track makes it the current track."""
		queue = PlayQueue()
		result = queue.set_items([42])
		assert result == 42
		assert queue.current_id == 42
		assert queue.current_index == 0
		assert queue.count == 1
		assert queue.ids == (42,)

	def test_set_items_multiple_tracks(self) -> None:
		"""Setting multiple tracks preserves order and starts at first."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30, 40])
		assert queue.ids == (10, 20, 30, 40)
		assert queue.current_id == 10
		assert queue.current_index == 0
		assert queue.count == 4

	def test_set_items_removes_duplicates(self) -> None:
		"""Duplicates are removed, keeping first occurrence."""
		queue = PlayQueue()
		queue.set_items([10, 20, 10, 30, 20, 40])
		assert queue.ids == (10, 20, 30, 40)
		assert queue.current_id == 10

	def test_set_items_with_start_id(self) -> None:
		"""start_id parameter sets which track is current."""
		queue = PlayQueue()
		result = queue.set_items([10, 20, 30, 40], start_id=30)
		assert result == 30
		assert queue.current_id == 30
		assert queue.current_index == 2

	def test_set_items_with_invalid_start_id(self) -> None:
		"""Invalid start_id falls back to first track."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30], start_id=99)
		assert queue.current_id == 10

	def test_set_items_with_none_start_id(self) -> None:
		"""None start_id starts at first track."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30], start_id=None)
		assert queue.current_id == 10

	def test_set_items_returns_none_for_empty(self) -> None:
		"""Setting empty list returns None."""
		queue = PlayQueue()
		result = queue.set_items([])
		assert result is None
		assert queue.count == 0


class TestJumpTo:
	"""Tests for jump_to() method."""

	def test_jump_to_valid_track(self) -> None:
		"""jump_to() with valid track ID changes current."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30, 40])
		result = queue.jump_to(30)
		assert result == 30
		assert queue.current_id == 30

	def test_jump_to_invalid_track(self) -> None:
		"""jump_to() with invalid track ID returns None and doesn't change current."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30])
		result = queue.jump_to(99)
		assert result is None
		assert queue.current_id == 10

	def test_jump_to_same_track(self) -> None:
		"""Jumping to current track works."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30])
		queue._pos = 1
		result = queue.jump_to(20)
		assert result == 20
		assert queue.current_id == 20

	def test_jump_to_with_shuffle(self) -> None:
		"""jump_to works correctly when shuffle is on."""
		queue = PlayQueue()
		queue.shuffle = True
		queue.set_items([10, 20, 30, 40, 50], start_id=10)
		result = queue.jump_to(40)
		assert result == 40
		assert queue.current_id == 40


class TestClear:
	"""Tests for the clear() method."""

	def test_clear_empty_queue(self) -> None:
		"""Clearing an empty queue is safe."""
		queue = PlayQueue()
		queue.clear()
		assert queue.count == 0
		assert queue.current_id is None

	def test_clear_non_empty_queue(self) -> None:
		"""Clearing removes all tracks."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30, 40])
		queue.clear()
		assert queue.count == 0
		assert queue.current_id is None
		assert queue.ids == ()

	def test_clear_resets_shuffle_state(self) -> None:
		"""After clear, shuffle state is preserved but queue is empty."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30])
		queue.shuffle = True
		queue.clear()
		assert queue.shuffle is True
		assert queue.count == 0


class TestRepeatProperty:
	"""Tests for the repeat property."""

	def test_repeat_default_is_off(self) -> None:
		"""Default repeat mode is OFF."""
		queue = PlayQueue()
		assert queue.repeat == RepeatMode.OFF

	def test_repeat_can_be_set(self) -> None:
		"""Repeat mode can be changed."""
		queue = PlayQueue()
		queue.repeat = RepeatMode.ALL
		assert queue.repeat == RepeatMode.ALL
		queue.repeat = RepeatMode.ONE
		assert queue.repeat == RepeatMode.ONE


class TestShuffleProperty:
	"""Tests for the shuffle property."""

	def test_shuffle_default_is_false(self) -> None:
		"""Default shuffle is off."""
		queue = PlayQueue()
		assert queue.shuffle is False

	def test_shuffle_can_be_set(self) -> None:
		"""Shuffle can be toggled."""
		queue = PlayQueue()
		queue.shuffle = True
		assert queue.shuffle is True
		queue.shuffle = False
		assert queue.shuffle is False
