"""Chép chuỗi vào clipboard cho QML.

QML KHÔNG có API clipboard. Mẹo quen thuộc là một `TextEdit` ẩn rồi
selectAll()+copy() -- ĐÃ THỬ VÀ ĐO TRÊN MÁY NÀY: không ăn, clipboard giữ
nguyên giá trị cũ (TextEdit không hiển thị thật thì copy() im lặng không làm
gì). Nên đi qua QClipboard, đúng tầng bridge như mọi thứ khác.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, Slot
from PySide6.QtGui import QGuiApplication

log = logging.getLogger(__name__)


class ClipboardBridge(QObject):
    """Một cửa duy nhất để QML đưa chữ vào clipboard hệ thống."""

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)

    @Slot(str, result=bool)
    def setText(self, text: str) -> bool:
        """Đặt clipboard; trả về False nếu không có clipboard (chạy offscreen)."""
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            log.warning("No clipboard available")
            return False
        clipboard.setText(text)
        return True
