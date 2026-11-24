"""QML face of the listening history (design R-1 History view)."""

from __future__ import annotations

import sqlite3
from typing import Any

from PySide6.QtCore import Property, QObject, Signal, Slot

from lumen.core.listen_history import recent_days


class ListenHistoryBridge(QObject):
    """Expose recent plays grouped by day; refresh when a new song starts."""

    changed = Signal()

    def __init__(self, conn: sqlite3.Connection, parent: Any = None) -> None:
        super().__init__(parent)
        self._conn = conn
        self._days: list[dict] = []

    @Slot()
    def refresh(self) -> None:
        """Re-read the history from the database."""
        self._days = recent_days(self._conn)
        self.changed.emit()

    days = Property("QVariantList", lambda self: self._days, notify=changed)
