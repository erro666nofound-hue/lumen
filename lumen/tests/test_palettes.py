"""Dựng bảng màu từ một màu chủ đạo: phải luôn ĐỦ và luôn ĐỌC ĐƯỢC."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lumen.core import palettes  # noqa: E402
from lumen.core.theme_source import TOKENS, is_valid_color  # noqa: E402


def _luminance(value: str) -> float:
    raw = value.lstrip("#")
    red, green, blue = (int(raw[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


class TestEveryPaletteIsComplete:
    @pytest.mark.parametrize("name", sorted(palettes.PRESETS))
    def test_preset_fills_every_token(self, name: str) -> None:
        made = palettes.palette_from_accent(palettes.PRESETS[name])

        assert set(made) == set(TOKENS)

    @pytest.mark.parametrize("name", sorted(palettes.PRESETS))
    def test_every_value_is_a_real_colour(self, name: str) -> None:
        made = palettes.palette_from_accent(palettes.PRESETS[name])

        assert all(is_valid_color(value) for value in made.values())

    def test_rubbish_falls_back_instead_of_crashing(self) -> None:
        made = palettes.palette_from_accent("không phải màu")

        assert set(made) == set(TOKENS)
        assert made["primary"] == palettes.DEFAULT_ACCENT


class TestTextStaysReadable:
    """Chữ chìm vào nền là lỗi không ai báo cáo được — phải chặn bằng test."""

    @pytest.mark.parametrize("name", sorted(palettes.PRESETS))
    def test_text_contrasts_with_the_surface(self, name: str) -> None:
        made = palettes.palette_from_accent(palettes.PRESETS[name])

        gap = abs(_luminance(made["onSurface"]) - _luminance(made["surface"]))
        assert gap > 0.5, f"{name}: chữ và nền quá gần nhau ({gap:.2f})"

    @pytest.mark.parametrize("name", sorted(palettes.PRESETS))
    def test_text_on_the_accent_contrasts_too(self, name: str) -> None:
        made = palettes.palette_from_accent(palettes.PRESETS[name])

        gap = abs(_luminance(made["onPrimary"]) - _luminance(made["primary"]))
        assert gap > 0.35, f"{name}: chữ trên màu nhấn quá gần nhau ({gap:.2f})"

    def test_a_pale_accent_gets_dark_ink(self) -> None:
        assert palettes.ink_for("#ffffff") == "#141018"

    def test_a_dark_accent_gets_light_ink(self) -> None:
        assert palettes.ink_for("#101010") == "#ffffff"


class TestTheWholeAppTakesTheHue:
    def test_the_background_follows_the_chosen_colour(self) -> None:
        """Nền phải ám theo màu đã chọn, không phải một màu nhấn lạc trên nền xám."""
        warm = palettes.palette_from_accent(palettes.PRESETS["Cam"])
        cool = palettes.palette_from_accent(palettes.PRESETS["Xanh dương"])

        assert warm["background"] != cool["background"]

    def test_the_accent_is_kept_exactly(self) -> None:
        made = palettes.palette_from_accent("#ff8a4c")

        assert made["primary"] == "#ff8a4c"

    def test_a_colourless_accent_still_works(self) -> None:
        """Trắng không còn sắc để ám nền — không được chia cho 0 hay ra màu lạ."""
        made = palettes.palette_from_accent(palettes.PRESETS["Trắng"])

        assert set(made) == set(TOKENS)
        assert all(is_valid_color(value) for value in made.values())


@pytest.mark.parametrize("preset", list(palettes.PRESETS.values()))
def test_shades_run_dark_to_light_and_keep_the_preset(preset: str) -> None:
    shades = palettes.shades(preset)
    assert len(shades) == len(palettes.SHADE_LIGHTNESS)
    assert preset in shades
    assert all(is_valid_color(s) for s in shades)
    assert len(set(shades)) == len(shades)
    lightness = [palettes._to_hls(s)[1] for s in shades]
    assert lightness == sorted(lightness)


def test_shades_of_garbage_is_empty() -> None:
    assert palettes.shades("not a colour") == []
