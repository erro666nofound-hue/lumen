"""Tests for configuration loading and saving."""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from unittest.mock import patch

import pytest

from lumen.core import paths
from lumen.core.config import Config, load_config, save_config


@pytest.fixture
def tmp_config_file(tmp_path: Path) -> Path:
    """Provide a temporary config file path."""
    return tmp_path / "config.json"


class TestConfigDefaults:
    def test_config_defaults(self) -> None:
        cfg = Config()
        assert cfg.volume == 80
        assert cfg.playback_speed == 1.0
        assert cfg.window_width == 1040
        assert cfg.window_height == 660


class TestLoadConfigDefaults:
    def test_load_config_returns_defaults_when_file_missing(self, tmp_config_file: Path) -> None:
        with patch("lumen.core.config.paths.config_path", return_value=tmp_config_file):
            cfg = load_config()

        assert cfg.volume == 80

    def test_load_config_from_file(self, tmp_config_file: Path) -> None:
        import json

        data = {"volume": 50, "window_width": 1200, "audio_bitrate": "320"}
        tmp_config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_config_file, "w") as f:
            json.dump(data, f)

        with patch("lumen.core.config.paths.config_path", return_value=tmp_config_file):
            cfg = load_config()

        assert cfg.volume == 50
        assert cfg.window_width == 1200
        assert cfg.audio_bitrate == "320"

    def test_load_config_clamps_volume(self, tmp_config_file: Path) -> None:
        import json

        data = {"volume": 150}
        tmp_config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_config_file, "w") as f:
            json.dump(data, f)

        with patch("lumen.core.config.paths.config_path", return_value=tmp_config_file):
            cfg = load_config()

        assert cfg.volume == 100

    def test_load_config_clamps_negative_volume(self, tmp_config_file: Path) -> None:
        import json

        data = {"volume": -10}
        tmp_config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_config_file, "w") as f:
            json.dump(data, f)

        with patch("lumen.core.config.paths.config_path", return_value=tmp_config_file):
            cfg = load_config()

        assert cfg.volume == 0

    def test_load_config_handles_corrupted_json(self, tmp_config_file: Path) -> None:
        tmp_config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_config_file, "w") as f:
            f.write("{invalid json")

        with patch("lumen.core.config.paths.config_path", return_value=tmp_config_file):
            cfg = load_config()

        assert cfg.volume == 80  # falls back to default


class TestLoadConfigPlaybackSpeed:
    def test_load_config_reads_playback_speed(self, tmp_config_file: Path) -> None:
        import json

        data = {"playback_speed": 1.25}
        tmp_config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_config_file, "w") as f:
            json.dump(data, f)

        with patch("lumen.core.config.paths.config_path", return_value=tmp_config_file):
            cfg = load_config()

        assert cfg.playback_speed == 1.25

    def test_load_config_clamps_playback_speed(self, tmp_config_file: Path) -> None:
        import json

        data = {"playback_speed": 10.0}
        tmp_config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_config_file, "w") as f:
            json.dump(data, f)

        with patch("lumen.core.config.paths.config_path", return_value=tmp_config_file):
            cfg = load_config()

        assert cfg.playback_speed == 3.0


class TestSaveConfig:
    def test_save_and_load_roundtrip(self, tmp_config_file: Path) -> None:
        cfg = Config(volume=60, playback_speed=1.5, window_width=900)
        tmp_config_file.parent.mkdir(parents=True, exist_ok=True)

        with patch("lumen.core.config.paths.config_path", return_value=tmp_config_file):
            save_config(cfg)
            loaded = load_config()

        assert loaded.volume == 60
        assert loaded.playback_speed == 1.5
        assert loaded.window_width == 900

    def test_save_config_volume_preserved(self, tmp_config_file: Path) -> None:
        cfg = Config(volume=45)
        tmp_config_file.parent.mkdir(parents=True, exist_ok=True)

        with patch("lumen.core.config.paths.config_path", return_value=tmp_config_file):
            save_config(cfg)
            loaded = load_config()

        assert loaded.volume == 45

    def test_save_config_clamps_on_load(self, tmp_config_file: Path) -> None:
        """Even if someone manually edits the JSON to have invalid volume, load clamps it."""
        import json

        cfg = Config(volume=80)
        tmp_config_file.parent.mkdir(parents=True, exist_ok=True)

        with patch("lumen.core.config.paths.config_path", return_value=tmp_config_file):
            save_config(cfg)
            # Manually corrupt the file to have volume > 100
            with open(tmp_config_file, "w") as f:
                data = {"volume": 999}
                json.dump(data, f)
            loaded = load_config()

        assert loaded.volume == 100

    def test_save_config_overwrites_previous(self, tmp_config_file: Path) -> None:
        cfg1 = Config(volume=30)
        cfg2 = Config(volume=75)
        tmp_config_file.parent.mkdir(parents=True, exist_ok=True)

        with patch("lumen.core.config.paths.config_path", return_value=tmp_config_file):
            save_config(cfg1)
            save_config(cfg2)
            loaded = load_config()

        assert loaded.volume == 75


def _different_from(value: object, kind: object = "") -> object:
    """Sinh một giá trị KHÁC mặc định, hợp lệ, cho từng kiểu trường."""
    if isinstance(value, dict):
        # Bảng phím tắt (str) và ô track (int) — vòng 2 R-1.
        return {"t1": 3} if "int" in str(kind) else {"t1": "SUPER + ALT + 1"}
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 7
    if isinstance(value, float):
        return value + 0.25
    if isinstance(value, list):
        return ["/mot-anh.png", "/hai-anh.png"]
    return "khac-di"


def test_every_field_survives_a_save_and_load(tmp_path, monkeypatch) -> None:
    """Thêm trường mới mà quên đọc lại là nó chỉ sống tới lúc thoát app.

    Đã xảy ra thật: màu tự chọn và ảnh nền được ghi xuống đĩa nhưng `load_config`
    không đọc, nên thoát hẳn rồi mở lại là mất sạch. Test này đi qua MỌI trường
    của Config nên trường thêm sau này cũng được canh.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    changed = Config(**{f.name: _different_from(getattr(Config(), f.name), f.type) for f in fields(Config)})

    save_config(changed)

    assert load_config() == changed


def test_windows_starts_with_lumens_own_colours(tmp_path, monkeypatch) -> None:
    """Máy Windows không có Noctalia — mặc định "theo hình nền máy" sẽ ra màu dự phòng."""
    monkeypatch.setattr(paths, "on_windows", lambda: True)
    monkeypatch.setenv("APPDATA", str(tmp_path))

    assert load_config().theme_follow_noctalia is False


def test_the_windows_default_applies_on_the_very_first_run(tmp_path, monkeypatch) -> None:
    """Chưa có file cấu hình thì hàm nạp thoát sớm — mặc định theo hệ vẫn phải áp."""
    monkeypatch.setattr(paths, "on_windows", lambda: True)
    monkeypatch.setenv("APPDATA", str(tmp_path / "khong-ton-tai"))

    assert not paths.config_path().exists()
    assert load_config().theme_follow_noctalia is False


def test_a_windows_user_who_chose_to_follow_is_respected(tmp_path, monkeypatch) -> None:
    """Chỉ đổi mặc định khi người dùng CHƯA từng chọn."""
    monkeypatch.setattr(paths, "on_windows", lambda: True)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    folder = tmp_path / "Lumen"
    folder.mkdir()
    (folder / "config.json").write_text('{"theme_follow_noctalia": true}', encoding="utf-8")

    assert load_config().theme_follow_noctalia is True


def test_linux_still_follows_by_default(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(paths, "on_windows", lambda: False)

    assert load_config().theme_follow_noctalia is True
