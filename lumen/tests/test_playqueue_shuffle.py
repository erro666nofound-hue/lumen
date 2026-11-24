"""Tests for PlayQueue shuffle and remove operations."""

from __future__ import annotations

import random

import pytest

from lumen.core.playqueue import PlayQueue, RepeatMode


class TestShuffleToggle:
	"""Tests for toggling shuffle on and off."""

	def test_shuffle_toggle_keeps_current_track(self) -> None:
		"""Toggling shuffle does not change the current track."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30, 40, 50])
		queue._pos = 2
		original_id = queue.current_id
		queue.shuffle = True
		assert queue.current_id == original_id
		queue.shuffle = False
		assert queue.current_id == original_id

	def test_shuffle_on_randomizes_order(self) -> None:
		"""Enabling shuffle randomizes the play order."""
		queue = PlayQueue()
		rng = random.Random(42)
		queue_with_seed = PlayQueue(rng)
		queue_with_seed.set_items([10, 20, 30, 40, 50])
		original_order = list(queue_with_seed._order)
		queue_with_seed.shuffle = True
		shuffled_order = list(queue_with_seed._order)
		# With seed 42, the order should change and current should stay at index 0
		assert shuffled_order[0] == original_order[0]  # Current stays first
		assert len(shuffled_order) == len(original_order)

	def test_shuffle_off_restores_original_order(self) -> None:
		"""Disabling shuffle returns to original order."""
		queue = PlayQueue(random.Random(42))
		queue.set_items([10, 20, 30, 40])
		queue._pos = 1
		original_current = queue.current_id
		queue.shuffle = True
		queue.shuffle = False
		assert queue.current_id == original_current
		# After turning shuffle off, order should be [0, 1, 2, 3]
		assert queue._order == [0, 1, 2, 3]

	def test_shuffle_off_twice_is_noop(self) -> None:
		"""Toggling shuffle when already off is a no-op."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30])
		queue.shuffle = False
		assert queue.current_id == 10
		assert queue._order == [0, 1, 2]

	def test_shuffle_set_items_with_shuffle_enabled(self) -> None:
		"""set_items with shuffle already enabled creates shuffled queue."""
		queue = PlayQueue(random.Random(42))
		queue.shuffle = True
		queue.set_items([10, 20, 30, 40, 50], start_id=30)
		# Current should be at position 0 in play order
		assert queue.current_id == 30
		assert queue._order[0] == queue._ids.index(30)


class TestRemove:
	"""Tests for the remove() method."""

	def test_remove_track_in_middle(self) -> None:
		"""Removing a non-current track just removes it."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30, 40])
		queue.remove(20)
		assert queue.ids == (10, 30, 40)
		assert queue.current_id == 10

	def test_remove_current_track_advances(self) -> None:
		"""Removing current track moves to next."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30, 40])
		queue.jump_to(20)
		queue.remove(20)
		assert queue.ids == (10, 30, 40)
		assert queue.current_id == 30

	def test_remove_last_track_when_current(self) -> None:
		"""Removing last track when it's current moves to previous."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30])
		queue.jump_to(30)
		queue.remove(30)
		assert queue.ids == (10, 20)
		assert queue.current_id == 20

	def test_remove_making_queue_empty(self) -> None:
		"""Removing the only track empties the queue."""
		queue = PlayQueue()
		queue.set_items([10])
		queue.remove(10)
		assert queue.count == 0
		assert queue.current_id is None

	def test_remove_non_existent_track_is_noop(self) -> None:
		"""Removing a non-existent track doesn't change anything."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30])
		queue.remove(99)
		assert queue.ids == (10, 20, 30)
		assert queue.current_id == 10

	def test_remove_with_shuffle(self) -> None:
		"""Removing works correctly with shuffle."""
		queue = PlayQueue()
		queue.shuffle = True
		queue.set_items([10, 20, 30, 40], start_id=20)
		queue.remove(20)
		assert 20 not in queue.ids
		assert queue.current_id in queue.ids


class TestIntegration:
	"""Integration tests combining multiple features."""

	def test_set_items_preserves_shuffle_state(self) -> None:
		"""set_items produces a shuffled queue if shuffle is enabled."""
		queue = PlayQueue(random.Random(42))
		queue.shuffle = True
		queue.set_items([10, 20, 30, 40, 50])
		# Current should be 10 but in shuffled play order
		assert queue.current_id == 10
		assert queue._order[0] == 0  # First item in play order

	def test_shuffle_then_advance_then_unshuffle(self) -> None:
		"""Advancing with shuffle and then unshuffling preserves position."""
		queue = PlayQueue(random.Random(42))
		queue.set_items([10, 20, 30, 40, 50])
		queue.shuffle = True
		original_current = queue.current_id
		queue.advance()
		advanced_id = queue.current_id
		assert advanced_id != original_current
		queue.shuffle = False
		# After unshuffling, should still be at the advanced track
		assert queue.current_id == advanced_id

	def test_remove_then_jump_to(self) -> None:
		"""Jumping to a track that exists after removal."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30, 40, 50])
		queue.remove(20)
		result = queue.jump_to(40)
		assert result == 40
		assert queue.current_id == 40

	def test_complex_scenario(self) -> None:
		"""Complex usage: set, shuffle, advance, jump, remove, clear."""
		queue = PlayQueue(random.Random(42))
		queue.set_items([1, 2, 3, 4, 5])
		queue.shuffle = True
		assert queue.shuffle is True
		queue.advance()
		queue.jump_to(3)
		queue.remove(2)
		assert 2 not in queue.ids
		queue.clear()
		assert queue.count == 0
