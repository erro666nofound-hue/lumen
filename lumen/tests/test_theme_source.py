"""Tests for the pure-Python Noctalia palette reader.

theme_source.load_palette() must never raise and must always return all 17
Lumen tokens, no matter how broken the underlying JSON file is -- the app
always needs a color to paint with.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from lumen.core import theme_source
from lumen.core.theme_source import FALLBACK, TOKENS, is_valid_color, load_palette, normalize_color

SAMPLE_JSON = """{
  "mPrimary": "#ffb3af", "mOnPrimary": "#5c181a",
  "mSecondary": "#f0b9b6", "mOnSecondary": "#4a2725",
  "mTertiary": "#fabb5c", "mOnTertiary": "#452b00",
  "mError": "#ffb4ab", "mOnError": "#690005",
  "mSurface": "#191111", "mOnSurface": "#efdfdd",
  "mSurfaceVariant": "#261e1d", "mOnSurfaceVariant": "#dac1bf",
  "mOutline": "#544241", "mShadow": "#000000",
  "mHover": "#fabb5c", "mOnHover": "#452b00"
}"""

EXPECTED_FROM_SAMPLE: dict[str, str] = {
    "background": "#191111",
    "surface": "#191111",
    "surfaceVariant": "#261e1d",
    "primary": "#ffb3af",
    "onPrimary": "#5c181a",
    "secondary": "#f0b9b6",
    "onSecondary": "#4a2725",
    "tertiary": "#fabb5c",
    "onTertiary": "#452b00",
    "error": "#ffb4ab",
    "onError": "#690005",
    "onSurface": "#efdfdd",
    "onSurfaceVariant": "#dac1bf",
    "outline": "#544241",
    "shadow": "#000000",
    "hover": "#fabb5c",
    "onHover": "#452b00",
}


def _write(tmp_path: Path, text: str, name: str = "colors.json") -> Path:
    target = tmp_path / name
    target.write_text(text, encoding="utf-8")
    return target


# --- module-level invariants ------------------------------------------------


def test_fallback_covers_exactly_the_token_set() -> None:
    assert set(FALLBACK) == set(TOKENS)


def test_tokens_and_fallback_are_complete() -> None:
    assert len(TOKENS) == 17
    assert len(FALLBACK) == 17


# --- load_palette: happy path ------------------------------------------------


def test_load_palette_reads_real_sample(tmp_path: Path) -> None:
    path = _write(tmp_path, SAMPLE_JSON)
    palette = load_palette(path)
    assert palette == EXPECTED_FROM_SAMPLE


def test_background_mirrors_surface(tmp_path: Path) -> None:
    path = _write(tmp_path, SAMPLE_JSON)
    palette = load_palette(path)
    assert palette["background"] == palette["surface"]


def test_result_always_has_all_17_tokens(tmp_path: Path) -> None:
    path = _write(tmp_path, SAMPLE_JSON)
    assert set(load_palette(path)) == set(TOKENS)


# --- load_palette: file-level failures fall back entirely -------------------


def test_missing_file_returns_fallback(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.json"
    assert load_palette(missing) == FALLBACK


def test_missing_file_does_not_raise(tmp_path: Path) -> None:
    missing = tmp_path / "nope" / "colors.json"  # parent dir also absent
    load_palette(missing)  # must not raise


def test_broken_json_returns_fallback(tmp_path: Path) -> None:
    path = _write(tmp_path, "{ not valid json at all")
    assert load_palette(path) == FALLBACK


def test_json_array_returns_fallback(tmp_path: Path) -> None:
    path = _write(tmp_path, json.dumps(["not", "an", "object"]))
    assert load_palette(path) == FALLBACK


def test_json_scalar_returns_fallback(tmp_path: Path) -> None:
    path = _write(tmp_path, json.dumps("just a string"))
    assert load_palette(path) == FALLBACK


def test_empty_file_returns_fallback(tmp_path: Path) -> None:
    path = _write(tmp_path, "")
    assert load_palette(path) == FALLBACK


def test_file_failure_logs_warning(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    missing = tmp_path / "does-not-exist.json"
    with caplog.at_level(logging.WARNING, logger="lumen.core.theme_source"):
        load_palette(missing)
    assert any(record.levelno == logging.WARNING for record in caplog.records)


# --- load_palette: partial data -> per-token fallback ------------------------


def test_missing_keys_fall_back_only_for_those_tokens(tmp_path: Path) -> None:
    partial = {"mPrimary": "#ffb3af", "mOnPrimary": "#5c181a"}
    path = _write(tmp_path, json.dumps(partial))
    palette = load_palette(path)

    assert palette["primary"] == "#ffb3af"
    assert palette["onPrimary"] == "#5c181a"
    # everything else came from FALLBACK
    for token in TOKENS:
        if token in ("primary", "onPrimary"):
            continue
        assert palette[token] == FALLBACK[token]


def test_missing_keys_log_warning_naming_the_token(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    partial = {"mPrimary": "#ffb3af"}
    path = _write(tmp_path, json.dumps(partial))
    with caplog.at_level(logging.WARNING, logger="lumen.core.theme_source"):
        load_palette(path)
    warnings = "\n".join(r.getMessage() for r in caplog.records)
    assert "surface" in warnings


@pytest.mark.parametrize("bad_value", ["red", 123, None, "#xyz", "", [1, 2, 3], {}])
def test_garbage_color_value_falls_back_for_that_token_only(tmp_path: Path, bad_value: object) -> None:
    data = {"mPrimary": bad_value, "mSurface": "#123456"}
    path = _write(tmp_path, json.dumps(data))
    palette = load_palette(path)

    assert palette["primary"] == FALLBACK["primary"]
    assert palette["surface"] == "#123456"


def test_shorthand_hex_in_file_is_expanded(tmp_path: Path) -> None:
    data = {"mSurface": "#abc"}
    path = _write(tmp_path, json.dumps(data))
    palette = load_palette(path)
    assert palette["surface"] == "#aabbcc"


def test_default_path_used_when_none_given(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """path=None must resolve via paths.noctalia_colors_path(), not a hardcoded string."""
    fake_path = tmp_path / "colors.json"
    fake_path.write_text(SAMPLE_JSON, encoding="utf-8")
    monkeypatch.setattr(theme_source.paths, "noctalia_colors_path", lambda: fake_path)
    assert load_palette(None) == EXPECTED_FROM_SAMPLE
    assert load_palette() == EXPECTED_FROM_SAMPLE


# --- is_valid_color -----------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    ["#fff", "#FFF", "#ffffff", "#FFFFFF", "#ffffffff", "#AAbbCCdd", "#123", "#12345678"],
)
def test_is_valid_color_accepts_hex_forms(value: str) -> None:
    assert is_valid_color(value) is True


@pytest.mark.parametrize(
    "value",
    ["red", "", "#", "#xyz", "#12", "#12345", "#1234567", "123456", 123, None, 1.5, [], {}, True],
)
def test_is_valid_color_rejects_everything_else(value: object) -> None:
    assert is_valid_color(value) is False


# --- normalize_color -----------------------------------------------------------


def test_normalize_color_expands_shorthand() -> None:
    assert normalize_color("#abc") == "#aabbcc"


def test_normalize_color_lowercases() -> None:
    assert normalize_color("#FF00AA") == "#ff00aa"
    assert normalize_color("#ABC") == "#aabbcc"


def test_normalize_color_leaves_full_form_untouched_besides_case() -> None:
    assert normalize_color("#aabbcc") == "#aabbcc"
    assert normalize_color("#aabbccdd") == "#aabbccdd"


def test_load_palette_result_reports_success(tmp_path) -> None:
    """A readable, well-formed file reports ok=True."""
    from lumen.core.theme_source import load_palette_result

    target = tmp_path / "colors.json"
    target.write_text(json.dumps({"mPrimary": "#112233", "mSurface": "#000000"}), encoding="utf-8")
    result = load_palette_result(target)
    assert result.ok is True
    assert result.colors["primary"] == "#112233"
    assert "onSurface" in result.missing_tokens


def test_load_palette_result_reports_failure(tmp_path) -> None:
    """Missing file and broken JSON both report ok=False with a full fallback table."""
    from lumen.core.theme_source import FALLBACK, load_palette_result

    missing = load_palette_result(tmp_path / "nope.json")
    assert missing.ok is False
    assert missing.colors == FALLBACK

    broken = tmp_path / "broken.json"
    broken.write_text('{"mPrimary": ', encoding="utf-8")
    assert load_palette_result(broken).ok is False


def test_dynsle_palette_is_preferred_and_translated(tmp_path, monkeypatch) -> None:
    """dynsle's matugen file wins over Noctalia, and its surface carries 12% accent."""
    import json

    from lumen.core import paths

    f = tmp_path / "dyn" / "colors.json"
    f.parent.mkdir()
    f.write_text(json.dumps({"background": "#131314", "on_background": "#e4e2e2", "primary": "#b5cad5",
                             "outline": "#8d9195", "surface_container_high": "#292a2b"}))
    monkeypatch.setattr(paths, "dynsle_colors_path", lambda: f)
    result = theme_source.load_palette_result()
    assert result.ok
    assert result.colors["background"] == "#131314"
    assert result.colors["onSurface"] == "#e4e2e2"
    assert result.colors["surface"] == "#26292b"
    assert "error" in result.missing_tokens


def test_no_dynsle_file_falls_back_to_noctalia(tmp_path, monkeypatch) -> None:
    """Without dynsle, the Noctalia path is the one followed."""
    from lumen.core import paths

    noct = tmp_path / "noct.json"
    monkeypatch.setattr(paths, "noctalia_colors_path", lambda: noct)
    assert paths.desktop_colors_path() == noct
