"""Lệnh cho trợ lý: `lumen --play/--pause/--seek/--mute/--volume/--status` (2026-10-16)."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from lumen.bridge.remote_commands import RemoteCommands  # noqa: E402
from lumen.core import cli, ipc, paths  # noqa: E402
from lumen.services.control import ControlServer  # noqa: E402


class _Player:
    """Đủ những gì RemoteCommands hỏi PlayerBridge — không cần mpv."""

    def __init__(self, loaded: bool = True) -> None:
        self.hasTrack = loaded
        self.isPlaying = False
        self.positionMs = 50_000
        self.durationMs = 180_000
        self.volume = 0.6
        self.title = "doodle"
        self.artist = "Zachz Winner"
        self.trackId = 7
        self.scopePlaylistId = 2
        self.started: list[int] = []

    def toggle(self) -> None:
        self.isPlaying = not self.isPlaying

    def seek(self, position_ms: int) -> None:
        self.positionMs = position_ms

    def setVolume(self, value: float) -> None:
        self.volume = value

    def setRepeat(self, mode: str) -> None:
        pass

    def playPlaylist(self, playlist_id: int, track_ids: list, start_id: int) -> None:
        self.started.append(playlist_id)
        self.hasTrack = self.isPlaying = True

    def playNext(self) -> None:
        pass

    def playPrevious(self) -> None:
        pass


class _Playlists:
    def firstPlayable(self) -> int:
        return 3

    def orderedIds(self, playlist_id: int) -> list:
        return [11, 12]


def _remote(player: _Player) -> RemoteCommands:
    return RemoteCommands(player, _Playlists())  # type: ignore[arg-type]


class TestArguments:
    @pytest.mark.parametrize("command", ["play", "pause", "mute", "status", "seek +10", "seek -10",
                                         "seek 30", "volume 0", "volume 100"])
    def test_hop_le(self, command: str) -> None:
        assert ipc.is_valid(command)

    @pytest.mark.parametrize("command", ["seek", "seek x", "seek 1.5", "volume", "volume 101",
                                         "volume -1", "play 1", "status now", "rm -rf"])
    def test_bi_tu_choi(self, command: str) -> None:
        assert not ipc.is_valid(command)

    def test_seek_am_doc_duoc_tu_dong_lenh(self) -> None:
        """`--seek -10` không được bị argparse hiểu nhầm thành một cờ."""
        assert cli.parse(["--seek", "-10"]).seek == "-10"


class TestRemoteCommands:
    def test_seek_tuong_doi_va_tuyet_doi(self) -> None:
        player = _Player()
        remote = _remote(player)
        remote.run("seek +10")
        assert player.positionMs == 60_000
        remote.run("seek -100")
        assert player.positionMs == 0, "lùi quá đầu bài thì dừng ở 0"
        remote.run("seek 999")
        assert player.positionMs == player.durationMs, "tiến quá cuối bài thì dừng ở cuối"
        remote.run("seek 30")
        assert player.positionMs == 30_000

    def test_play_pause_khong_dao_trang_thai(self) -> None:
        """`--play` khi đang phát không được dừng nhạc (khác `--toggle`)."""
        player = _Player()
        remote = _remote(player)
        remote.run("play")
        remote.run("play")
        assert player.isPlaying
        remote.run("pause")
        remote.run("pause")
        assert not player.isPlaying

    def test_play_luc_chua_co_bai_chay_track_dau(self) -> None:
        player = _Player(loaded=False)
        _remote(player).run("play")
        assert player.started == [3]

    def test_mute_nho_am_luong_cu(self) -> None:
        player = _Player()
        remote = _remote(player)
        remote.run("mute")
        assert player.volume == 0
        remote.run("mute")
        assert player.volume == pytest.approx(0.6)

    def test_volume(self) -> None:
        player = _Player()
        _remote(player).run("volume 25")
        assert player.volume == pytest.approx(0.25)

    def test_status_la_json_du_truong(self) -> None:
        player = _Player()
        data = json.loads(_remote(player).status())
        assert data["title"] == "doodle"
        assert data["position_s"] == 50.0
        assert data["paused"] is True and data["playing"] is False
        assert data["volume"] == 60


@pytest.fixture(scope="module")
def qapp() -> QGuiApplication:
    return QGuiApplication.instance() or QGuiApplication([])


def _request_while_serving(command: str, path: str) -> str | None:
    """Hỏi từ luồng khác trong lúc luồng chính quay vòng lặp sự kiện (xem test_control_socket)."""
    result: list[str | None] = []
    worker = threading.Thread(target=lambda: result.append(ipc.request(command, address=path)))
    worker.start()
    end = time.time() + 2.0
    while worker.is_alive() and time.time() < end:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    worker.join(timeout=1.0)
    assert result, "client thread never finished"
    return result[0]


class TestStatusOverTheSocket:
    def test_tra_loi_bang_du_lieu_dai(self, qapp, tmp_path: Path) -> None:
        """Tên bài dài vượt 256 byte vẫn phải về nguyên vẹn."""
        server = ControlServer()
        assert server.start(str(tmp_path / "control.sock"))
        long_title = "ブルーアーカイブ " * 40
        server.status_provider = lambda: json.dumps({"title": long_title}, ensure_ascii=False)
        try:
            answer = _request_while_serving(ipc.CMD_STATUS, str(tmp_path / "control.sock"))
        finally:
            server.stop()
        assert answer is not None
        assert json.loads(answer)["title"] == long_title

    def test_khong_ai_chay_thi_noi_ro(self, monkeypatch, tmp_path: Path, capsys) -> None:
        monkeypatch.setattr(paths, "control_address", lambda: str(tmp_path / "nothing.sock"))
        assert cli.handle_fast_path(["--status"]) == 1
        assert json.loads(capsys.readouterr().out) == {"running": False}
