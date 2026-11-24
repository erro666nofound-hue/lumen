"""Tests for the glass / bounce / speed choices (design R-1)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from lumen.core import look  # noqa: E402


def test_unknown_choice_falls_back_to_default() -> None:
    assert look.clean("glass", "nonsense") == look.DEFAULT_GLASS
    assert look.clean("bounce", "nhieu") == "nhieu"


def test_numbers_match_dynsle() -> None:
    assert look.number("glass", "kinh") == 0.74
    assert look.number("bounce", "khong") == 0.0
    assert look.number("speed", "cham") == 1.6


def test_theme_feel_changes_alpha_and_is_remembered() -> None:
    from PySide6.QtGui import QGuiApplication

    from lumen.bridge.theme_bridge import ThemeBridge

    QGuiApplication.instance() or QGuiApplication([])
    seen = []
    theme = ThemeBridge(follow_noctalia=False, on_changed=lambda b: seen.append(b.feel()),
                        feel={"glass": "dac", "bounce": "bogus"})
    assert theme.surfaceAlpha == 0.96
    assert theme.bounce == look.DEFAULT_BOUNCE
    theme.setFeel("speed", "nhanh")
    assert theme.motionScale == 0.6
    assert seen[-1]["speed"] == "nhanh"
    theme.setFeel("speed", "bogus")
    assert theme.speed == "nhanh"
