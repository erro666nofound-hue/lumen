"""Tests for PlayQueue.reorder — kéo đổi thứ tự mà không cắt nhạc đang phát.

Hàng đợi là bản chép ids lúc bấm play. Kéo một hàng trong track đang phát phải
đổi được bản chép đó, và phải đổi mà KHÔNG đụng vào bài đang chạy.
"""

from __future__ import annotations

import random

from lumen.core.playqueue import PlayQueue


class TestReorderKeepsPlaying:
	def test_next_song_follows_the_new_order(self) -> None:
		queue = PlayQueue()
		queue.set_items([1, 2, 3], start_id=1)

		queue.reorder([1, 3, 2])

		assert queue.current_id == 1, "bài đang phát không được đổi"
		assert queue.advance(manual=True) == 3

	def test_the_playing_song_survives_being_moved(self) -> None:
		queue = PlayQueue()
		queue.set_items([1, 2, 3], start_id=2)

		queue.reorder([2, 3, 1])

		assert queue.current_id == 2
		assert queue.ids == (2, 3, 1)
		assert queue.advance(manual=True) == 3

	def test_a_song_the_caller_forgot_stays_in_the_queue(self) -> None:
		"""Mất một bài khỏi hàng đợi là kiểu mất không ai thấy lúc nó xảy ra."""
		queue = PlayQueue()
		queue.set_items([1, 2, 3], start_id=1)

		queue.reorder([3, 1])

		assert set(queue.ids) == {1, 2, 3}
		assert queue.ids[:2] == (3, 1)

	def test_an_id_from_nowhere_is_ignored(self) -> None:
		queue = PlayQueue()
		queue.set_items([1, 2], start_id=1)

		queue.reorder([2, 99, 1])

		assert queue.ids == (2, 1)

	def test_reordering_an_empty_queue_does_nothing(self) -> None:
		queue = PlayQueue()

		queue.reorder([1, 2])

		assert queue.ids == ()
		assert queue.current_id is None


class TestReorderUnderShuffle:
	def test_the_shuffle_sequence_is_kept_not_rolled_again(self) -> None:
		"""Kéo một hàng KHÔNG được xáo lại — người nghe đang đi giữa một vòng xáo."""
		queue = PlayQueue(rng=random.Random(7))
		queue.set_items([1, 2, 3, 4], start_id=1)
		queue.shuffle = True
		sequence = [queue.current_id]
		while queue.has_next:
			sequence.append(queue.advance(manual=True))

		again = PlayQueue(rng=random.Random(7))
		again.set_items([1, 2, 3, 4], start_id=1)
		again.shuffle = True
		again.reorder([4, 3, 2, 1])
		after = [again.current_id]
		while again.has_next:
			after.append(again.advance(manual=True))

		assert after == sequence
		assert again.ids == (4, 3, 2, 1), "danh sách thật vẫn phải đổi"
