"""Đường dẫn và kênh điều khiển phải đúng trên CẢ Linux lẫn Windows.

Chạy được trên máy Linux nhờ giả lập `paths.on_windows()` — không thay được cho
một lần chạy thật trên Windows, nhưng bắt được mọi chỗ còn đóng cứng chuẩn XDG.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lumen.core import paths  # noqa: E402


@pytest.fixture
def windows(monkeypatch, tmp_path: Path):
    """Giả làm Windows, với %APPDATA% và %LOCALAPPDATA% nằm trong tmp_path."""
    monkeypatch.setattr(paths, "on_windows", lambda: True)
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "user"))
    return tmp_path


@pytest.fixture
def linux(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(paths, "on_windows", lambda: False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    return tmp_path


class TestWindowsFolders:
    def test_data_goes_to_local_appdata(self, windows: Path) -> None:
        """Database và ảnh bìa gắn với MỘT máy, không nên đồng bộ theo hồ sơ người dùng."""
        assert paths.data_dir() == windows / "Local" / "Lumen"

    def test_config_goes_to_roaming_appdata(self, windows: Path) -> None:
        """Cấu hình thì NÊN đi theo người dùng sang máy khác."""
        assert paths.config_dir() == windows / "Roaming" / "Lumen"

    def test_log_and_cache_stay_local(self, windows: Path) -> None:
        assert paths.state_dir() == windows / "Local" / "Lumen" / "state"
        assert paths.cache_dir() == windows / "Local" / "Lumen" / "cache"

    def test_music_lands_in_the_user_music_folder(self, windows: Path) -> None:
        assert paths.music_dir() == windows / "user" / "Music" / "Lumen"

    def test_nothing_falls_back_to_xdg(self, windows: Path, monkeypatch) -> None:
        """Đặt biến XDG trên Windows KHÔNG được ảnh hưởng gì — máy Windows không có chúng."""
        monkeypatch.setenv("XDG_DATA_HOME", "/khong-duoc-dung")

        assert str(paths.data_dir()).startswith(str(windows / "Local"))

    def test_it_works_even_without_the_environment_variables(self, monkeypatch, tmp_path) -> None:
        """Một số môi trường Windows không có %APPDATA% — không được văng lỗi."""
        monkeypatch.setattr(paths, "on_windows", lambda: True)
        monkeypatch.delenv("APPDATA", raising=False)
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "user"))

        assert paths.data_dir() == tmp_path / "user" / "AppData" / "Local" / "Lumen"


class TestLinuxFoldersStayTheSame:
    def test_data_and_config_follow_xdg(self, linux: Path) -> None:
        assert paths.data_dir() == linux / "share" / "lumen"
        assert paths.config_dir() == linux / "config" / "lumen"


class TestControlAddress:
    def test_windows_uses_a_pipe_name_not_a_path(self, windows: Path) -> None:
        """Windows không có socket kiểu file; Qt dựng named pipe từ một cái TÊN."""
        address = paths.control_address()

        assert address == "lumen-control"
        assert "/" not in address and "\\" not in address

    def test_linux_uses_a_file_path(self, linux: Path, monkeypatch) -> None:
        monkeypatch.setenv("XDG_RUNTIME_DIR", str(linux / "run"))

        assert paths.control_address() == str(linux / "run" / "lumen-control.sock")
