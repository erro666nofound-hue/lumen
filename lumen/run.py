#!/usr/bin/env python3
"""Self-locating entry point for Lumen.

Never rely on PYTHONPATH: this repository can live under a directory whose
name contains ``:``, which Python treats as a path separator. Resolving the
source root from ``__file__`` is the only safe way in.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _report_crash() -> None:
    """Write the traceback to a fixed file and pop a desktop notice.

    Started from a launcher there is no terminal: without this a crash at
    startup is a click that does nothing. Uses only the stdlib, because the
    import of `lumen` itself may be what failed.
    """
    import os
    import shutil
    import subprocess
    import traceback

    base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    crash = base / "lumen" / "crash.log"
    try:
        crash.parent.mkdir(parents=True, exist_ok=True)
        crash.write_text(traceback.format_exc(), encoding="utf-8")
    except OSError:
        return
    hint = f"Lỗi đã ghi vào {crash}"
    if "undefined symbol" in traceback.format_exc():
        # pyside6 build cho Qt mới, máy còn Qt cũ: cập nhật dở, không phải lỗi Lumen.
        hint = "Gói hệ thống lệch phiên bản. Chạy: sudo pacman -Syu"
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "-a", "Lumen", "Lumen không mở được", hint], check=False)


if __name__ == "__main__":
    try:
        from lumen.__main__ import main

        sys.exit(main())
    except Exception:
        _report_crash()
        raise
