"""Kênh điều khiển: một lệnh `lumen` mới phải nói được với bản đang chạy."""

from __future__ import annotations

import os
import sys
import subprocess
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from lumen.core import cli, ipc, paths  # noqa: E402
from lumen.services.control import ControlServer  # noqa: E402

PROBE = Path(__file__).resolve().parent / "control_probe.py"


@pytest.fixture(scope="module")
def qapp() -> QGuiApplication:
    return QGuiApplication.instance() or QGuiApplication([])


@pytest.fixture
def server(qapp, tmp_path: Path):
    made = ControlServer()
    assert made.start(str(tmp_path / "control.sock")) is True
    yield made
    made.stop()


@contextmanager
def _holding(path: Path):
    """Chạy một tiến trình khác đang giữ socket ở `path`."""
    probe = subprocess.Popen(
        [sys.executable, str(PROBE), str(path)], stdout=subprocess.PIPE, text=True
    )
    try:
        assert probe.stdout is not None
        assert probe.stdout.readline().strip() == "ready", "tiến trình giữ socket không khởi động"
        yield probe
    finally:
        probe.terminate()
        probe.wait(timeout=5)


def _send_while_serving(command: str, path: Path, seconds: float = 2.0) -> bool:
    """Gửi từ một luồng khác trong lúc luồng chính quay vòng lặp sự kiện.

    `send` chặn cho tới khi có trả lời, mà trả lời chỉ tới khi server được chạy
    — nên hai việc phải song song. Dùng sleep chứ không dùng QTest.qWait: qWait
    giữ GIL nên luồng gửi gần như không nhúc nhích (CLAUDE.md mục 8.3).
    """
    result: list[bool] = []
    worker = threading.Thread(target=lambda: result.append(ipc.send(command, address=str(path))))
    worker.start()
    end = time.time() + seconds
    while worker.is_alive() and time.time() < end:
        QCoreApplication.processEvents()
        time.sleep(0.01)
    worker.join(timeout=1.0)
    assert result, "client thread never finished"
    return result[0]


class TestAddressing:
    def test_socket_lives_in_the_runtime_dir(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))

        assert paths.control_address() == str(tmp_path / "lumen-control.sock")

    def test_falls_back_when_there_is_no_runtime_dir(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

        assert paths.control_address() == str(tmp_path / "lumen" / "control.sock")


class TestMessages:
    def test_round_trip(self) -> None:
        assert ipc.decode(ipc.encode(ipc.CMD_SHOW)) == ipc.CMD_SHOW

    def test_a_newline_can_never_hide_a_second_command(self) -> None:
        with pytest.raises(ValueError):
            ipc.encode("show\nquit")

    def test_oversized_payload_is_dropped(self) -> None:
        assert ipc.decode(b"x" * (ipc.MAX_MESSAGE + 1)) == ""

    def test_sending_an_unknown_command_is_a_programming_error(self) -> None:
        with pytest.raises(ValueError):
            ipc.send("rm -rf")


class TestDelivery:
    def test_command_reaches_the_running_instance(self, server) -> None:
        seen: list[str] = []
        server.commandReceived.connect(seen.append)

        assert _send_while_serving(ipc.CMD_SHOW, server.address) is True
        assert seen == [ipc.CMD_SHOW]

    def test_nobody_listening_is_answered_with_false(self, tmp_path: Path) -> None:
        assert ipc.send(ipc.CMD_PING, address=str(tmp_path / "nothing.sock")) is False

    def test_two_commands_in_a_row_both_arrive(self, server) -> None:
        seen: list[str] = []
        server.commandReceived.connect(seen.append)

        _send_while_serving(ipc.CMD_PING, server.address)
        _send_while_serving(ipc.CMD_SHOW, server.address)

        assert seen == [ipc.CMD_PING, ipc.CMD_SHOW]


class TestStaleSocket:
    def test_a_leftover_socket_file_does_not_block_startup(self, qapp, tmp_path: Path) -> None:
        """Thoát đột ngột để lại file socket chết; không dọn thì app không bao giờ nghe lại được."""
        path = tmp_path / "control.sock"
        path.write_bytes(b"")

        made = ControlServer()
        try:
            assert made.start(str(path)) is True
            assert _send_while_serving(ipc.CMD_PING, path) is True
        finally:
            made.stop()

    def test_stopping_removes_the_socket_file(self, qapp, tmp_path: Path) -> None:
        path = tmp_path / "control.sock"
        made = ControlServer()
        made.start(str(path))

        made.stop()

        assert not path.exists()


class TestFastPath:
    """Cửa trước phải trả lời được mà không cần Qt — xem core/cli.py."""

    def test_starts_the_app_when_nothing_is_running(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))

        assert cli.handle_fast_path([]) is None

    def test_quitting_nothing_reports_failure(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))

        assert cli.handle_fast_path(["--quit"]) == 1

    def test_a_second_launch_defers_to_the_running_one(
        self, qapp, monkeypatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
        made = ControlServer()
        assert made.start() is True
        seen: list[str] = []
        made.commandReceived.connect(seen.append)
        try:
            result: list[int | None] = []
            worker = threading.Thread(target=lambda: result.append(cli.handle_fast_path([])))
            worker.start()
            end = time.time() + 2.0
            while worker.is_alive() and time.time() < end:
                QCoreApplication.processEvents()
                time.sleep(0.01)
            worker.join(timeout=1.0)
        finally:
            made.stop()

        assert result == [0], "phải thoát ngay, không mở app thứ hai"
        assert seen == [ipc.CMD_SHOW]

    def test_the_front_door_never_imports_qt(self) -> None:
        """Nạp PySide6 mất ~2s; đo được: 1.98s trước khi tách, 0.13s sau khi tách."""
        source = (
            Path(__file__).resolve().parent.parent / "src" / "lumen" / "__main__.py"
        ).read_text(encoding="utf-8")

        assert "PySide6" not in source
        assert "from lumen.app import" in source, "phải nạp app MUỘN, trong thân hàm"


class TestMiniCommand:
    """`lumen --mini` là đường đi của phím tắt SUPER+M."""

    def test_mini_is_a_known_command(self) -> None:
        assert ipc.is_valid(ipc.CMD_MINI)

    def test_it_reaches_the_running_instance(self, server) -> None:
        seen: list[str] = []
        server.commandReceived.connect(seen.append)

        assert _send_while_serving(ipc.CMD_MINI, server.address) is True
        assert seen == [ipc.CMD_MINI]

    def test_with_no_instance_it_asks_for_the_app_to_start(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        """Bấm phím tắt khi Lumen chưa chạy thì phải MỞ app, không phải báo lỗi."""
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))

        assert cli.handle_fast_path(["--mini"]) is None

    def test_with_an_instance_it_only_sends_and_stops(
        self, qapp, monkeypatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
        made = ControlServer()
        assert made.start() is True
        seen: list[str] = []
        made.commandReceived.connect(seen.append)
        try:
            result: list[int | None] = []
            worker = threading.Thread(
                target=lambda: result.append(cli.handle_fast_path(["--mini"]))
            )
            worker.start()
            end = time.time() + 2.0
            while worker.is_alive() and time.time() < end:
                QCoreApplication.processEvents()
                time.sleep(0.01)
            worker.join(timeout=1.0)
        finally:
            made.stop()

        assert result == [0]
        assert seen == [ipc.CMD_MINI]


class TestNoSecondInstanceCanStealTheSocket:
    """Đã xảy ra thật: hai Lumen cùng chạy, chỉ một cái gọi tới được."""

    def test_a_second_instance_refuses_to_take_over(self, qapp, tmp_path: Path) -> None:
        path = tmp_path / "control.sock"
        with _holding(path):
            thief = ControlServer()
            try:
                claimed = thief.start(str(path))
            finally:
                thief.stop()

            assert claimed is False, "bản thứ hai đã cướp socket của bản đang sống"
            assert _send_while_serving(ipc.CMD_PING, path) is True, "bản đầu phải còn trả lời"

    def test_a_dead_socket_file_can_still_be_reclaimed(self, qapp, tmp_path: Path) -> None:
        """Không được cẩn thận tới mức không bao giờ dọn được rác."""
        path = tmp_path / "control.sock"
        path.write_bytes(b"")

        made = ControlServer()
        try:
            assert made.start(str(path)) is True
        finally:
            made.stop()
