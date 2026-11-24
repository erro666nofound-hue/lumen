"""Những việc của bản thân ứng dụng, không thuộc về bài hát hay track nào."""

from __future__ import annotations

import logging

from PySide6.QtCore import Property, QCoreApplication, QObject, Slot

import lumen
from pathlib import Path

from lumen.core import paths
from lumen.core.config import load_config

log = logging.getLogger(__name__)


class AppBridge(QObject):
    """Application-level actions exposed to QML."""

    @Slot()
    def quit(self) -> None:
        """Exit for real, even though closing a window only hides it.

        Cố ý KHÔNG dùng `QGuiApplication.quit()` / `Qt.quit()`. Từ Qt 6.6,
        `quit()` đóng hết cửa sổ trước rồi mới thoát, và **một cửa sổ từ chối
        đóng là huỷ luôn cả lệnh thoát**. Cửa sổ chính của Lumen từ chối đóng
        đúng như thế (đóng = ẩn), nên `quit()` biến thành lệnh không làm gì:
        đo được, app treo ở `app.exec()` cho tới khi bị giết.

        `exit(0)` nói thẳng với vòng lặp sự kiện, không hỏi cửa sổ nào.
        """
        log.info("Quit requested from the interface")
        QCoreApplication.exit(0)

    @staticmethod
    def _folder_summary(folder: Path, pattern: str) -> str:
        """Describe a folder as "N mục · dung lượng", or say it is not there yet."""
        if not folder.is_dir():
            return "chưa có"
        files = list(folder.rglob(pattern))
        total = sum(f.stat().st_size for f in files if f.is_file())
        return f"{len(files)} mục · {total / 1024 / 1024:.1f} MB"

    version = Property(str, lambda self: lumen.__version__, constant=True)
    # Đường dẫn THẬT đang dùng: người dùng có thể đã đổi thư mục nhạc trong cấu
    # hình, hiện thư mục mặc định là nói sai.
    musicDir = Property(str, lambda self: str(load_config().resolved_music_dir()), constant=True)
    dataDir = Property(str, lambda self: str(paths.data_dir()), constant=True)
    musicDirInfo = Property(
        str,
        lambda self: AppBridge._folder_summary(load_config().resolved_music_dir(), "*.mp3"),
        constant=True,
    )
    dataDirInfo = Property(
        str, lambda self: AppBridge._folder_summary(paths.data_dir(), "*"), constant=True
    )
