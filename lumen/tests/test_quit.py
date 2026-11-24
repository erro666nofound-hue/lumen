"""Thoát hẳn: phải thoát được KỂ CẢ khi cửa sổ từ chối đóng.

Cửa sổ chính của Lumen từ chối đóng có chủ đích (đóng = ẩn, để nhạc chạy tiếp).
Từ Qt 6.6, `quit()` đóng hết cửa sổ trước rồi mới thoát — nên một cửa sổ từ chối
đóng làm `quit()` thành lệnh không làm gì, và app treo cho tới khi bị giết. Bẫy
này đã cắn thật nên có test canh.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tests.quit_probe import SWALLOWED

PROBE = Path(__file__).resolve().parent / "quit_probe.py"
TIMEOUT_S = 30


def _probe(mode: str) -> int:
    done = subprocess.run(
        [sys.executable, str(PROBE), mode], capture_output=True, timeout=TIMEOUT_S
    )
    return done.returncode


def test_quits_even_though_the_window_refuses_to_close() -> None:
    assert _probe("bridge") == 0, "AppBridge.quit() bị cửa sổ từ chối đóng nuốt mất"


def test_the_old_way_is_the_one_that_gets_swallowed() -> None:
    """Chứng minh cái bẫy có thật, để mai sau không ai "dọn" AppBridge.quit về Qt.quit()."""
    assert _probe("quit") == SWALLOWED, "Qt đã đổi hành vi: quit() không còn bị nuốt nữa"
