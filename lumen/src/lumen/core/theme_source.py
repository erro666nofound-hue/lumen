"""Pure-Python reader for the Noctalia color palette.

Reads ``~/.config/noctalia/colors.json`` and translates its ``mXxx`` keys into
Lumen's own token names. No Qt, no file watching -- ``bridge/theme_bridge.py``
owns polling/watching the file and re-calling :func:`load_palette` on change.

This module must stay resilient against any garbage a human or a broken
Noctalia install could put in that file: missing file, invalid JSON, wrong
JSON shape, missing keys, or keys holding non-color values. The app must
always end up with a complete, paintable palette.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
import logging
import re
from pathlib import Path

from . import paths

log = logging.getLogger(__name__)

TOKENS: tuple[str, ...] = (
    "background",
    "surface",
    "surfaceVariant",
    "primary",
    "onPrimary",
    "secondary",
    "onSecondary",
    "tertiary",
    "onTertiary",
    "error",
    "onError",
    "onSurface",
    "onSurfaceVariant",
    "outline",
    "shadow",
    "hover",
    "onHover",
)

FALLBACK: dict[str, str] = {
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

# #rgb, #rrggbb, #aarrggbb or #rrggbbaa -- length alone tells them apart, we
# don't need to know which of the two 8-digit orderings a value uses to know
# it is a color.
_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def is_valid_color(value: object) -> bool:
    """Return True if value is a hex color string (#rgb/#rrggbb/#aarrggbb/#rrggbbaa)."""
    if not isinstance(value, str):
        return False
    return bool(_COLOR_RE.match(value))


def normalize_color(value: str) -> str:
    """Lowercase a hex color and expand shorthand #rgb into #rrggbb."""
    lowered = value.lower()
    if len(lowered) == 4:  # "#rgb"
        _, r, g, b = lowered
        return f"#{r}{r}{g}{g}{b}{b}"
    return lowered


def _noctalia_key(token: str) -> str:
    """Map a Lumen token name to the Noctalia JSON key that feeds it (mPrimary, ...)."""
    return "m" + token[0].upper() + token[1:]


#: Lumen token → matugen key (dynsle). Noctalia's "hover" has no matugen twin;
#: dynsle's second colour is tertiary, so hover follows it.
_MATUGEN_KEYS: dict[str, str] = {
    "background": "background", "surface": "background", "surfaceVariant": "surface_container_high",
    "primary": "primary", "onPrimary": "on_primary", "secondary": "secondary",
    "onSecondary": "on_secondary", "tertiary": "tertiary", "onTertiary": "on_tertiary",
    "error": "error", "onError": "on_error", "onSurface": "on_background",
    "onSurfaceVariant": "on_surface_variant", "outline": "outline", "shadow": "shadow",
    "hover": "tertiary", "onHover": "on_tertiary",
}

#: dynsle tints its island with 12% of the accent (Theme.qml islandTint).
_ISLAND_TINT = 0.12


def _mix(base: str, other: str, amount: float) -> str:
    """Blend two #rrggbb colours, `amount` of `other` into `base`."""
    a, b = normalize_color(base)[1:7], normalize_color(other)[1:7]
    if len(a) != 6 or len(b) != 6:
        return normalize_color(base)
    out = (round(int(a[i:i + 2], 16) * (1 - amount) + int(b[i:i + 2], 16) * amount) for i in (0, 2, 4))
    return "#" + "".join(f"{v:02x}" for v in out)


def _from_matugen(data: dict) -> tuple[dict[str, str], list[str]]:
    """Translate dynsle's matugen palette into Lumen tokens, plus the missing ones."""
    palette: dict[str, str] = {}
    missing: list[str] = []
    for token in TOKENS:
        value = data.get(_MATUGEN_KEYS[token])
        if is_valid_color(value):
            palette[token] = normalize_color(value)  # type: ignore[arg-type]
        else:
            palette[token] = FALLBACK[token]
            missing.append(token)
    palette["surface"] = _mix(palette["surface"], palette["primary"], _ISLAND_TINT)
    return palette, missing


@dataclass(frozen=True, slots=True)
class PaletteResult:
    """A palette plus whether the underlying file could actually be read.

    Callers must not infer "the read failed" by comparing the palette to
    FALLBACK: a perfectly valid Noctalia file can legitimately produce exactly
    the fallback values (it is where those values came from), and treating that
    as a failure makes the app refuse a real theme change.
    """

    colors: dict[str, str]
    ok: bool
    missing_tokens: tuple[str, ...] = ()


def load_palette_result(path: Path | None = None) -> PaletteResult:
    """Read the Noctalia palette, reporting whether the file itself was usable."""
    source = path if path is not None else paths.desktop_colors_path()

    try:
        raw = source.read_text(encoding="utf-8")
    except OSError as exc:
        log.warning("Cannot read Noctalia palette at %s (%s) -- using fallback colors", source, exc)
        return PaletteResult(dict(FALLBACK), ok=False)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.warning("Invalid JSON in Noctalia palette at %s (%s) -- using fallback colors", source, exc)
        return PaletteResult(dict(FALLBACK), ok=False)

    if not isinstance(data, dict):
        log.warning("Noctalia palette at %s is not a JSON object -- using fallback colors", source)
        return PaletteResult(dict(FALLBACK), ok=False)

    if "on_background" in data and "mPrimary" not in data:
        palette, missing = _from_matugen(data)
        if missing:
            log.warning("dynsle palette at %s missing/invalid tokens %s -- using fallback for them", source, missing)
        return PaletteResult(palette, ok=True, missing_tokens=tuple(missing))

    palette: dict[str, str] = {}
    missing: list[str] = []
    for token in TOKENS:
        if token == "background":
            continue  # resolved from surface below, has no Noctalia key of its own
        value = data.get(_noctalia_key(token))
        if is_valid_color(value):
            palette[token] = normalize_color(value)  # type: ignore[arg-type]
        else:
            palette[token] = FALLBACK[token]
            missing.append(token)

    palette["background"] = palette["surface"]

    if missing:
        log.warning("Noctalia palette at %s missing/invalid tokens %s -- using fallback for them", source, missing)

    return PaletteResult(palette, ok=True, missing_tokens=tuple(missing))


def load_palette(path: Path | None = None) -> dict[str, str]:
    """Read the Noctalia palette, always returning a complete token table."""
    return load_palette_result(path).colors
