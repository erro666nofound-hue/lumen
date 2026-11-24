"""Tiến trình con: giữ socket điều khiển rồi đứng yên, cho test khác thử cướp.

Phải là tiến trình RIÊNG. Trong cùng một tiến trình, bản đang nghe không thể
trả lời cái ping của chính nó (luồng chính đang chặn ở lệnh gửi), nên phép thử
"có ai đang nghe không" luôn ra sai.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QTimer  # noqa: E402

from lumen.services.control import ControlServer  # noqa: E402

HOLD_MS = 15000


def main() -> int:
    path = Path(sys.argv[1])
    app = QCoreApplication([])
    server = ControlServer()
    if not server.start(str(path)):
        return 2
    print("ready", flush=True)
    QTimer.singleShot(HOLD_MS, app.quit)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
