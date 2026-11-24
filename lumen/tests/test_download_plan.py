"""Dán một link vào track: tải, chép, hay từ chối."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lumen.core import download_plan as plan  # noqa: E402


def _plan(**overrides) -> plan.DownloadPlan:
    facts = {
        "already_downloading": False,
        "already_in_track": False,
        "track_exists": True,
        "already_in_library": False,
    }
    facts.update(overrides)
    return plan.plan_for(**facts)


class TestTheHappyPaths:
    def test_a_new_song_is_downloaded(self) -> None:
        assert _plan().action == plan.ACTION_DOWNLOAD

    def test_a_song_already_on_disk_is_copied_not_downloaded_again(self) -> None:
        """Tải lại một file đã có là phí băng thông và phí thời gian của người dùng."""
        assert _plan(already_in_library=True).action == plan.ACTION_COPY


class TestRefusals:
    def test_the_same_song_twice_at_once(self) -> None:
        made = _plan(already_downloading=True)

        assert made.refused
        assert made.message == plan.REASON_ALREADY_DOWNLOADING

    def test_a_song_already_in_this_track(self) -> None:
        made = _plan(already_in_track=True)

        assert made.refused
        assert made.message == plan.REASON_ALREADY_IN_TRACK

    def test_a_track_that_has_been_deleted(self) -> None:
        made = _plan(track_exists=False)

        assert made.refused
        assert made.message == plan.REASON_NO_TRACK

    def test_every_refusal_says_why(self) -> None:
        """Từ chối mà không nói lý do thì người dùng tưởng app hỏng."""
        for facts in ({"already_downloading": True},
                      {"already_in_track": True},
                      {"track_exists": False}):
            assert _plan(**facts).message


class TestWhichReasonWins:
    def test_being_downloaded_beats_being_in_the_track(self) -> None:
        """Nói đúng cái lý do người dùng nhận ra trước tiên."""
        made = _plan(already_downloading=True, already_in_track=True)

        assert made.message == plan.REASON_ALREADY_DOWNLOADING

    def test_a_missing_track_never_turns_into_a_copy(self) -> None:
        made = _plan(track_exists=False, already_in_library=True)

        assert made.refused
