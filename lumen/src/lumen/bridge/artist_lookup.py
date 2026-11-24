"""Tra cứu mạng cho mục "Nhạc sĩ", ngoài luồng chính.

Tách khỏi ArtistsBridge vì nó chặn trên mạng vài giây mỗi lần, mà bridge thì
phải chạy trên luồng Qt (CLAUDE.md muc 4). Bridge chỉ nói "tra giúp cái này",
còn ở đây lo phần chậm.

Cùng khuôn với bridge/preview_worker.py — QRunnable + QueuedConnection.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QRunnable, Signal

from lumen.core.channel import avatar_of_video

log = logging.getLogger(__name__)


class LookupSignals(QObject):
    avatars = Signal(object)         # dict[tên nghệ sĩ, link ảnh]


class AvatarLookup(QRunnable):
    """Lấy ảnh đại diện kênh cho vài nghệ sĩ, ngoài luồng chính (~3s mỗi người)."""

    def __init__(self, wanted: list[tuple[str, str]]) -> None:
        super().__init__()
        self.signals = LookupSignals()
        self._wanted = wanted            # [(tên nghệ sĩ, một video id của họ)]

    def run(self) -> None:
        found: dict[str, str] = {}
        for name, video_id in self._wanted:
            try:
                _, url = avatar_of_video(video_id)
            except Exception:
                log.exception("Avatar lookup failed for %s", name)
                url = ""
            # Ghi cả khi rỗng: "đã hỏi và không có" cũng là một kết quả.
            found[name] = url
        self.signals.avatars.emit(found)
