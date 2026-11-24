"""The discovery page: who the user listens to, and what else those artists made.

Threading contract (CLAUDE.md muc 4): the network work (search + full
extraction for like counts) runs in a QRunnable; SQLite -- the ledger it reads
artists from and the cache it writes results to -- is touched ONLY here, on the
Qt main thread. That split is why the worker is handed plain artist names and
hands back plain results: it never sees a database connection.

Đệm 24 giờ (core/discovery_store.py) là thứ làm trang này dùng được: xếp hạng
theo tỉ lệ like/view phải bóc đầy đủ từng video, nên dựng lại mỗi lần mở app sẽ
mất hàng chục giây. Nghệ sĩ nào còn hạn thì hiện NGAY, chỉ nghệ sĩ hết hạn mới
phải đi lấy — và trong lúc chờ, phần đã có vẫn hiện chứ không để trang trắng.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    QRunnable,
    QThreadPool,
    Property,
    Qt,
    Signal,
    Slot,
)

from lumen.core.artist_prefs import ArtistPrefsRepository, tier_of_rating
from lumen.core.channel import fetch_channels
from lumen.core.discovery import TIER_NORMAL, Recommendations, artist_tiers, build, pick_podium, select_shelves
from lumen.core.discovery_store import DiscoveryCache
from lumen.core.formatting import format_duration
from lumen.core.history import DownloadHistoryRepository
from lumen.core.youtube_search import SearchResult, fetch_details, search

log = logging.getLogger(__name__)

# Lấy dư vài nghệ sĩ: kênh nào hoá ra không đăng nhạc sẽ bị lọc sạch và
# biến mất khỏi trang, nên xin ít quá là trang bị ngắn cụt.
_MAX_ARTISTS = 8
_PER_ARTIST = 8


class _Signals(QObject):
    finished = Signal(int, object)   # (generation, Recommendations)
    failed = Signal(int, str)
    backfilled = Signal(int, object)  # (generation, dict[video_id, channel name])


class _BackfillWorker(QRunnable):
    """Lấy tên kênh thật cho những bài chưa biết, TRƯỚC khi suy ra nghệ sĩ.

    Cột `artist` trong thư viện là kết quả đoán từ tiêu đề video, và phép đoán
    đó lật ngược ở khá nhiều bài. Không sửa trước thì trang khám phá đi tìm
    những "nghệ sĩ" vốn là tên bài hát. Rẻ: ~0.2s mỗi bài, và chỉ chạy một lần
    cho mỗi bài trong đời.
    """

    def __init__(self, generation: int, video_ids: list[str]) -> None:
        super().__init__()
        self.signals = _Signals()
        self._generation = generation
        self._video_ids = video_ids

    def run(self) -> None:
        try:
            names = fetch_channels(self._video_ids)
        except Exception:
            log.exception("Channel backfill failed")
            names = {}
        self.signals.backfilled.emit(self._generation, names)


class _BuildWorker(QRunnable):
    """Fetch and rank one batch of artists off the main thread."""

    def __init__(
        self, generation: int, artists: list[str], exclude: set[str], tiers: dict[str, str]
    ) -> None:
        super().__init__()
        self.signals = _Signals()
        self._generation = generation
        self._artists = artists
        self._exclude = exclude
        self._tiers = tiers

    def run(self) -> None:
        try:
            result = build(
                self._artists,
                search=search,
                fetch_details=fetch_details,
                per_artist=_PER_ARTIST,
                exclude_ids=self._exclude,
                tiers=self._tiers,
            )
        except Exception:
            log.exception("Discovery build failed")
            self.signals.failed.emit(self._generation, "Không tải được đề xuất.")
        else:
            self.signals.finished.emit(self._generation, result)


#: Số thẻ tối đa ở dải "Gợi ý cho bạn" (design R-1).
_STRIP_LIMIT = 16


class DiscoveryBridge(QAbstractListModel):
    """One row per artist, plus the top-three podium."""

    ArtistRole = Qt.ItemDataRole.UserRole + 1
    SongsRole = Qt.ItemDataRole.UserRole + 2

    countChanged = Signal()
    podiumChanged = Signal()
    stateChanged = Signal()

    def __init__(
        self,
        history: DownloadHistoryRepository,
        cache: DiscoveryCache,
        prefs: ArtistPrefsRepository | None = None,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._history = history
        self._cache = cache
        # Đánh giá tay của người dùng; không có thì mọi thứ suy như cũ.
        self._prefs = prefs
        self._rows: list[tuple[str, list[SearchResult]]] = []
        self._podium: list[SearchResult] = []
        self._state = "idle"
        self._generation = 0
        # Strong refs: a QRunnable's signal carrier is collected the moment
        # nothing holds it, and the callback silently never arrives.
        self._alive: dict[int, QRunnable] = {}
        # Bài bị xoá/để riêng tư sẽ KHÔNG BAO GIỜ tra ra tên kênh. Không có cờ
        # này thì mỗi lần dựng lại trang sẽ hỏi lại đúng những bài đó, và
        # _on_backfilled gọi refresh() -> vòng lặp vô tận.
        self._backfill_done = False
        # Mức yêu thích của từng nghệ sĩ đang lên trang; bục dựa vào nó để biết
        # hàng nào được lên hạng 1-2 và hàng nào chỉ được hạng 3.
        self._tiers: dict[str, str] = {}
        # Nghệ sĩ đã hỏi ở mỗi thế hệ, để biết ai KHÔNG trả về gì -- xem
        # _on_finished. Không nhớ thì mỗi ngày lại đi tìm lại những kênh vốn
        # chẳng đăng nhạc bao giờ.
        self._asked: dict[int, list[str]] = {}

    # -- QAbstractListModel ---------------------------------------------------

    def roleNames(self) -> dict[int, QByteArray]:
        return {
            self.ArtistRole: QByteArray(b"artist"),
            self.SongsRole: QByteArray(b"songs"),
        }

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        artist, songs = self._rows[index.row()]
        match role:
            case self.ArtistRole: return artist
            case self.SongsRole: return [_as_map(song) for song in songs]
        return None

    # -- Slots for QML --------------------------------------------------------

    @Slot()
    @Slot(bool)
    def refresh(self, force: bool = False) -> None:
        """Rebuild the page: cached artists appear at once, stale ones are fetched."""
        self._generation += 1
        generation = self._generation
        self._alive.clear()

        if force:
            self._cache.clear()

        # Bước 0: bài nào chưa biết kênh thì đi hỏi, rồi mới suy ra nghệ sĩ.
        # Không có bước này thì danh sách nghệ sĩ toàn tên bài hát.
        missing = [] if self._backfill_done else self._history.missing_uploaders()
        if missing:
            self._state = "loading"
            self.stateChanged.emit()
            worker = _BackfillWorker(generation, missing)
            worker.signals.backfilled.connect(
                self._on_backfilled, Qt.ConnectionType.QueuedConnection
            )
            self._alive[generation] = worker
            QThreadPool.globalInstance().start(worker)
            return

        shelves = select_shelves(artist_tiers(self._history.artists(), self._ratings()))
        if not shelves:
            self._apply({}, [], state="empty")
            return
        # Chỉ toàn "bình thường" (1-3 bài mỗi nghệ sĩ) là chưa đủ để đoán gu:
        # đề xuất lúc này chỉ là đoán mò. Dừng hẳn, KHÔNG gọi mạng, để màn hình
        # chuyển sang lời mời tải thêm.
        if all(t.tier == TIER_NORMAL for t in shelves):
            self._tiers = {}
            self._apply({}, [], state="learning")
            return
        self._tiers = {t.artist: t.tier for t in shelves}
        artists = [t.artist for t in shelves]

        cached = {} if force else {a: self._cache.get(a) for a in artists}
        # None = chưa từng hỏi; [] = đã hỏi và biết chắc kênh này không có nhạc.
        # Phân biệt hai thứ đó chính là chỗ tiết kiệm được cả chục lần gọi mạng.
        ready = {a: songs for a, songs in cached.items() if songs}
        stale = [a for a in artists if cached.get(a) is None]

        if not stale:
            # "ready" mà không có hàng nào là một trang TRẮNG: người dùng không
            # được nhắc gì cả. Không có gì để hiện thì trạng thái đúng là "empty".
            self._apply(ready, artists, state="ready" if ready else "empty")
            return

        # Show what we already have while the rest is on its way.
        self._apply(ready, artists, state="loading")

        self._asked[generation] = stale
        worker = _BuildWorker(
            generation, stale, self._history.owned_source_ids(), dict(self._tiers)
        )
        worker.signals.finished.connect(self._on_finished, Qt.ConnectionType.QueuedConnection)
        worker.signals.failed.connect(self._on_failed, Qt.ConnectionType.QueuedConnection)
        self._alive[generation] = worker
        QThreadPool.globalInstance().start(worker)

    def _on_backfilled(self, generation: int, names: dict) -> None:
        self._alive.pop(generation, None)
        if generation != self._generation:
            return
        self._backfill_done = True
        self._history.set_uploaders(names)
        # Tên nghệ sĩ vừa đổi thì đề xuất cũ đã vô nghĩa -- bỏ đệm rồi dựng lại.
        self._cache.clear()
        self.refresh(False)

    def _ratings(self) -> dict:
        """Tên nghệ sĩ -> mức người dùng đặt tay; None = bị chặn."""
        if self._prefs is None:
            return {}
        return {
            name: tier_of_rating(rating)
            for name, rating in self._prefs.ratings().items()
        }

    def _on_finished(self, generation: int, result: Recommendations) -> None:
        self._alive.pop(generation, None)
        asked = self._asked.pop(generation, [])
        if generation != self._generation:
            return                       # a newer refresh already replaced this
        shelves = select_shelves(artist_tiers(self._history.artists(), self._ratings()))
        artists = [t.artist for t in shelves]
        merged = {a: songs for a, songs in ((r.artist, r.songs) for r in result.rows)}
        # Chỉ cất vào đệm khi bộ lọc nhạc THẬT SỰ chạy được. Lượt bóc bị YouTube
        # chặn cho ra danh sách chưa lọc; đệm nó lại là khoá cứng một trang đầy
        # video linh tinh suốt 24 giờ, đúng thứ chủ dự án vừa phàn nàn.
        if result.filtered:
            for artist, songs in merged.items():
                self._cache.put(artist, songs)
        # Kênh được hỏi mà không ra bài nhạc nào: ghi một dòng đệm RỖNG. Nó không
        # đăng nhạc (người dùng tải một video thường của kênh đó), nên hôm nay
        # đừng hỏi lại, và ngày mai cũng chỉ hỏi lại một lần.
        if result.filtered:
            for artist in asked:
                if artist not in merged:
                    self._cache.put(artist, [])
        for artist in artists:
            if artist not in merged:
                cached = self._cache.get(artist)
                if cached:
                    merged[artist] = cached
        self._apply(merged, artists, state="ready" if merged else "empty")

    def _on_failed(self, generation: int, message: str) -> None:
        self._alive.pop(generation, None)
        if generation != self._generation:
            return
        self._state = "error" if not self._rows else "ready"
        self.stateChanged.emit()

    def _apply(
        self, by_artist: dict[str, list[SearchResult]], order: list[str], *, state: str
    ) -> None:
        """Publish one snapshot of the page: rows in artist order, then the podium."""
        self.beginResetModel()
        self._rows = [(a, by_artist[a]) for a in order if by_artist.get(a)]
        self.endResetModel()
        self._podium = pick_podium(dict(self._rows), tiers=self._tiers or None)
        self._state = state
        self.countChanged.emit()
        self.podiumChanged.emit()
        self.stateChanged.emit()

    # -- Properties -------------------------------------------------------------

    count = Property(int, lambda self: len(self._rows), notify=countChanged)
    state = Property(str, lambda self: self._state, notify=stateChanged)
    busy = Property(bool, lambda self: self._state == "loading", notify=stateChanged)
    def _strip(self) -> list:
        """Podium first, then one song per artist in turn — the "Gợi ý cho bạn" strip (R-1)."""
        picked, seen = [], set()
        shelves = [list(songs) for _, songs in self._rows]
        queue = list(self._podium)
        for depth in range(max((len(songs) for songs in shelves), default=0)):
            queue += [songs[depth] for songs in shelves if depth < len(songs)]
        for song in queue:
            if song.video_id not in seen:
                seen.add(song.video_id)
                picked.append(_as_map(song))
        return picked[:_STRIP_LIMIT]

    strip = Property("QVariantList", lambda self: self._strip(), notify=podiumChanged)

    podium = Property(
        "QVariantList", lambda self: [_as_map(s) for s in self._podium], notify=podiumChanged
    )


def _as_map(song: SearchResult) -> dict:
    """One search result in the shape QML reads."""
    return {
        "videoId": song.video_id,
        "title": song.title,
        "uploader": song.uploader,
        "durationText": format_duration(song.duration_ms),
        "url": song.url,
        "thumbnail": song.thumbnail,
        "viewCount": song.view_count,
        "likeCount": song.like_count,
    }
