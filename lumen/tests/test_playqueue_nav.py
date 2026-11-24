"""Tests for PlayQueue navigation: advance, go_back, has_next/has_previous."""

from __future__ import annotations

import pytest

from lumen.core.playqueue import PlayQueue, RepeatMode


class TestAdvance:
	"""Tests for the advance() method with different repeat modes."""

	def test_advance_normal(self) -> None:
		"""Normal advance moves to next track."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30, 40])
		assert queue.advance() == 20
		assert queue.current_id == 20
		assert queue.advance() == 30
		assert queue.current_id == 30

	def test_advance_manual_false_with_repeat_one_loops(self) -> None:
		"""advance(manual=False) with repeat=ONE loops the same song."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30])
		queue.repeat = RepeatMode.ONE
		assert queue.advance(manual=False) == 10
		assert queue.current_id == 10

	def test_advance_manual_true_with_repeat_one_advances(self) -> None:
		"""advance(manual=True) with repeat=ONE advances even in ONE mode."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30])
		queue.repeat = RepeatMode.ONE
		assert queue.advance(manual=True) == 20
		assert queue.current_id == 20

	def test_advance_off_mode_at_end_returns_none(self) -> None:
		"""advance() at end with repeat=OFF returns None and stays put."""
		queue = PlayQueue()
		queue.set_items([10, 20])
		queue.repeat = RepeatMode.OFF
		queue.advance()  # Move to 20
		result = queue.advance()
		assert result is None
		assert queue.current_id == 20

	def test_advance_all_mode_at_end_wraps(self) -> None:
		"""advance() at end with repeat=ALL wraps to start."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30])
		queue.repeat = RepeatMode.ALL
		queue._pos = 2  # Jump to last
		result = queue.advance()
		assert result == 10
		assert queue.current_id == 10

	def test_advance_one_mode_at_end_wraps(self) -> None:
		"""advance() at end with repeat=ONE and manual=True wraps."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30])
		queue.repeat = RepeatMode.ONE
		queue._pos = 2
		result = queue.advance(manual=True)
		assert result == 10

	def test_advance_on_empty_queue(self) -> None:
		"""advance() on empty queue returns None."""
		queue = PlayQueue()
		assert queue.advance() is None
		assert queue.current_id is None


class TestGoBack:
	"""Tests for the go_back() method."""

	def test_go_back_normal(self) -> None:
		"""go_back() moves to previous track."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30, 40])
		queue._pos = 2
		assert queue.go_back() == 20
		assert queue.current_id == 20

	def test_go_back_at_start_off_mode_replays(self) -> None:
		"""go_back() at start with repeat=OFF replays current track."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30])
		queue.repeat = RepeatMode.OFF
		assert queue.go_back() == 10
		assert queue.current_id == 10

	def test_go_back_at_start_all_mode_wraps(self) -> None:
		"""go_back() at start with repeat=ALL wraps to end."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30])
		queue.repeat = RepeatMode.ALL
		assert queue.go_back() == 30
		assert queue.current_id == 30
		assert queue._pos == 2

	def test_go_back_on_empty_queue(self) -> None:
		"""go_back() on empty queue returns None."""
		queue = PlayQueue()
		assert queue.go_back() is None

	def test_go_back_repeat_one_does_not_affect(self) -> None:
		"""go_back() behavior is the same regardless of repeat=ONE."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30])
		queue.repeat = RepeatMode.ONE
		queue._pos = 1
		assert queue.go_back() == 10


class TestHasNextHasPrevious:
	"""Tests for has_next and has_previous properties."""

	def test_has_next_in_middle(self) -> None:
		"""has_next is True when not at end."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30, 40])
		queue._pos = 1
		assert queue.has_next is True

	def test_has_next_at_end_off_mode(self) -> None:
		"""has_next is False at end with repeat=OFF."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30])
		queue.repeat = RepeatMode.OFF
		queue._pos = 2
		assert queue.has_next is False

	def test_has_next_at_end_all_mode(self) -> None:
		"""has_next is True at end with repeat=ALL."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30])
		queue.repeat = RepeatMode.ALL
		queue._pos = 2
		assert queue.has_next is True

	def test_has_next_empty_queue(self) -> None:
		"""has_next is False for empty queue."""
		queue = PlayQueue()
		assert queue.has_next is False

	def test_has_previous_in_middle(self) -> None:
		"""has_previous is True when not at start."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30, 40])
		queue._pos = 2
		assert queue.has_previous is True

	def test_has_previous_at_start_off_mode(self) -> None:
		"""has_previous is False at start with repeat=OFF."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30])
		queue.repeat = RepeatMode.OFF
		assert queue.has_previous is False

	def test_has_previous_at_start_all_mode(self) -> None:
		"""has_previous is True at start with repeat=ALL."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30])
		queue.repeat = RepeatMode.ALL
		assert queue.has_previous is True

	def test_has_previous_empty_queue(self) -> None:
		"""has_previous is False for empty queue."""
		queue = PlayQueue()
		assert queue.has_previous is False

	def test_has_next_matches_advance_behavior(self) -> None:
		"""has_next is True exactly when advance() would change the track."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30])
		queue.repeat = RepeatMode.OFF
		queue._pos = 2
		# At end with OFF: has_next should be False, advance should return None without changing
		assert queue.has_next is False
		old_pos = queue._pos
		queue.advance()
		assert queue._pos == old_pos

	def test_has_previous_matches_go_back_behavior(self) -> None:
		"""has_previous relates to go_back() behavior."""
		queue = PlayQueue()
		queue.set_items([10, 20, 30])
		queue.repeat = RepeatMode.OFF
		# At start with OFF: has_previous is False but go_back returns current (replay)
		assert queue.has_previous is False
		assert queue.go_back() == 10
