"""Qt list model over the download ledger -- the "Nhạc của tôi" section.

Threading contract (CLAUDE.md muc 4): SQLite only from the Qt main thread, so
every method here runs there, exactly like LibraryBridge.

Rows are identified by URL rather than by title and local cover, on purpose:
the ledger keeps songs the user has already deleted, and a deleted song has no
file and no artwork left to show.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, Property, Qt, Signal, Slot

from lumen.core.history import DownloadHistoryRepository
from lumen.core.youtube_search import thumbnail_url

log = logging.getLogger(__name__)


class HistoryBridge(QAbstractListModel):
    """Everything ever downloaded, newest first, whether or not it still exists."""

    UrlRole = Qt.ItemDataRole.UserRole + 1
    SourceIdRole = Qt.ItemDataRole.UserRole + 2
    TitleRole = Qt.ItemDataRole.UserRole + 3
    ArtistRole = Qt.ItemDataRole.UserRole + 4
    DateTextRole = Qt.ItemDataRole.UserRole + 5
    StillOwnedRole = Qt.ItemDataRole.UserRole + 6
    ThumbnailRole = Qt.ItemDataRole.UserRole + 7

    countChanged = Signal()

    def __init__(self, repository: DownloadHistoryRepository, parent: Any = None) -> None:
        super().__init__(parent)
        self._repository = repository
        self._records: list = []
        self.refresh()

    def roleNames(self) -> dict[int, QByteArray]:
        return {
            self.UrlRole: QByteArray(b"url"),
            self.SourceIdRole: QByteArray(b"sourceId"),
            self.TitleRole: QByteArray(b"title"),
            self.ArtistRole: QByteArray(b"artist"),
            self.DateTextRole: QByteArray(b"dateText"),
            self.StillOwnedRole: QByteArray(b"stillOwned"),
            self.ThumbnailRole: QByteArray(b"thumbnail"),
        }

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._records)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._records)):
            return None
        record = self._records[index.row()]
        match role:
            case self.UrlRole: return record.url
            case self.SourceIdRole: return record.source_id
            case self.TitleRole: return record.title
            case self.ArtistRole: return record.best_artist
            case self.DateTextRole: return _date_text(record.downloaded_at)
            case self.StillOwnedRole: return record.still_owned
            # Ảnh lấy thẳng từ YouTube theo video id: sổ này còn kể cả những
            # bài đã xoá khỏi máy, mà bài đã xoá thì không còn file bìa nào.
            case self.ThumbnailRole:
                return thumbnail_url(record.source_id) if record.source_id else ""
        return None

    @Slot(int, result="QVariantMap")
    def get(self, row: int) -> dict:
        """Một dòng sổ dưới dạng object cho QML.

        Lưới "Nhạc của tôi" xếp thẻ theo hàng/cột nên delegate KHÔNG ứng một-một
        với dòng model; nó phải tự tra theo chỉ số phẳng, và `model.xxx` của
        Repeater không dùng được cho việc đó.
        """
        if not (0 <= row < len(self._records)):
            return {}
        record = self._records[row]
        return {
            "url": record.url,
            "sourceId": record.source_id,
            "title": record.title,
            "artist": record.best_artist,
            "dateText": _date_text(record.downloaded_at),
            "stillOwned": record.still_owned,
            "thumbnail": thumbnail_url(record.source_id) if record.source_id else "",
        }

    @Slot()
    def refresh(self) -> None:
        """Re-read the whole ledger. It is short and only changes on download."""
        self.beginResetModel()
        self._records = self._repository.all()
        self.endResetModel()
        self.countChanged.emit()

    count = Property(int, lambda self: len(self._records), notify=countChanged)


def _date_text(stamp: int) -> str:
    """Render a download timestamp as dd/mm/yyyy, or blank if it makes no sense."""
    try:
        return datetime.fromtimestamp(stamp).strftime("%d/%m/%Y")
    except (OSError, OverflowError, ValueError):
        return ""
