"""Danh sách nghệ sĩ cho mục "Nhạc sĩ": ai đã tải bao nhiêu, và bạn nghĩ sao về họ.

Gộp hai nguồn: số bài ĐANG GIỮ trong track (suy ra mức tự động) và đánh giá tay
người dùng đặt. Đánh giá tay thắng — xem core/artist_prefs.py.

Threading contract (CLAUDE.md muc 4): sqlite chỉ chạm từ luồng chính, nên mọi
thứ ở đây chạy trên luồng đó, y hệt LibraryBridge.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QThreadPool,
    Property,
    Qt,
    Signal,
    Slot,
)

from lumen.core.artist_prefs import RATING_BLOCKED, ArtistAvatarCache, ArtistPrefsRepository
from lumen.bridge.artist_lookup import AvatarLookup
from lumen.core.history import DownloadHistoryRepository
from lumen.core.tiers import TIER_FAV, TIER_NORMAL, TIER_VERY, artist_tiers, tier_for

log = logging.getLogger(__name__)

_RATING_OF_TIER = {TIER_NORMAL: 0, TIER_FAV: 1, TIER_VERY: 2}

# Mỗi lượt chỉ lấy ngần này ảnh: mỗi ảnh ~3s, lấy cả chục người một lúc là
# đấm liên tục vào YouTube và ăn giới hạn tốc độ.
_AVATAR_BATCH = 4

# Bao nhiêu người lên hàng "Nghệ sĩ bạn nghe nhiều nhất" ở trang thư viện của
# gói Free. Ba là con số vừa một hàng và vừa bản phác trong QĐ-010.
_TOP_ARTISTS = 3


class ArtistsBridge(QAbstractListModel):
    """Mọi nghệ sĩ người dùng có nhạc, kèm đánh giá (nếu đã đặt)."""

    NameRole = Qt.ItemDataRole.UserRole + 1
    SongCountRole = Qt.ItemDataRole.UserRole + 2
    RatingRole = Qt.ItemDataRole.UserRole + 3
    RatedRole = Qt.ItemDataRole.UserRole + 4
    AvatarRole = Qt.ItemDataRole.UserRole + 5

    countChanged = Signal()
    busyChanged = Signal()
    #: Danh sách "nghe nhiều nhất" đổi. Tách khỏi `countChanged`: cái kia phát cả
    #: khi người dùng gõ vào ô tìm nhạc sĩ, mà bộ lọc đó KHÔNG được đụng tới hàng
    #: nghệ sĩ ở trang thư viện.
    topArtistsChanged = Signal()
    errorOccurred = Signal(str)

    def __init__(
        self,
        history: DownloadHistoryRepository,
        prefs: ArtistPrefsRepository,
        avatars: ArtistAvatarCache | None = None,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._history = history
        self._prefs = prefs
        self._avatars = avatars
        self._all: list[dict] = []
        self._rows: list[dict] = []
        self._search = ""
        self._busy = False
        # Giữ tham chiếu mạnh: bộ mang tín hiệu của QRunnable bị thu hồi ngay
        # khi không ai giữ, và callback lặng lẽ không bao giờ tới.
        self._avatar_worker: AvatarLookup | None = None
        self.refresh()

    # -- QAbstractListModel ---------------------------------------------------

    def roleNames(self) -> dict[int, QByteArray]:
        return {
            self.NameRole: QByteArray(b"name"),
            self.SongCountRole: QByteArray(b"songCount"),
            self.RatingRole: QByteArray(b"rating"),
            self.RatedRole: QByteArray(b"rated"),
            self.AvatarRole: QByteArray(b"avatar"),
        }

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        row = self._rows[index.row()]
        match role:
            case self.NameRole: return row["name"]
            case self.SongCountRole: return row["songCount"]
            case self.RatingRole: return row["rating"]
            case self.RatedRole: return row["rated"]
            case self.AvatarRole: return row["avatar"]
        return None

    # -- Slots for QML --------------------------------------------------------

    @Slot()
    def refresh(self) -> None:
        """Dựng lại danh sách: MỖI nghệ sĩ đúng MỘT dòng.

        Không đi qua phần xử lý đánh giá của `artist_tiers` — nó LOẠI nghệ sĩ bị
        chặn (đúng cho trang khám phá, sai cho trang này, vì không hiện thì
        không có cách nào bỏ chặn). Trước đây tôi lách bằng cách bỏ mục "chặn"
        ra khỏi bản đồ rồi nối thêm dòng riêng cho họ — kết quả là mỗi nghệ sĩ
        bị chặn hiện HAI lần, một dòng có số bài và một dòng "chưa có bài nào".
        """
        ratings = self._prefs.ratings()
        counts = {t.artist: t.count for t in artist_tiers(self._history.artists())}
        # Nghệ sĩ được đánh giá nhưng chưa tải bài nào vẫn phải có mặt.
        for name in ratings:
            counts.setdefault(name, 0)

        cached = self._avatars.all() if self._avatars is not None else {}
        rows = [
            {
                "name": name,
                "songCount": count,
                "rating": ratings.get(name, _RATING_OF_TIER.get(tier_for(count), 0)),
                "rated": name in ratings,
                "avatar": cached.get(name, ""),
            }
            for name, count in counts.items()
        ]
        # Nhiều bài trước, rồi tới tên — thứ tự tất định để danh sách không nhảy.
        rows.sort(key=lambda r: (-r["songCount"], r["name"].casefold()))

        self._all = rows
        self.topArtistsChanged.emit()
        self._apply_search()
        self._fetch_missing_avatars()

    @Slot(int, result="QVariantList")
    def top(self, limit: int) -> list:
        """Return the first artists by song count, for the podium (design R-1)."""
        return [dict(row) for row in self._all if row["songCount"] > 0][:max(0, limit)]

    @Slot(str, int, result=bool)
    def setRating(self, name: str, rating: int) -> bool:
        """Đặt đánh giá cho một nghệ sĩ."""
        if not self._prefs.set_rating(name, rating):
            self.errorOccurred.emit("Không lưu được đánh giá.")
            return False
        self.refresh()
        return True

    @Slot(str, result=bool)
    def clearRating(self, name: str) -> bool:
        """Bỏ đánh giá tay, trả nghệ sĩ đó về cho phép đoán tự động."""
        cleared = self._prefs.clear(name)
        if cleared:
            self.refresh()
        return cleared

    @Slot(str)
    def setSearch(self, text: str) -> None:
        """Lọc trong các nhạc sĩ Lumen đã biết. Rỗng = hiện tất."""
        value = text.strip().casefold()
        if value == self._search:
            return
        self._search = value
        self._apply_search()

    def _apply_search(self) -> None:
        """Áp bộ lọc lên danh sách đầy đủ.

        Giữ RIÊNG `_all` và `_rows`: lọc trực tiếp lên danh sách hiển thị sẽ làm
        mất dần dữ liệu qua mỗi lần gõ, và phải nạp lại DB mỗi phím.
        """
        rows = [r for r in self._all if self._search in r["name"].casefold()]
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()
        self.countChanged.emit()

    @Slot(str, result="QVariantList")
    def songsOf(self, artist: str) -> list:
        """Các bài đang giữ của một nghệ sĩ, mỗi bài đúng một lần."""
        return self._history.songs_of_artist(artist)

    def _fetch_missing_avatars(self) -> None:
        """Lấy ảnh đại diện cho nghệ sĩ chưa có, một lần cho mỗi người.

        Chạy nền: mỗi người tốn ~3s (video -> link kênh -> trang kênh). Chỉ hỏi
        những người CHƯA từng hỏi — kể cả người hỏi rồi mà không có ảnh.
        """
        if self._avatars is None or self._avatar_worker is not None:
            return
        known = self._avatars.known()
        wanted: list[tuple[str, str]] = []
        for row in self._all:
            if row["name"] in known:
                continue
            songs = self._history.songs_of_artist(row["name"])
            video = next((s["sourceId"] for s in songs if s["sourceId"]), "")
            if video:
                wanted.append((row["name"], video))
        if not wanted:
            return
        worker = AvatarLookup(wanted[:_AVATAR_BATCH])
        worker.signals.avatars.connect(self._on_avatars, Qt.ConnectionType.QueuedConnection)
        self._avatar_worker = worker
        QThreadPool.globalInstance().start(worker)

    def _on_avatars(self, found: dict) -> None:
        self._avatar_worker = None
        if self._avatars is None:
            return
        for name, url in found.items():
            self._avatars.put(name, url)
        self.refresh()

    def _set_busy(self, value: bool) -> None:
        if value != self._busy:
            self._busy = value
            self.busyChanged.emit()

    def _top_artists(self) -> list[dict]:
        """Return the few artists this library holds the most songs of.

        Đọc `_all` chứ KHÔNG đọc `_rows`: `_rows` đã qua ô tìm của trang "Nhạc
        sĩ", và trang thư viện thì không liên quan gì tới ô tìm đó.

        Nhưng `_all` GIỮ LẠI nghệ sĩ bị chặn — cố ý, vì trang "Nhạc sĩ" không
        hiện họ thì không có cách nào bỏ chặn (xem `refresh`). Trang thư viện
        thì ngược lại: chặn ai rồi mà vẫn dí mặt người đó lên trang chính là
        phản bội đúng cái nút người dùng vừa bấm. Nên lọc ở đây.

        Không gọi mạng: `_all` dựng từ `core/tiers.py` + sqlite trên máy. Đó
        chính là đường cắt Free/Pro của QĐ-010 — Free biết bạn thích ai, Pro đi
        tìm nhạc mới của họ.
        """
        wanted = [row for row in self._all if row["rating"] != RATING_BLOCKED]
        return wanted[:_TOP_ARTISTS]

    count = Property(int, lambda self: len(self._rows), notify=countChanged)
    #: Cho hàng "Nghệ sĩ bạn nghe nhiều nhất" ở trang thư viện của gói Free.
    topArtists = Property("QVariantList", _top_artists, notify=topArtistsChanged)
    busy = Property(bool, lambda self: self._busy, notify=busyChanged)
