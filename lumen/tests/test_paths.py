"""Path resolution tests.

The user-dirs regression matters more than it looks: the original parser
matched on the bare key ("MUSIC=") while the real file stores fully qualified
keys ("XDG_MUSIC_DIR=..."). It therefore never matched and every lookup fell
through to the fallback -- which on a default machine is the *same* directory,
so the bug was completely invisible until someone relocated their Music folder.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lumen.core import paths


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point HOME at a scratch directory and clear every XDG override."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for var in (
        "XDG_DATA_HOME",
        "XDG_CONFIG_HOME",
        "XDG_STATE_HOME",
        "XDG_CACHE_HOME",
        "XDG_MUSIC_DIR",
    ):
        monkeypatch.delenv(var, raising=False)
    return tmp_path


def _write_user_dirs(home: Path, body: str) -> None:
    config = home / ".config"
    config.mkdir(parents=True, exist_ok=True)
    (config / "user-dirs.dirs").write_text(body, encoding="utf-8")


def test_music_dir_follows_relocated_user_dirs(fake_home: Path) -> None:
    """A relocated XDG_MUSIC_DIR in user-dirs.dirs must actually be honoured."""
    _write_user_dirs(
        fake_home,
        '# comment\nXDG_DOWNLOAD_DIR="$HOME/Downloads"\nXDG_MUSIC_DIR="$HOME/Media/Songs"\n',
    )
    assert paths.music_dir() == fake_home / "Media" / "Songs" / "Lumen"


def test_music_dir_accepts_absolute_path(fake_home: Path) -> None:
    """Absolute values (not $HOME-relative) are supported by the spec too."""
    _write_user_dirs(fake_home, 'XDG_MUSIC_DIR="/mnt/media/music"\n')
    assert paths.music_dir() == Path("/mnt/media/music") / "Lumen"


def test_music_dir_env_var_wins_over_file(fake_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The environment overrides user-dirs.dirs."""
    _write_user_dirs(fake_home, 'XDG_MUSIC_DIR="$HOME/FromFile"\n')
    monkeypatch.setenv("XDG_MUSIC_DIR", str(fake_home / "FromEnv"))
    assert paths.music_dir() == fake_home / "FromEnv" / "Lumen"


def test_music_dir_falls_back_without_user_dirs(fake_home: Path) -> None:
    """No user-dirs.dirs at all -> ~/Music/Lumen."""
    assert paths.music_dir() == fake_home / "Music" / "Lumen"


def test_xdg_env_vars_are_read_at_call_time(fake_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Paths must not cache env lookups at import time."""
    assert paths.data_dir() == fake_home / ".local" / "share" / "lumen"
    monkeypatch.setenv("XDG_DATA_HOME", str(fake_home / "custom"))
    assert paths.data_dir() == fake_home / "custom" / "lumen"


def test_noctalia_colors_path_follows_config_home(fake_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The theme source path tracks XDG_CONFIG_HOME like everything else."""
    assert paths.noctalia_colors_path() == fake_home / ".config" / "noctalia" / "colors.json"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(fake_home / "cfg"))
    assert paths.noctalia_colors_path() == fake_home / "cfg" / "noctalia" / "colors.json"


def test_ui_dir_is_inside_the_package(fake_home: Path) -> None:
    """ui_dir() resolves from __file__, so it must not move when HOME changes."""
    assert paths.ui_dir().name == "ui"
    assert (paths.ui_dir() / "Main.qml").exists()
