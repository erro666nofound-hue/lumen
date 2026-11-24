"""Pytest bootstrap for Lumen.

Mirrors run.py: resolve the source root from __file__ instead of relying on
PYTHONPATH or pytest's ``pythonpath`` ini option, because this repository can
live under a directory whose name contains ``:``.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
