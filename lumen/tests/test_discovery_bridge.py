"""The discovery page's bridge: cache first, network only for what is stale.

The expensive part (a full extraction per video to get like counts) is why the
cache exists at all, so most of these tests are about NOT going to the network.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402

from lumen.bridge.discovery_bridge import DiscoveryBridge  # noqa: E402
from lumen.core import db  # noqa: E402
from lumen.core.discovery_store import DiscoveryCache  # noqa: E402
from lumen.core.history import DownloadHistoryRepository  # noqa: E402
from lumen.core.youtube_search import SearchResult  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QGuiApplication:
    return QGuiApplication.instance() or QGuiApplication([])


@pytest.fixture
def conn(tmp_path: Path):
    return db.connect(tmp_path / "library.db")


@pytest.fixture
def history(conn) -> DownloadHistoryRepository:
    return DownloadHistoryRepository(conn)


@pytest.fixture
def cache(conn) -> DiscoveryCache:
    return DiscoveryCache(conn)


def _adore(history, artist: str, count: int = 8, *, conn=None) -> None:
    """Đặt đủ nhiều bài CỦA NGHỆ SĨ ĐÓ VÀO MỘT TRACK để đạt "rất yêu thích".

    Phải nằm trong track, không chỉ trong sổ lịch sử: đề xuất đọc từ những bài
    người dùng ĐANG GIỮ (xem DownloadHistoryRepository.artists).
    """
    from lumen.core.repository import PlaylistRepository, TrackRepository
    from tests.conftest import make_track

    tracks = TrackRepository(conn)
    playlists = PlaylistRepository(conn)
    playlist = playlists.create(f"track-{artist}")
    for i in range(count):
        song = tracks.add(
            make_track(title=f"{artist}-{i}", artist=artist, file_path=f"/tmp/{artist}-{i}.mp3")
        )
        playlists.add_track(playlist.id, song.id)
        history.record(url=f"https://y/{artist}-{i}", source_id=f"{artist}-{i}", uploader=artist)


def _song(video_id: str, *, views: int = 1_000, likes: int = 0) -> SearchResult:
    return SearchResult(
        video_id=video_id,
        title=f"title-{video_id}",
        uploader="Chan",
        duration_ms=180_000,
        url=f"https://www.youtube.com/watch?v={video_id}",
        thumbnail=f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",
        view_count=views,
        like_count=likes,
    )


class TestCacheRoundTrip:
    def test_put_then_get(self, cache: DiscoveryCache) -> None:
        cache.put("Chan", [_song("a", views=10, likes=5)], now=1_000)

        songs = cache.get("Chan", now=1_100)

        assert [s.video_id for s in songs] == ["a"]
        assert songs[0].like_count == 5

    def test_expires_after_a_day(self, cache: DiscoveryCache) -> None:
        cache.put("Chan", [_song("a")], now=0)

        assert cache.get("Chan", now=24 * 60 * 60 - 1) is not None
        assert cache.get("Chan", now=24 * 60 * 60) is None

    def test_unknown_artist_is_a_miss(self, cache: DiscoveryCache) -> None:
        assert cache.get("Nobody") is None

    def test_put_replaces_the_previous_entry(self, cache: DiscoveryCache) -> None:
        cache.put("Chan", [_song("old")], now=0)
        cache.put("Chan", [_song("new")], now=10)

        assert [s.video_id for s in cache.get("Chan", now=20)] == ["new"]

    def test_unreadable_payload_is_treated_as_a_miss(self, conn, cache: DiscoveryCache) -> None:
        # A cache we can no longer parse must never crash the page.
        conn.execute(
            "INSERT INTO discovery_cache (artist, payload, fetched_at) VALUES (?, ?, ?)",
            ("Chan", "{not json", 0),
        )
        conn.commit()

        assert cache.get("Chan", now=1) is None

    def test_clear_empties_everything(self, cache: DiscoveryCache) -> None:
        cache.put("A", [_song("a")], now=0)
        cache.put("B", [_song("b")], now=0)

        cache.clear()

        assert cache.get("A", now=1) is None
        assert cache.get("B", now=1) is None


class TestBridgeUsesTheCache:
    def test_fully_cached_page_needs_no_network(
        self, qapp, conn, history: DownloadHistoryRepository, cache: DiscoveryCache
    ) -> None:
        _adore(history, "Chan", conn=conn)
        cache.put("Chan", [_song("a", views=100, likes=50)])
        bridge = DiscoveryBridge(history, cache)
        bridge._backfill_done = True          # nothing to look up in this test

        bridge.refresh(False)

        assert bridge.state == "ready"         # synchronous: no worker was started
        assert bridge.count == 1
        assert bridge.data(bridge.index(0, 0), DiscoveryBridge.ArtistRole) == "Chan"
        assert [s["videoId"] for s in bridge.podium] == ["a"]

    def test_songs_role_is_shaped_for_qml(
        self, qapp, conn, history: DownloadHistoryRepository, cache: DiscoveryCache
    ) -> None:
        _adore(history, "Chan", conn=conn)
        cache.put("Chan", [_song("a", views=999, likes=9)])
        bridge = DiscoveryBridge(history, cache)
        bridge._backfill_done = True

        bridge.refresh(False)

        song = bridge.data(bridge.index(0, 0), DiscoveryBridge.SongsRole)[0]
        assert set(song) == {
            "videoId", "title", "uploader", "durationText",
            "url", "thumbnail", "viewCount", "likeCount",
        }
        assert song["durationText"] == "3:00"
        assert song["viewCount"] == 999

    def test_no_downloads_means_an_empty_page(
        self, qapp, conn, history: DownloadHistoryRepository, cache: DiscoveryCache
    ) -> None:
        bridge = DiscoveryBridge(history, cache)
        bridge._backfill_done = True

        bridge.refresh(False)

        assert bridge.state == "empty"
        assert bridge.count == 0
        assert bridge.podium == []

    def test_artists_are_ordered_by_how_often_they_were_downloaded(
        self, qapp, conn, history: DownloadHistoryRepository, cache: DiscoveryCache
    ) -> None:
        _adore(history, "Popular", 12, conn=conn)
        _adore(history, "Rare", 8, conn=conn)
        cache.put("Popular", [_song("a")])
        cache.put("Rare", [_song("b")])
        bridge = DiscoveryBridge(history, cache)
        bridge._backfill_done = True

        bridge.refresh(False)

        artists = [
            bridge.data(bridge.index(i, 0), DiscoveryBridge.ArtistRole)
            for i in range(bridge.count)
        ]
        assert artists == ["Popular", "Rare"]

    def test_backfill_only_runs_once_per_session(
        self, qapp, conn, history: DownloadHistoryRepository, cache: DiscoveryCache
    ) -> None:
        # A deleted/private video never resolves a channel name. Without the
        # one-shot guard, _on_backfilled -> refresh() -> backfill again forever.
        history.record(url="https://y/1", source_id="unresolvable", uploader="")
        bridge = DiscoveryBridge(history, cache)

        assert history.missing_uploaders() == ["unresolvable"]

        bridge._on_backfilled(bridge._generation, {})   # lookup found nothing

        assert bridge._backfill_done is True
        assert bridge.state in ("empty", "ready")       # settled, not looping


class TestCacheRulesVersion:
    """A cache built under the old rules must not survive a rules change."""

    def test_entry_from_an_older_rules_version_is_a_miss(
        self, conn, cache: DiscoveryCache
    ) -> None:
        cache.put("Chan", [_song("a")], now=0)
        conn.execute("UPDATE discovery_cache SET rules_version = rules_version - 1")
        conn.commit()

        assert cache.get("Chan", now=1) is None

    def test_a_fresh_write_is_readable_again(self, conn, cache: DiscoveryCache) -> None:
        cache.put("Chan", [_song("a")], now=0)
        conn.execute("UPDATE discovery_cache SET rules_version = rules_version - 1")
        conn.commit()

        cache.put("Chan", [_song("b")], now=1)

        assert [s.video_id for s in cache.get("Chan", now=2)] == ["b"]


class TestKnownEmptyArtists:
    """A channel the user downloaded a non-music video from must not be re-searched daily."""

    def test_empty_cache_entry_is_remembered_not_retried(self, cache: DiscoveryCache) -> None:
        cache.put("NotAMusician", [], now=0)

        # [] and None must not be confused: one means "asked, nothing there",
        # the other means "never asked".
        assert cache.get("NotAMusician", now=1) == []
        assert cache.get("NeverAsked", now=1) is None

    def test_bridge_skips_an_artist_already_known_to_have_no_music(
        self, qapp, conn, history: DownloadHistoryRepository, cache: DiscoveryCache
    ) -> None:
        _adore(history, "NotAMusician", conn=conn)
        cache.put("NotAMusician", [])
        bridge = DiscoveryBridge(history, cache)
        bridge._backfill_done = True

        bridge.refresh(False)

        # Settled without starting a worker: nothing was stale.
        assert bridge.state == "empty"
        assert bridge._alive == {}


class TestLearningState:
    """Chỉ toàn nghệ sĩ "bình thường" thì không đề xuất gì cả.

    Luật chủ dự án: 1-3 bài mỗi nghệ sĩ chưa nói lên gu của ai. Đề xuất lúc đó
    chỉ là đoán mò, nên màn hình chuyển sang lời mời tải thêm.
    """

    def test_only_casual_artists_means_no_recommendations(
        self, qapp, conn, history: DownloadHistoryRepository, cache: DiscoveryCache
    ) -> None:
        for i in range(3):
            _adore(history, f"Ca{i}", 1, conn=conn)
        bridge = DiscoveryBridge(history, cache)
        bridge._backfill_done = True

        bridge.refresh(False)

        assert bridge.state == "learning"
        assert bridge.count == 0
        assert bridge.podium == []

    def test_learning_state_costs_no_network(
        self, qapp, conn, history: DownloadHistoryRepository, cache: DiscoveryCache
    ) -> None:
        # Không đủ dữ liệu thì đừng đi hỏi YouTube làm gì -- đây cũng là chỗ
        # tiết kiệm nhiều lần gọi mạng nhất với thư viện còn non.
        _adore(history, "Ca", 1, conn=conn)
        bridge = DiscoveryBridge(history, cache)
        bridge._backfill_done = True

        bridge.refresh(False)

        assert bridge._alive == {}

    def test_one_favourite_artist_is_enough_to_start_recommending(
        self, qapp, conn, history: DownloadHistoryRepository, cache: DiscoveryCache
    ) -> None:
        _adore(history, "Loved", 5, conn=conn)                    # 4-6 bài = "yêu thích"
        _adore(history, "Casual", 1, conn=conn)                   # 1 bài = "bình thường"
        cache.put("Loved", [_song("a", views=100, likes=50)])
        cache.put("Casual", [_song("b", views=100, likes=10)])
        bridge = DiscoveryBridge(history, cache)
        bridge._backfill_done = True

        bridge.refresh(False)

        assert bridge.state == "ready"
        artists = [
            bridge.data(bridge.index(i, 0), DiscoveryBridge.ArtistRole)
            for i in range(bridge.count)
        ]
        assert artists == ["Loved", "Casual"]          # bình thường bị đẩy xuống cuối

    def test_podium_ignores_the_casual_row(
        self, qapp, conn, history: DownloadHistoryRepository, cache: DiscoveryCache
    ) -> None:
        _adore(history, "Loved", 5, conn=conn)
        _adore(history, "Casual", 1, conn=conn)
        cache.put("Loved", [_song("a", views=1000, likes=10)])
        cache.put("Casual", [_song("b", views=1000, likes=999)])   # điểm cao hơn hẳn
        bridge = DiscoveryBridge(history, cache)
        bridge._backfill_done = True

        bridge.refresh(False)

        assert [s["videoId"] for s in bridge.podium] == ["a"]
