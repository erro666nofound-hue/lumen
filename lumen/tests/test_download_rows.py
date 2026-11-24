"""Ba hình dạng dữ liệu gửi lên QML cho việc tải nhạc."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from lumen.bridge import download_rows  # noqa: E402
from lumen.bridge.download_worker import (  # noqa: E402
    STATE_DONE,
    STATE_FAILED,
    STATE_QUEUED,
    STATE_RUNNING,
    _Job,
)


def _job(job_id: int, playlist_id: int, state: str = STATE_RUNNING, **extra) -> _Job:
    return _Job(
        job_id=job_id,
        url=f"https://youtu.be/v{job_id}",
        video_id=f"v{job_id}",
        playlist_id=playlist_id,
        target_dir=Path("/tmp"),
        state=state,
        **extra,
    )


class TestWhichJobsCount:
    def test_queued_and_running_are_active(self) -> None:
        assert download_rows.is_active(_job(1, 1, STATE_QUEUED))
        assert download_rows.is_active(_job(2, 1, STATE_RUNNING))

    def test_finished_and_failed_are_not(self) -> None:
        assert not download_rows.is_active(_job(3, 1, STATE_DONE))
        assert not download_rows.is_active(_job(4, 1, STATE_FAILED))


class TestKeepingTracksApart:
    """Bài đang tải vào track này KHÔNG được hiện ở track khác."""

    def test_ids_are_filtered_by_track(self) -> None:
        jobs = [_job(1, playlist_id=7), _job(2, playlist_id=9)]

        assert download_rows.active_ids_for(jobs, 7) == [1]

    def test_rows_are_filtered_by_track(self) -> None:
        jobs = [_job(1, playlist_id=7), _job(2, playlist_id=9)]

        rows = download_rows.active_for(jobs, 9)

        assert [row["jobId"] for row in rows] == [2]

    def test_a_finished_job_stops_showing(self) -> None:
        jobs = [_job(1, playlist_id=7, state=STATE_DONE)]

        assert download_rows.active_ids_for(jobs, 7) == []
        assert download_rows.any_active_for(jobs, 7) is False

    def test_the_sidebar_only_lights_the_right_track(self) -> None:
        jobs = [_job(1, playlist_id=7)]

        assert download_rows.any_active_for(jobs, 7) is True
        assert download_rows.any_active_for(jobs, 8) is False


class TestWhatEachShapeCarries:
    def test_the_id_list_is_only_ids(self) -> None:
        """Kèm dữ liệu vào đây thì mỗi nhịp tiến độ lại dựng lại toàn bộ hàng."""
        ids = download_rows.active_ids_for([_job(1, 7)], 7)

        assert ids == [1]
        assert all(isinstance(item, int) for item in ids)

    def test_the_hint_title_is_used_until_the_real_one_arrives(self) -> None:
        job = _job(1, 7, hint_title="Tên tạm")

        assert download_rows.info_of(job)["title"] == "Tên tạm"

    def test_the_real_title_wins_once_known(self) -> None:
        job = _job(1, 7, hint_title="Tên tạm", title="Tên thật")

        assert download_rows.info_of(job)["title"] == "Tên thật"
