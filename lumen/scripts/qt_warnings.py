"""Run Lumen and write EVERY Qt/QML message to a file — the app itself swallows them.

    XDG_RUNTIME_DIR=… XDG_DATA_HOME=… XDG_CONFIG_HOME=… XDG_STATE_HOME=… \\
    QT_QPA_PLATFORM=offscreen timeout 14 python3 scripts/qt_warnings.py /tmp/qt.txt

Zero lines in the file = healthy. A polish loop (CB-059) shows up here and nowhere else.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

from PySide6.QtCore import qInstallMessageHandler

_out = open(sys.argv[1], "w", encoding="utf-8")  # noqa: SIM115 - lives as long as the app


def _handler(mode, context, message) -> None:  # noqa: ANN001
    """Append one Qt message with its source location."""
    _out.write(f"{mode} {context.file}:{context.line} {message}\n")
    _out.flush()


qInstallMessageHandler(_handler)
sys.argv = ["run.py", "--verbose"]
runpy.run_path(str(Path(__file__).resolve().parent.parent / "run.py"), run_name="__main__")
