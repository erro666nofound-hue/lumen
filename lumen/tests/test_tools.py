"""Tìm libmpv và ffmpeg khi app đã được đóng gói.

Chạy từ mã nguồn thì hai thứ này có sẵn trong hệ thống. Bản đóng gói thì không —
sai chỗ này là app mở lên chết ngay ở bước phát nhạc, trên máy người dùng, sau
khi mọi test đã xanh.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lumen.core import paths, tools  # noqa: E402


@pytest.fixture
def bundled(monkeypatch, tmp_path: Path) -> Path:
    """Giả làm bản đã đóng gói, với thư mục runtime nằm cạnh file chạy."""
    exe = tmp_path / "Lumen"
    exe.write_text("")
    runtime = tmp_path / tools.BUNDLED_DIR_NAME
    runtime.mkdir()
    monkeypatch.setattr(tools, "is_frozen", lambda: True)
    monkeypatch.setattr(sys, "executable", str(exe))
    return runtime


class TestFindingFfmpeg:
    def test_the_bundled_one_wins(self, bundled: Path, monkeypatch) -> None:
        monkeypatch.setattr(paths, "on_windows", lambda: False)
        (bundled / "ffmpeg").write_text("")

        assert tools.ffmpeg_path() == str(bundled / "ffmpeg")

    def test_windows_looks_for_the_exe(self, bundled: Path, monkeypatch) -> None:
        monkeypatch.setattr(paths, "on_windows", lambda: True)
        (bundled / "ffmpeg.exe").write_text("")

        assert tools.ffmpeg_path() == str(bundled / "ffmpeg.exe")

    def test_without_a_bundle_it_falls_back_to_the_system(self, monkeypatch) -> None:
        monkeypatch.setattr(tools, "is_frozen", lambda: False)

        assert tools.ffmpeg_path().endswith("ffmpeg")

    def test_a_bundle_without_ffmpeg_still_falls_back(self, bundled: Path, monkeypatch) -> None:
        """Gói thiếu ffmpeg thì dùng của hệ thống, đừng trả về đường dẫn không tồn tại."""
        monkeypatch.setattr(paths, "on_windows", lambda: False)

        assert tools.ffmpeg_path().endswith("ffmpeg")
        assert str(bundled) not in tools.ffmpeg_path()


class TestPreparingTheRuntime:
    def test_the_bundle_goes_to_the_front_of_path(self, bundled: Path, monkeypatch) -> None:
        """python-mpv tra %PATH% để tìm libmpv — bản đi kèm phải đứng trước."""
        monkeypatch.setattr(paths, "on_windows", lambda: False)
        monkeypatch.setenv("PATH", "/usr/bin")

        tools.prepare_runtime()

        assert os.environ["PATH"].startswith(str(bundled))

    def test_windows_declares_the_dll_folder(self, bundled: Path, monkeypatch) -> None:
        """Từ Python 3.8, Windows không tra PATH khi nạp DLL — phải khai tường minh."""
        monkeypatch.setattr(paths, "on_windows", lambda: True)
        declared: list[str] = []
        monkeypatch.setattr(os, "add_dll_directory", declared.append, raising=False)

        tools.prepare_runtime()

        assert declared == [str(bundled)]

    def test_running_from_source_changes_nothing(self, monkeypatch) -> None:
        monkeypatch.setattr(tools, "is_frozen", lambda: False)
        monkeypatch.setenv("PATH", "/usr/bin")

        tools.prepare_runtime()

        assert os.environ["PATH"] == "/usr/bin"

    def test_a_missing_runtime_folder_is_not_a_crash(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(tools, "is_frozen", lambda: True)
        monkeypatch.setattr(sys, "executable", str(tmp_path / "Lumen"))

        tools.prepare_runtime()
