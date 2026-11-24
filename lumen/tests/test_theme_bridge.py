"""Live-reload tests for ThemeBridge.

This is the one piece of Lumen that fails *silently* when it breaks: the app
keeps running, it just stops following Noctalia, and nobody notices for weeks.
The atomic-replace test below is the important one -- palette generators write
a temp file and rename it over the original, which retires the inode and makes
QFileSystemWatcher quietly drop the path unless it is re-added.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from lumen.bridge.theme_bridge import ThemeBridge
from lumen.core import palettes  # noqa: E402
from lumen.core import paths  # noqa: E402
from lumen.core.theme_source import FALLBACK  # noqa: E402

PALETTE_A = {"mPrimary": "#ffb3af", "mSurface": "#191111", "mOnSurface": "#efdfdd"}
PALETTE_B = {"mPrimary": "#8fd3ff", "mSurface": "#0d1520", "mOnSurface": "#dde8f5"}


@pytest.fixture(scope="module")
def qapp() -> QGuiApplication:
    """One QGuiApplication for the whole module (Qt allows only a single instance)."""
    return QGuiApplication.instance() or QGuiApplication([])


@pytest.fixture
def palette_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the whole app at a scratch palette file we control."""
    target = tmp_path / "noctalia" / "colors.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(PALETTE_A), encoding="utf-8")
    monkeypatch.setattr(paths, "noctalia_colors_path", lambda: target)
    return target


def _wait_for_change(bridge: ThemeBridge, timeout_ms: int = 4000) -> bool:
    """Spin a real event loop until the bridge reports a palette change."""
    loop = QEventLoop()
    fired: list[bool] = []

    def on_changed() -> None:
        fired.append(True)
        loop.quit()

    bridge.changed.connect(on_changed)
    guard = QTimer()
    guard.setSingleShot(True)
    guard.timeout.connect(loop.quit)
    guard.start(timeout_ms)
    loop.exec()
    guard.stop()
    bridge.changed.disconnect(on_changed)
    return bool(fired)


def _write_atomically(target: Path, payload: dict[str, str]) -> None:
    """Write like a real palette generator does: temp file, then rename over."""
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(tmp, target)


def test_initial_palette_comes_from_file(qapp, palette_file: Path) -> None:
    bridge = ThemeBridge(follow_noctalia=True)
    try:
        assert bridge.primary == "#ffb3af"
        assert bridge.background == "#191111"  # derived from surface
    finally:
        bridge.stop_watching()


def test_reloads_on_plain_overwrite(qapp, palette_file: Path) -> None:
    bridge = ThemeBridge(follow_noctalia=True)
    try:
        palette_file.write_text(json.dumps(PALETTE_B), encoding="utf-8")
        assert _wait_for_change(bridge), "changed signal never fired on plain write"
        assert bridge.primary == "#8fd3ff"
    finally:
        bridge.stop_watching()


def test_reloads_on_atomic_replace(qapp, palette_file: Path) -> None:
    """The trap: rename-over-original retires the inode the watcher held."""
    bridge = ThemeBridge(follow_noctalia=True)
    try:
        _write_atomically(palette_file, PALETTE_B)
        assert _wait_for_change(bridge), "changed signal never fired on atomic replace"
        assert bridge.primary == "#8fd3ff"
    finally:
        bridge.stop_watching()


def test_survives_repeated_atomic_replaces(qapp, palette_file: Path) -> None:
    """Live reload must keep working after the first rename, not just once."""
    bridge = ThemeBridge(follow_noctalia=True)
    try:
        for _ in range(3):
            _write_atomically(palette_file, PALETTE_B)
            assert _wait_for_change(bridge)
            assert bridge.primary == "#8fd3ff"
            _write_atomically(palette_file, PALETTE_A)
            assert _wait_for_change(bridge)
            assert bridge.primary == "#ffb3af"
    finally:
        bridge.stop_watching()


def test_follow_disabled_uses_lumens_own_colour_and_no_watcher(qapp, palette_file: Path) -> None:
    """Tắt "theo wallpaper" nghĩa là dùng màu người dùng chọn, KHÔNG phải bảng dự phòng."""
    bridge = ThemeBridge(follow_noctalia=False)
    try:
        assert bridge.primary == palettes.DEFAULT_ACCENT
        assert bridge._watcher is None
    finally:
        bridge.stop_watching()


def test_a_chosen_colour_paints_the_whole_app(qapp, palette_file: Path) -> None:
    bridge = ThemeBridge(follow_noctalia=False, accent=palettes.PRESETS["Cam"])
    try:
        assert bridge.primary == palettes.PRESETS["Cam"]
        # Nền cũng phải ám theo, không phải chỉ đổi mỗi màu nhấn.
        assert bridge.background != FALLBACK["background"]
    finally:
        bridge.stop_watching()


def test_switching_source_swaps_the_palette(qapp, palette_file: Path) -> None:
    bridge = ThemeBridge(follow_noctalia=True)
    try:
        from_noctalia = bridge.primary

        bridge.setFollowNoctalia(False)
        bridge.setAccent(palettes.PRESETS["Xanh dương"])

        assert bridge.primary == palettes.PRESETS["Xanh dương"]

        bridge.setFollowNoctalia(True)

        assert bridge.primary == from_noctalia
    finally:
        bridge.stop_watching()


def test_choices_are_written_down_immediately(qapp, palette_file: Path) -> None:
    """Người dùng có thể tắt máy ngay sau khi chọn — không được đợi lúc thoát mới ghi."""
    saved: list[tuple] = []
    bridge = ThemeBridge(
        follow_noctalia=False,
        on_changed=lambda b: saved.append((b.followNoctalia, b.accent, b.wallpaper)),
    )
    try:
        bridge.setAccent(palettes.PRESETS["Hồng"])
        bridge.setWallpaper("/home/ai/anh.png")

        assert saved[-1] == (False, palettes.PRESETS["Hồng"], "/home/ai/anh.png")
    finally:
        bridge.stop_watching()


def test_a_wallpaper_url_is_stored_as_a_plain_path(qapp, palette_file: Path) -> None:
    """Hộp chọn file trả về file:// — lưu nguyên thì mọi chỗ đọc file đều hỏng."""
    bridge = ThemeBridge(follow_noctalia=False)
    try:
        bridge.setWallpaper("file:///home/ai/anh.png")

        assert bridge.wallpaper == "/home/ai/anh.png"
    finally:
        bridge.stop_watching()


def test_rubbish_colour_is_ignored(qapp, palette_file: Path) -> None:
    bridge = ThemeBridge(follow_noctalia=False, accent=palettes.PRESETS["Cam"])
    try:
        bridge.setAccent("không phải màu")

        assert bridge.accent == palettes.PRESETS["Cam"]
    finally:
        bridge.stop_watching()


def test_stop_watching_is_idempotent(qapp, palette_file: Path) -> None:
    bridge = ThemeBridge(follow_noctalia=True)
    bridge.stop_watching()
    bridge.stop_watching()


def test_valid_palette_equal_to_fallback_is_still_applied(qapp, palette_file: Path) -> None:
    """Regression: a real palette that happens to equal FALLBACK is not a failed read.

    The first implementation detected mid-write reads by comparing the result
    to FALLBACK. Because FALLBACK *is* the user's own Noctalia palette,
    switching color schemes away and back made the app silently refuse the
    change and freeze on the old colors.
    """
    palette_file.write_text(json.dumps(PALETTE_B), encoding="utf-8")
    bridge = ThemeBridge(follow_noctalia=True)
    try:
        assert bridge.primary == "#8fd3ff"
        fallback_shaped = {
            "mPrimary": FALLBACK["primary"],
            "mSurface": FALLBACK["surface"],
            "mOnSurface": FALLBACK["onSurface"],
        }
        _write_atomically(palette_file, fallback_shaped)
        assert _wait_for_change(bridge), "palette identical to FALLBACK was wrongly rejected"
        assert bridge.primary == FALLBACK["primary"]
    finally:
        bridge.stop_watching()
