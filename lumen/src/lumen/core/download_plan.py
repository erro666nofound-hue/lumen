"""Quyết định: dán một link vào track thì nên TẢI, CHÉP, hay TỪ CHỐI.

Đây là logic nghiệp vụ nên nó nằm ở `core/` (hiến pháp mục 2), không nằm trong
bridge. Thuần Python: không Qt, không SQL, không mạng — bridge đi hỏi database
lấy sự thật rồi đưa xuống đây, và chỉ ở đây mới có luật.

Tách ra còn được một cái nữa: bốn nhánh này trước đây nằm lẫn trong một hàm dài
cùng với việc dựng job và cập nhật model, nên muốn kiểm một nhánh phải dựng cả
một bridge có Qt.
"""

from __future__ import annotations

from dataclasses import dataclass

ACTION_DOWNLOAD = "download"
ACTION_COPY = "copy"
ACTION_REFUSE = "refuse"

REASON_ALREADY_DOWNLOADING = "Bài này đang được tải rồi."
REASON_ALREADY_IN_TRACK = "Bài này đã có trong track."
REASON_NO_TRACK = "Track không còn tồn tại."


@dataclass(frozen=True, slots=True)
class DownloadPlan:
    """What to do with a pasted link, and why when the answer is no."""

    action: str
    message: str = ""

    @property
    def refused(self) -> bool:
        """Report whether this plan is a refusal."""
        return self.action == ACTION_REFUSE


def plan_for(
    *,
    already_downloading: bool,
    already_in_track: bool,
    track_exists: bool,
    already_in_library: bool,
) -> DownloadPlan:
    """Decide what to do with a link the user just dropped into a track.

    Thứ tự các câu hỏi có ý nghĩa: lời từ chối phải nói đúng cái lý do NGƯỜI
    DÙNG nhận ra trước tiên. Đang tải dở thì nói "đang tải", chứ đừng nói "track
    không tồn tại" chỉ vì tình cờ kiểm cái đó trước.
    """
    if already_downloading:
        return DownloadPlan(ACTION_REFUSE, REASON_ALREADY_DOWNLOADING)
    if already_in_track:
        return DownloadPlan(ACTION_REFUSE, REASON_ALREADY_IN_TRACK)
    if not track_exists:
        return DownloadPlan(ACTION_REFUSE, REASON_NO_TRACK)
    if already_in_library:
        # Đã có file trên máy: chép sang track mới, không tải lại từ mạng.
        return DownloadPlan(ACTION_COPY)
    return DownloadPlan(ACTION_DOWNLOAD)
