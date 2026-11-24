"""The download ledger: it must outlive the files it describes.

"Nhạc của tôi" lists every song ever downloaded, including ones the user has
since deleted -- so these tests care most about what survives a deletion.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402

from lumen.bridge.history_bridge import HistoryBridge  # noqa: E402
from lumen.core import db  # noqa: E402
from lumen.core.history import DownloadHistoryRepository  # noqa: E402
from lumen.core.repository import TrackRepository  # noqa: E402
from tests.conftest import make_track  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QGuiApplication:
    return QGuiApplication.instance() or QGuiApplication([])


@pytest.fixture
def conn(tmp_path: Path):
    return db.connect(tmp_path / "library.db")


@pytest.fixture
def history(conn) -> DownloadHistoryRepository:
    return DownloadHistoryRepository(conn)


class TestLedgerOutlivesTheFile:
    def test_record_then_delete_the_song_keeps_the_line(
        self, conn, history: DownloadHistoryRepository
    ) -> None:
        tracks = TrackRepository(conn)
        stored = tracks.add(make_track(title="Gone", source_id="vid1", file_path="/tmp/gone.mp3"))
        history.record(url="https://y/vid1", source_id="vid1", title="Gone", uploader="Someone")

        assert history.all()[0].still_owned is True

        tracks.delete(stored.id)
        records = history.all()

        assert len(records) == 1
        assert records[0].url == "https://y/vid1"
        assert records[0].still_owned is False

    def test_downloading_again_keeps_the_first_timestamp(
        self, history: DownloadHistoryRepository
    ) -> None:
        history.record(url="https://y/v", source_id="v", title="Old name", when=1000)
        history.record(url="https://y/v", source_id="v", title="New name", when=9999)

        records = history.all()
        assert len(records) == 1
        assert records[0].downloaded_at == 1000     # first arrival, not last re-fetch
        assert records[0].title == "New name"       # ...but the names do refresh

    def test_newest_first(self, history: DownloadHistoryRepository) -> None:
        history.record(url="https://y/a", title="A", when=100)
        history.record(url="https://y/b", title="B", when=200)

        assert [r.title for r in history.all()] == ["B", "A"]

    def test_blank_url_is_not_recorded(self, history: DownloadHistoryRepository) -> None:
        history.record(url="", title="Nowhere")
        assert history.all() == []


    def test_owned_source_ids(self, conn, history: DownloadHistoryRepository) -> None:
        tracks = TrackRepository(conn)
        tracks.add(make_track(title="Have it", source_id="here", file_path="/tmp/x.mp3"))
        history.record(url="https://y/here", source_id="here")
        history.record(url="https://y/gone", source_id="gone")

        assert history.owned_source_ids() == {"here"}


class TestHistoryBridge:
    def test_model_exposes_the_ledger(self, qapp, history: DownloadHistoryRepository) -> None:
        history.record(url="https://y/v", source_id="v", title="Song", uploader="Chan", when=0)
        bridge = HistoryBridge(history)

        assert bridge.count == 1
        index = bridge.index(0, 0)
        assert bridge.data(index, HistoryBridge.UrlRole) == "https://y/v"
        assert bridge.data(index, HistoryBridge.ArtistRole) == "Chan"
        assert bridge.data(index, HistoryBridge.StillOwnedRole) is False

    def test_refresh_picks_up_new_downloads(self, qapp, history: DownloadHistoryRepository) -> None:
        bridge = HistoryBridge(history)
        assert bridge.count == 0

        history.record(url="https://y/v", title="Late arrival")
        bridge.refresh()

        assert bridge.count == 1


class TestThumbnails:
    def test_thumbnail_comes_from_the_video_id_not_a_local_file(
        self, qapp, history: DownloadHistoryRepository
    ) -> None:
        # Sổ còn kể cả bài đã xoá khỏi máy; bài đã xoá không còn file bìa nào,
        # nên ảnh phải lấy thẳng từ YouTube theo id.
        history.record(url="https://y/v", source_id="abc12345678", title="Song")
        bridge = HistoryBridge(history)

        thumb = bridge.data(bridge.index(0, 0), HistoryBridge.ThumbnailRole)

        assert thumb == "https://i.ytimg.com/vi/abc12345678/mqdefault.jpg"

    def test_no_video_id_means_no_thumbnail(
        self, qapp, history: DownloadHistoryRepository
    ) -> None:
        history.record(url="https://y/v", source_id="", title="Song")
        bridge = HistoryBridge(history)

        assert bridge.data(bridge.index(0, 0), HistoryBridge.ThumbnailRole) == ""


class TestGetForTheGrid:
    def test_get_returns_the_row_as_an_object(
        self, qapp, history: DownloadHistoryRepository
    ) -> None:
        history.record(url="https://y/v", source_id="abc12345678", title="Song", uploader="Chan")
        bridge = HistoryBridge(history)

        entry = bridge.get(0)

        assert entry["url"] == "https://y/v"
        assert entry["title"] == "Song"
        assert entry["artist"] == "Chan"
        assert entry["sourceId"] == "abc12345678"
        assert entry["thumbnail"].endswith("/abc12345678/mqdefault.jpg")

    def test_out_of_range_is_empty_not_a_crash(
        self, qapp, history: DownloadHistoryRepository
    ) -> None:
        # Lưới tính chỉ số theo hàng x cột nên ô cuối hàng thường vượt số dòng.
        bridge = HistoryBridge(history)

        assert bridge.get(0) == {}
        assert bridge.get(-1) == {}


class TestArtistsComeFromTracksNotTheLedger:
    """Đề xuất phải phản ánh thứ người dùng ĐANG GIỮ, không phải từng tải.

    Chủ dự án báo: không thích một nghệ sĩ nên xoá bài đi, mà app vẫn đề xuất
    nghệ sĩ đó mãi — vì nguồn là sổ lịch sử, mà sổ thì chỉ ghi thêm.
    """

    def test_a_song_only_in_the_ledger_does_not_count(
        self, conn, history: DownloadHistoryRepository
    ) -> None:
        history.record(url="https://y/gone", source_id="gone", uploader="Ghét")

        assert history.artists() == []

    def test_a_song_sitting_in_a_track_counts_once_per_song(
        self, conn, history: DownloadHistoryRepository
    ) -> None:
        from lumen.core.repository import PlaylistRepository

        tracks = TrackRepository(conn)
        playlists = PlaylistRepository(conn)
        playlist = playlists.create("Cozy")
        for i in range(3):
            song = tracks.add(
                make_track(title=f"S{i}", artist="Thích", file_path=f"/tmp/s{i}.mp3")
            )
            playlists.add_track(playlist.id, song.id)

        assert history.artists() == ["Thích"] * 3

    def test_deleting_the_song_stops_it_counting(
        self, conn, history: DownloadHistoryRepository
    ) -> None:
        from lumen.core.repository import PlaylistRepository

        tracks = TrackRepository(conn)
        playlists = PlaylistRepository(conn)
        playlist = playlists.create("Cozy")
        song = tracks.add(make_track(title="S", artist="Ghét", file_path="/tmp/s.mp3"))
        playlists.add_track(playlist.id, song.id)
        assert history.artists() == ["Ghét"]

        playlists.remove_songs(playlist.id, [song.id])

        assert history.artists() == []


class TestSongsOfArtistAreDeduplicated:
    """Cùng một bài nằm trong hai track không được hiện hai lần."""

    def _put(self, conn, playlist_name: str, *, source_id: str, title: str, artist: str):
        from lumen.core.repository import PlaylistRepository

        tracks = TrackRepository(conn)
        playlists = PlaylistRepository(conn)
        playlist = playlists.create(playlist_name)
        song = tracks.add(
            make_track(
                title=title, artist=artist, source_id=source_id,
                file_path=f"/tmp/{playlist_name}-{source_id}.mp3",
            )
        )
        playlists.add_track(playlist.id, song.id)

    def test_the_same_video_in_two_tracks_appears_once(
        self, conn, history: DownloadHistoryRepository
    ) -> None:
        self._put(conn, "Cozy", source_id="vid1", title="Bài A", artist="Zachz Winner")
        self._put(conn, "Chill", source_id="vid1", title="Bài A", artist="Zachz Winner")

        songs = history.songs_of_artist("Zachz Winner")

        assert [s["title"] for s in songs] == ["Bài A"]

    def test_different_videos_all_appear(self, conn, history: DownloadHistoryRepository) -> None:
        self._put(conn, "Cozy", source_id="vid1", title="Bài A", artist="Zachz Winner")
        self._put(conn, "Cozy2", source_id="vid2", title="Bài B", artist="Zachz Winner")

        assert len(history.songs_of_artist("Zachz Winner")) == 2

    def test_only_that_artists_songs_come_back(
        self, conn, history: DownloadHistoryRepository
    ) -> None:
        self._put(conn, "Cozy", source_id="vid1", title="Của Zachz", artist="Zachz Winner")
        self._put(conn, "Chill", source_id="vid2", title="Của Cukak", artist="Cukak")

        assert [s["title"] for s in history.songs_of_artist("Cukak")] == ["Của Cukak"]

    def test_a_collaboration_counts_for_its_primary_artist(
        self, conn, history: DownloadHistoryRepository
    ) -> None:
        self._put(
            conn, "Cozy", source_id="vid1", title="Hợp tác",
            artist="Zachz Winner, springs!, maxwell4k",
        )

        assert [s["title"] for s in history.songs_of_artist("Zachz Winner")] == ["Hợp tác"]

    def test_a_song_in_no_track_is_not_listed(
        self, conn, history: DownloadHistoryRepository
    ) -> None:
        # Chỉ liệt kê bài ĐANG GIỮ, giống mọi nơi khác trong app.
        TrackRepository(conn).add(
            make_track(title="Mồ côi", artist="Zachz Winner", file_path="/tmp/x.mp3")
        )

        assert history.songs_of_artist("Zachz Winner") == []
