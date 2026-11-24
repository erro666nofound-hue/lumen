"""Đổi một việc tải thành đúng thứ QML cần đọc.

Thuần hàm trên `_Job`, không đụng model: nhờ thế mỗi hình dạng dữ liệu gửi lên
QML kiểm được riêng, và DownloadBridge chỉ còn lo hàng đợi với callback.

Ba hình dạng khác nhau CÓ CHỦ ĐÍCH, không phải trùng lặp — xem chú thích từng
hàm để biết vì sao không gộp làm một.
"""

from __future__ import annotations

from lumen.bridge.download_worker import STATE_QUEUED, STATE_RUNNING, _Job


def is_active(job: _Job) -> bool:
    """Report whether this job is still queued or running."""
    return job.state in (STATE_QUEUED, STATE_RUNNING)


def active_ids_for(jobs: list[_Job], playlist_id: int) -> list[int]:
    """List just the job ids downloading into this track.

    CHỈ id, không kèm dữ liệu: danh sách này đổi rất hiếm (thêm/xong), trong khi
    tiến độ đổi liên tục. Repeater lấy nó làm model nên delegate sống yên; lấy
    cả object thì mỗi nhịp tiến độ lại thay cả mảng, Repeater dựng lại toàn bộ
    hàng và animation viền khởi động lại liên tục — đúng cái giật đã gặp.
    """
    return [job.job_id for job in jobs if job.playlist_id == playlist_id and is_active(job)]


def info_of(job: _Job) -> dict:
    """Describe one job for a row that updates itself in place."""
    return {
        "jobId": job.job_id,
        # Tên bài chỉ biết sau bước dò video; để rỗng cho QML tự hiện lời chờ,
        # hiện URL thô ra danh sách nhạc thì xấu.
        "title": job.title or job.hint_title,
        "artist": job.hint_artist,
        "durationText": job.hint_duration_text,
        "thumbnail": job.hint_thumbnail,
        "progress": job.fraction,
        "detail": job.detail,
        "state": job.state,
    }


def active_for(jobs: list[_Job], playlist_id: int) -> list[dict]:
    """Describe the jobs downloading into this track, for the progress strip.

    Lọc theo track chứ không trả cả hàng đợi: trước đây dải tiến độ đọc cả model
    nên bài đang tải vào track Cozy vẫn chạy ở mọi track khác.
    """
    return [
        {
            "jobId": job.job_id,
            "title": job.title or job.hint_title,
            "videoId": job.video_id,
            "progress": job.fraction,
            "detail": job.detail,
            "state": job.state,
        }
        for job in jobs
        if job.playlist_id == playlist_id and is_active(job)
    ]


def any_active_for(jobs: list[_Job], playlist_id: int) -> bool:
    """Report whether this track has anything downloading — the sidebar runs a border on it."""
    return any(job.playlist_id == playlist_id and is_active(job) for job in jobs)
