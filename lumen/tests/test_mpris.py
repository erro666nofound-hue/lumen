"""MPRIS: những gì Lumen kể cho thanh trạng thái và playerctl nghe."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtDBus import QDBusObjectPath  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from lumen.services.mpris import MprisService  # noqa: E402

_US_PER_MS = 1000


@dataclass
class FakePlayer:
    """Đủ đúng những gì MprisService đọc, không hơn."""

    hasTrack: bool = True  # noqa: N815 (khớp tên thuộc tính của PlayerBridge)
    isPlaying: bool = True  # noqa: N815
    trackId: int = 7  # noqa: N815
    title: str = "discopled"
    artist: str = "Zachz Winner"
    coverPath: str = "/home/user/.local/share/lumen/covers/abc.jpg"  # noqa: N815
    durationMs: int = 86504  # noqa: N815


@pytest.fixture(scope="module")
def qapp() -> QGuiApplication:
    return QGuiApplication.instance() or QGuiApplication([])


@pytest.fixture
def service(qapp) -> MprisService:
    """KHÔNG gọi start(): test không được chiếm tên trên bus thật của người dùng."""
    return MprisService(FakePlayer())


class TestPlaybackStatus:
    def test_playing(self, service) -> None:
        assert service.playback_status() == "Playing"

    def test_paused(self, service) -> None:
        service.player.isPlaying = False

        assert service.playback_status() == "Paused"

    def test_nothing_loaded_is_stopped_not_paused(self, service) -> None:
        """Chuẩn MPRIS phân biệt "đang dừng giữa bài" với "chẳng có bài nào"."""
        service.player.hasTrack = False
        service.player.isPlaying = False

        assert service.playback_status() == "Stopped"


class TestMetadata:
    def test_title_and_artist(self, service) -> None:
        data = service.metadata()

        assert data["xesam:title"] == "discopled"
        assert data["xesam:artist"] == ["Zachz Winner"]

    def test_artist_is_a_list_even_when_there_is_one(self, service) -> None:
        """`xesam:artist` là mảng theo chuẩn; đưa chuỗi thì client hiện từng ký tự."""
        assert isinstance(service.metadata()["xesam:artist"], list)

    def test_no_artist_gives_an_empty_list(self, service) -> None:
        service.player.artist = ""

        assert service.metadata()["xesam:artist"] == []

    def test_length_is_microseconds(self, service) -> None:
        """MPRIS đo bằng micro-giây, app đo bằng mili-giây — sai chỗ này là lệch 1000 lần."""
        assert service.metadata()["mpris:length"] == 86504 * _US_PER_MS

    def test_cover_becomes_a_file_url(self, service) -> None:
        assert service.metadata()["mpris:artUrl"].startswith("file:///")

    def test_no_cover_means_no_art_key(self, service) -> None:
        """Gửi artUrl rỗng làm một số thanh trạng thái hiện ô ảnh vỡ."""
        service.player.coverPath = ""

        assert "mpris:artUrl" not in service.metadata()

    def test_track_id_is_a_real_object_path_not_a_string(self, service) -> None:
        """Chuỗi thì playerctl vẫn đọc, nhưng client có kiểu chặt bỏ luôn player."""
        track = service.metadata()["mpris:trackid"]

        assert isinstance(track, QDBusObjectPath)
        assert track.path().startswith("/")

    def test_nothing_loaded_means_empty_metadata(self, service) -> None:
        service.player.hasTrack = False

        assert service.metadata() == {}


def test_invalidated_list_is_a_string_array_not_variants() -> None:
    """PropertiesChanged must be sa{sv}as, or Quickshell drops it (CB-057)."""
    from lumen.services.mpris import no_invalidated_properties

    assert no_invalidated_properties().currentSignature() == "as"
