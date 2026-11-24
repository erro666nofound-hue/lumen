"""Tiến trình con cho tests/test_quit.py: dựng một cửa sổ TỪ CHỐI ĐÓNG rồi thử thoát.

Phải là tiến trình riêng. Gọi `exec()` trên QGuiApplication dùng chung của bộ
test sẽ để lại cờ thoát trong Qt và làm hỏng những test chạy sau — đã xảy ra
thật, 6 test đỏ theo.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QByteArray, QTimer, QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402

from lumen.bridge.app_bridge import AppBridge  # noqa: E402

STUBBORN_WINDOW = b"""
import QtQuick
import QtQuick.Window

Window {
    width: 120
    height: 80
    visible: true
    onClosing: (event) => event.accepted = false
}
"""

WATCHDOG_MS = 4000
#: Mã thoát của chốt hẹn giờ: lệnh thoát đã bị nuốt.
SWALLOWED = 97


def main() -> int:
    mode = sys.argv[1]
    app = QGuiApplication([])
    app.setQuitOnLastWindowClosed(False)
    engine = QQmlApplicationEngine()
    engine.loadData(QByteArray(STUBBORN_WINDOW), QUrl("stubborn"))
    if not engine.rootObjects():
        return 2

    bridge = AppBridge()
    QTimer.singleShot(200, bridge.quit if mode == "bridge" else app.quit)
    QTimer.singleShot(WATCHDOG_MS, lambda: app.exit(SWALLOWED))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
