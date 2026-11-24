"""Tests for PlayerBridge playback controls (play/toggle/previous/volume)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402

from lumen.bridge.library_bridge import LibraryBridge  # noqa: E402
from lumen.bridge.player_bridge import PlayerBridge  # noqa: E402
from lumen.core import db  # noqa: E402
from lumen.core.playback import PlaybackController  # noqa: E402
from lumen.core.repository import TrackRepository  # noqa: E402
from tests.conftest import make_track  # noqa: E402


class FakeBackend:
    """Fake audio backend for PlayerBridge tests."""

    def __init__(self) -> None:
        self._listener_finished: Callable[[], None] | None = None
        self._listener_failed: Callable[[str], None] | None = None
        self._position_ms = 0
        self._duration_ms = 0
        self._is_playing = False
        self._has_file = False
        self._volume = 80
        self._speed = 1.0

    def set_listener(
        self, *, finished: Callable[[], None] | None = None, failed: Callable[[str], None] | None = None
    ) -> None:
        self._listener_finished = finished
        self._listener_failed = failed

    def load(self, path: str, *, autoplay: bool = True) -> None:
        self._has_file = True
        self._position_ms = 0
        self._is_playing = autoplay

    def resume(self) -> None:
        self._is_playing = True

    def pause(self) -> None:
        self._is_playing = False

    def stop(self) -> None:
        self._has_file = False
        self._is_playing = False

    def seek_ms(self, position_ms: int) -> None:
        self._position_ms = position_ms

    def set_volume(self, volume: int) -> None:
        self._volume = volume

    def set_speed(self, rate: float) -> None:
        self._speed = rate

    def shutdown(self) -> None:
        pass

    @property
    def position_ms(self) -> int:
        return self._position_ms

    @property
    def duration_ms(self) -> int:
        return self._duration_ms

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    @property
    def has_file(self) -> bool:
        return self._has_file

    # Test helpers
    def set_state(self, position_ms: int = None, duration_ms: int = None, is_playing: bool = None) -> None:
        if position_ms is not None:
            self._position_ms = position_ms
        if duration_ms is not None:
            self._duration_ms = duration_ms
        if is_playing is not None:
            self._is_playing = is_playing

    def emit_finished(self) -> None:
        if self._listener_finished is not None:
            self._listener_finished()

    def emit_failed(self, message: str) -> None:
        if self._listener_failed is not None:
            self._listener_failed(message)


@pytest.fixture(scope="module")
def qapp() -> QGuiApplication:
    return QGuiApplication.instance() or QGuiApplication([])


@pytest.fixture
def library(tmp_path: Path) -> LibraryBridge:
    conn = db.connect(tmp_path / "library.db")
    return LibraryBridge(TrackRepository(conn))


@pytest.fixture
def backend() -> FakeBackend:
    return FakeBackend()


@pytest.fixture
def player_bridge(backend: FakeBackend, library: LibraryBridge) -> PlayerBridge:
    controller = PlaybackController(backend, volume=80)
    bridge = PlayerBridge(controller, library)
    # CRITICAL: keep strong references so GC doesn't collect them
    bridge._kept_backend = backend
    bridge._kept_library = library
    return bridge


class TestPlayerBridgePlayTrack:
    def test_play_track_loads_file(self, qapp, player_bridge: PlayerBridge, library: LibraryBridge, tmp_path: Path) -> None:
        track = make_track(title="Test", file_path=str(tmp_path / "test.mp3"))
        (tmp_path / "test.mp3").write_bytes(b"fake")
        stored = library.add_track(track)

        player_bridge.playPlaylist(1, library.ordered_track_ids(), stored.id)

        assert player_bridge.hasTrack is True
        assert player_bridge.isPlaying is True
        assert player_bridge.title == "Test"

    def test_play_nonexistent_track_emits_error(self, qapp, player_bridge: PlayerBridge) -> None:
        errors = []
        player_bridge.errorOccurred.connect(errors.append)

        player_bridge.playPlaylist(1, [999], 999)

        assert len(errors) == 1
        assert "không" in errors[0].lower() or "not" in errors[0].lower()

    def test_play_track_with_missing_file_emits_error(
        self, qapp, player_bridge: PlayerBridge, library: LibraryBridge, tmp_path: Path
    ) -> None:
        track = make_track(title="Missing", file_path=str(tmp_path / "nonexistent.mp3"))
        stored = library.add_track(track)
        errors = []
        player_bridge.errorOccurred.connect(errors.append)

        player_bridge.playPlaylist(1, library.ordered_track_ids(), stored.id)

        assert len(errors) == 1
        assert "Missing" in errors[0]


class TestPlayerBridgeToggle:
    def test_toggle_does_nothing_when_nothing_loaded(
        self, qapp, player_bridge: PlayerBridge, library: LibraryBridge, tmp_path: Path
    ) -> None:
        # The library stopped being a place to listen from, so a blind space bar
        # must NOT reach in and start playing something the user never picked.
        track = make_track(file_path=str(tmp_path / "first.mp3"))
        (tmp_path / "first.mp3").write_bytes(b"fake")
        library.add_track(track)

        player_bridge.toggle()

        assert player_bridge.isPlaying is False
        assert player_bridge.hasTrack is False


class TestPlayerBridgePrevious:
    def test_previous_within_restart_window_restarts_track(
        self, qapp, player_bridge: PlayerBridge, library: LibraryBridge, tmp_path: Path
    ) -> None:
        track = make_track(file_path=str(tmp_path / "test.mp3"))
        (tmp_path / "test.mp3").write_bytes(b"fake")
        stored = library.add_track(track)

        player_bridge.playPlaylist(1, library.ordered_track_ids(), stored.id)
        player_bridge._controller._position_ms = 2_000  # within 3-second restart window

        player_bridge.playPrevious()

        assert player_bridge.positionMs == 0

    def test_previous_after_restart_window_goes_to_previous_track(
        self, qapp, player_bridge: PlayerBridge, library: LibraryBridge, tmp_path: Path
    ) -> None:
        # Add in reverse order so library shows track1, track2 (newest first)
        track2 = make_track(file_path=str(tmp_path / "track2.mp3"))
        track1 = make_track(file_path=str(tmp_path / "track1.mp3"))
        (tmp_path / "track1.mp3").write_bytes(b"fake")
        (tmp_path / "track2.mp3").write_bytes(b"fake")
        stored2 = library.add_track(track2)
        stored1 = library.add_track(track1)

        # Queue will be [stored1, stored2]
        player_bridge.playPlaylist(1, library.ordered_track_ids(), stored1.id)
        # Move to second track first
        player_bridge._controller.next_id(manual=True)
        player_bridge.playNext()
        player_bridge._controller._position_ms = 2_000  # within 3-second window to go back

        player_bridge.playPrevious()

        assert player_bridge.trackId == stored1.id


class TestPlayerBridgeVolume:
    def test_set_volume_updates_property(self, qapp, player_bridge: PlayerBridge) -> None:
        player_bridge.setVolume(0.5)

        assert player_bridge.volume == 0.5
        assert player_bridge.volume_percent == 50


class TestPlayerBridgeSpeed:
    def test_set_speed_updates_property(self, qapp, player_bridge: PlayerBridge) -> None:
        player_bridge.setSpeed(1.25)

        assert player_bridge.speed == 1.25

    def test_set_speed_same_value_does_not_emit(self, qapp, player_bridge: PlayerBridge) -> None:
        signals: list[float] = []
        player_bridge.speedChanged.connect(lambda: signals.append(player_bridge.speed))

        player_bridge.setSpeed(1.0)  # default is already 1.0

        assert signals == []


class TestPlayerBridgeScope:
    """Playback scope: which track view is allowed to light up a row."""

    def test_scope_follows_the_playlist_it_was_started_from(
        self, qapp, player_bridge: PlayerBridge, library: LibraryBridge, tmp_path: Path
    ) -> None:
        (tmp_path / "a.mp3").write_bytes(b"fake")
        stored = library.add_track(make_track(file_path=str(tmp_path / "a.mp3")))

        player_bridge.playPlaylist(7, [stored.id], stored.id)

        assert player_bridge.scopePlaylistId == 7
        assert player_bridge.trackId == stored.id

    def test_empty_queue_reports_and_changes_nothing(
        self, qapp, player_bridge: PlayerBridge, library: LibraryBridge, tmp_path: Path
    ) -> None:
        (tmp_path / "a.mp3").write_bytes(b"fake")
        stored = library.add_track(make_track(file_path=str(tmp_path / "a.mp3")))
        player_bridge.playPlaylist(7, [stored.id], stored.id)
        errors: list[str] = []
        player_bridge.errorOccurred.connect(errors.append)

        player_bridge.playPlaylist(9, [], -1)

        assert len(errors) == 1
        assert player_bridge.scopePlaylistId == 7      # nothing was disturbed
        assert player_bridge.trackId == stored.id

    def test_negative_start_id_plays_the_first_song(
        self, qapp, player_bridge: PlayerBridge, library: LibraryBridge, tmp_path: Path
    ) -> None:
        for name in ("a.mp3", "b.mp3"):
            (tmp_path / name).write_bytes(b"fake")
        first = library.add_track(make_track(title="A", file_path=str(tmp_path / "a.mp3")))
        second = library.add_track(make_track(title="B", file_path=str(tmp_path / "b.mp3")))

        player_bridge.playPlaylist(3, [first.id, second.id], -1)

        assert player_bridge.trackId == first.id

    def test_stop_leaves_the_scope(
        self, qapp, player_bridge: PlayerBridge, library: LibraryBridge, tmp_path: Path
    ) -> None:
        (tmp_path / "a.mp3").write_bytes(b"fake")
        stored = library.add_track(make_track(file_path=str(tmp_path / "a.mp3")))
        player_bridge.playPlaylist(7, [stored.id], stored.id)

        player_bridge.stop()

        assert player_bridge.scopePlaylistId == -1

    def test_set_repeat_sets_the_mode_and_ignores_junk(
        self, qapp, player_bridge: PlayerBridge
    ) -> None:
        player_bridge.setRepeat("all")
        assert player_bridge.repeatMode == "all"

        player_bridge.setRepeat("sideways")
        assert player_bridge.repeatMode == "all"


class TestPreview:
    """Nghe thử: play a YouTube stream without downloading anything.

    The whole point is that it is OUTSIDE the library and outside every track,
    so nothing anywhere may light up because of it.
    """

    @pytest.fixture(autouse=True)
    def _no_network(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # preview() otherwise starts a real yt-dlp worker: slow, flaky, and it
        # outlives the test (the worker then emits into a deleted signal source).
        from lumen.bridge.preview_worker import PreviewResolver

        monkeypatch.setattr(PreviewResolver, "start", lambda self, video_id: None)

    def _resolved(self, player_bridge: PlayerBridge, **kwargs) -> None:
        from lumen.bridge.preview_worker import on_preview_resolved
        from lumen.core.stream import StreamInfo

        defaults = dict(
            url="https://stream.example/audio",
            title="Never Gonna Give You Up",
            uploader="Rick Astley",
            duration_ms=213_000,
            thumbnail="https://i.ytimg.com/vi/x/mqdefault.jpg",
        )
        on_preview_resolved(player_bridge, StreamInfo(**{**defaults, **kwargs}))

    def test_preview_plays_without_a_library_row(self, qapp, player_bridge: PlayerBridge) -> None:
        self._resolved(player_bridge)

        assert player_bridge.hasTrack is True
        assert player_bridge.title == "Never Gonna Give You Up"
        assert player_bridge.artist == "Rick Astley"
        # id -1 = no database row exists for this, so no view can match it.
        assert player_bridge.trackId == -1
        assert player_bridge.scopePlaylistId == -1

    def test_preview_is_never_counted_as_a_listen(
        self, qapp, player_bridge: PlayerBridge
    ) -> None:
        self._resolved(player_bridge)
        player_bridge._controller._position_ms = 10 * 60 * 1000   # long past any threshold

        assert player_bridge._controller.take_listen_credit(force=True) is None

    def test_preview_cover_is_a_web_url_not_a_file(
        self, qapp, player_bridge: PlayerBridge
    ) -> None:
        self._resolved(player_bridge)

        assert player_bridge.coverPath.startswith("https://")

    def test_starting_a_real_track_abandons_the_preview(
        self, qapp, player_bridge: PlayerBridge, library: LibraryBridge, tmp_path: Path
    ) -> None:
        (tmp_path / "a.mp3").write_bytes(b"fake")
        stored = library.add_track(make_track(file_path=str(tmp_path / "a.mp3")))
        player_bridge.preview("somevideo")
        assert player_bridge.previewVideoId == "somevideo"

        player_bridge.playPlaylist(4, [stored.id], stored.id)

        assert player_bridge.previewVideoId == ""
        assert player_bridge.scopePlaylistId == 4

    def test_failed_preview_clears_itself_and_reports(
        self, qapp, player_bridge: PlayerBridge
    ) -> None:
        from lumen.bridge.preview_worker import on_preview_failed

        player_bridge.preview("somevideo")
        errors: list[str] = []
        player_bridge.errorOccurred.connect(errors.append)

        on_preview_failed(player_bridge, "Không nghe thử được bài này.")

        assert player_bridge.previewVideoId == ""
        assert errors == ["Không nghe thử được bài này."]

    def test_stop_preview_leaves_nothing_loaded(self, qapp, player_bridge: PlayerBridge) -> None:
        player_bridge.preview("somevideo")
        self._resolved(player_bridge)

        player_bridge.stopPreview()

        assert player_bridge.hasTrack is False
        assert player_bridge.previewVideoId == ""


class TestPreviewFailureMessage:
    """YouTube có lúc từ chối phát trực tiếp dù bài vẫn tải về được bình thường.

    Đo được thật: ffmpeg gửi `Range: bytes=0-` (mở) và googlevideo trả 403,
    trong khi cùng URL đó với range có giới hạn lại trả 206. Báo "không phát
    được file này" ở đây là sai — người dùng sẽ tưởng bài hỏng.
    """

    @pytest.fixture(autouse=True)
    def _no_network(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from lumen.bridge.preview_worker import PreviewResolver

        monkeypatch.setattr(PreviewResolver, "start", lambda self, video_id: None)

    def test_a_failing_preview_says_it_is_youtube_not_the_file(
        self, qapp, player_bridge: PlayerBridge
    ) -> None:
        player_bridge.preview("somevideo")
        errors: list[str] = []
        player_bridge.errorOccurred.connect(errors.append)

        player_bridge._onFailed("Không phát được file này.")

        assert len(errors) == 1
        assert "YouTube" in errors[0]
        assert "Tải về" in errors[0]
        assert player_bridge.previewVideoId == ""

    def test_a_failing_local_file_keeps_the_original_message(
        self, qapp, player_bridge: PlayerBridge
    ) -> None:
        errors: list[str] = []
        player_bridge.errorOccurred.connect(errors.append)

        player_bridge._onFailed("Không phát được file này.")

        assert errors == ["Không phát được file này."]


class TestDeletingWhilePlaying:
    """Xoá bài ĐANG PHÁT phải dừng nhạc, không phát tiếp file đã biến mất.

    Chủ dự án gặp: xoá bài trong track mà nhạc vẫn chạy tới khi bấm sang bài
    khác. PlayerBridge chỉ nghe LibraryBridge; xoá trong track đi qua
    TrackSongsBridge nên không ai báo cho player.
    """

    def test_removing_the_current_track_stops_playback(
        self, qapp, player_bridge: PlayerBridge, library: LibraryBridge, tmp_path: Path
    ) -> None:
        (tmp_path / "a.mp3").write_bytes(b"fake")
        stored = library.add_track(make_track(file_path=str(tmp_path / "a.mp3")))
        player_bridge.playPlaylist(3, [stored.id], stored.id)
        assert player_bridge.isPlaying is True

        # Đúng tín hiệu mà TrackSongsBridge.trackRemoved nối vào.
        player_bridge._onTrackRemoved(stored.id)

        assert player_bridge.hasTrack is False
        assert player_bridge.isPlaying is False

    def test_removing_another_song_leaves_playback_alone(
        self, qapp, player_bridge: PlayerBridge, library: LibraryBridge, tmp_path: Path
    ) -> None:
        for name in ("a.mp3", "b.mp3"):
            (tmp_path / name).write_bytes(b"fake")
        playing = library.add_track(make_track(title="A", file_path=str(tmp_path / "a.mp3")))
        other = library.add_track(make_track(title="B", file_path=str(tmp_path / "b.mp3")))
        player_bridge.playPlaylist(3, [playing.id, other.id], playing.id)

        player_bridge._onTrackRemoved(other.id)

        assert player_bridge.trackId == playing.id
        assert player_bridge.isPlaying is True


class TestARenameReachesThePlayerBar:
    """Đổi tên ĐÚNG bài đang phát: thanh phát, Mini và MPRIS phải đổi theo.

    `PlaybackController` giữ BẢN SAO Track lấy lúc bài bắt đầu, nên đổi tên
    dưới thư viện không tự tới được chỗ nó — thiếu dây thì tên cũ nằm trên
    thanh phát tới khi sang bài khác. Đúng hình dạng CB-029.
    """

    def _dang_phat(self, player_bridge, library, tmp_path):
        (tmp_path / "a.mp3").write_bytes(b"fake")
        stored = library.add_track(make_track(title="ten cu", file_path=str(tmp_path / "a.mp3")))
        player_bridge.playPlaylist(3, [stored.id], stored.id)
        return stored

    def test_ten_tren_thanh_phat_doi_theo(self, qapp, player_bridge, library, tmp_path) -> None:
        stored = self._dang_phat(player_bridge, library, tmp_path)

        # Đúng tín hiệu mà TrackSongsBridge.songRenamed nối vào.
        player_bridge.onSongRenamed(stored.id, "ten moi")

        assert player_bridge.title == "ten moi"

    def test_mpris_duoc_danh_thuc(self, qapp, player_bridge, library, tmp_path) -> None:
        """MPRIS (thanh Noctalia, playerctl, phím media) nghe đúng `trackChanged`."""
        stored = self._dang_phat(player_bridge, library, tmp_path)
        keu = []
        player_bridge.trackChanged.connect(lambda: keu.append(player_bridge.title))

        player_bridge.onSongRenamed(stored.id, "ten moi")

        assert keu == ["ten moi"]

    def test_doi_ten_bai_KHAC_thi_khong_dong_gi(self, qapp, player_bridge, library, tmp_path) -> None:
        self._dang_phat(player_bridge, library, tmp_path)
        (tmp_path / "b.mp3").write_bytes(b"fake")
        khac = library.add_track(make_track(title="B", file_path=str(tmp_path / "b.mp3")))
        keu = []
        player_bridge.trackChanged.connect(lambda: keu.append(1))

        player_bridge.onSongRenamed(khac.id, "ten moi")

        assert player_bridge.title == "ten cu"
        assert keu == [], "bắn trackChanged vô cớ là bắt MPRIS phát lại metadata không đổi"

    def test_khong_phat_gi_thi_khong_no(self, qapp, player_bridge) -> None:
        player_bridge.onSongRenamed(1, "ten moi")

        assert player_bridge.hasTrack is False

    def test_file_tren_dia_khong_bi_dung_toi(self, qapp, player_bridge, library, tmp_path) -> None:
        """Đổi cái NHÌN THẤY không được đụng tới cái đang chạy trong mpv."""
        stored = self._dang_phat(player_bridge, library, tmp_path)
        truoc = player_bridge._controller.track.file_path

        player_bridge.onSongRenamed(stored.id, "ten moi")

        assert player_bridge._controller.track.file_path == truoc
        assert player_bridge.isPlaying is True


class TestASyncRenameReachesThePlayerBar:
    """Máy KIA đổi tên bài đang phát: thanh phát và MPRIS phải đổi theo.

    Khác hẳn `TestARenameReachesThePlayerBar` ở chỗ ai gọi: không ai gõ gì trên
    máy này, nên không danh sách nào bắn `songRenamed`. Vòng đồng bộ ghi thẳng
    vào SQLite sau lưng mọi model rồi kêu một tiếng `libraryChanged` TRỐNG
    KHÔNG — thanh phát phải tự đọc lại database mới biết tên đã đổi.
    """

    def _dang_phat(self, player_bridge, library, tmp_path):
        (tmp_path / "a.mp3").write_bytes(b"fake")
        stored = library.add_track(make_track(title="ten cu", file_path=str(tmp_path / "a.mp3")))
        player_bridge.playPlaylist(3, [stored.id], stored.id)
        return stored

    def _dong_bo_doi_ten(self, library, track_id: int, ten_moi: str) -> None:
        """Giả đúng cái vòng đồng bộ làm: ghi thẳng database, không báo ai."""
        library._repository.rename(track_id, ten_moi)

    def test_ten_tren_thanh_phat_doi_theo(self, qapp, player_bridge, library, tmp_path) -> None:
        stored = self._dang_phat(player_bridge, library, tmp_path)
        self._dong_bo_doi_ten(library, stored.id, "ten may kia")

        player_bridge.onLibraryChanged()

        assert player_bridge.title == "ten may kia"

    def test_mpris_duoc_danh_thuc_dung_mot_lan(self, qapp, player_bridge, library, tmp_path) -> None:
        stored = self._dang_phat(player_bridge, library, tmp_path)
        self._dong_bo_doi_ten(library, stored.id, "ten may kia")
        keu = []
        player_bridge.trackChanged.connect(lambda: keu.append(player_bridge.title))

        player_bridge.onLibraryChanged()

        assert keu == ["ten may kia"]

    def test_dong_bo_khong_doi_ten_thi_khong_dong_gi(self, qapp, player_bridge, library, tmp_path) -> None:
        """Vòng đồng bộ nào cũng kêu `libraryChanged`, phần lớn không đụng tên.

        Bắn `trackChanged` vô cớ là bắt MPRIS phát lại metadata y hệt cũ.
        """
        self._dang_phat(player_bridge, library, tmp_path)
        keu = []
        player_bridge.trackChanged.connect(lambda: keu.append(1))

        player_bridge.onLibraryChanged()

        assert player_bridge.title == "ten cu"
        assert keu == []

    def test_doi_ten_bai_KHAC_thi_khong_dong_gi(self, qapp, player_bridge, library, tmp_path) -> None:
        self._dang_phat(player_bridge, library, tmp_path)
        (tmp_path / "b.mp3").write_bytes(b"fake")
        khac = library.add_track(make_track(title="B", file_path=str(tmp_path / "b.mp3")))
        keu = []
        player_bridge.trackChanged.connect(lambda: keu.append(1))

        self._dong_bo_doi_ten(library, khac.id, "ten may kia")
        player_bridge.onLibraryChanged()

        assert player_bridge.title == "ten cu"
        assert keu == []

    def test_khong_phat_gi_thi_khong_no(self, qapp, player_bridge) -> None:
        player_bridge.onLibraryChanged()

        assert player_bridge.hasTrack is False

    def test_bai_bi_dong_bo_xoa_mat_thi_de_yen(self, qapp, player_bridge, library, tmp_path) -> None:
        """Đọc lại không thấy bài nữa: KHÔNG tự dừng nhạc ở đây.

        Dừng nhạc là việc của `trackRemoved`. Đoán từ chỗ này thì một lần hoà
        chỉ đổi thứ tự cũng đủ cắt ngang bài đang nghe.
        """
        stored = self._dang_phat(player_bridge, library, tmp_path)
        library._repository.delete(stored.id)

        player_bridge.onLibraryChanged()

        assert player_bridge.isPlaying is True
        assert player_bridge.title == "ten cu"

    def test_file_tren_dia_khong_bi_dung_toi(self, qapp, player_bridge, library, tmp_path) -> None:
        stored = self._dang_phat(player_bridge, library, tmp_path)
        truoc = player_bridge._controller.track.file_path
        self._dong_bo_doi_ten(library, stored.id, "ten may kia")

        player_bridge.onLibraryChanged()

        assert player_bridge._controller.track.file_path == truoc
        assert player_bridge.isPlaying is True
