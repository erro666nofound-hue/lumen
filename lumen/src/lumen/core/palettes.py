"""Dựng một bảng màu ĐẦY ĐỦ từ đúng MỘT màu người dùng chọn.

Người dùng chỉ muốn nói "cho tôi màu cam". Từ một màu đó phải ra đủ 17 token mà
giao diện cần, và ra bộ nào cũng phải đọc được — chữ không được chìm vào nền.

Thuần Python (`colorsys` của thư viện chuẩn), không Qt, không đọc file: chạy
được bằng pytest mà không mở cửa sổ nào.
"""

from __future__ import annotations

import colorsys

from lumen.core.theme_source import FALLBACK, TOKENS, is_valid_color, normalize_color

#: Các màu dựng sẵn. Tên hiện thẳng lên giao diện nên viết bằng tiếng Việt.
PRESETS: dict[str, str] = {
    "Cam": "#ff8a4c",
    "Đỏ": "#ff5f5f",
    "Vàng": "#ffc94a",
    "Xanh lá": "#4fd68a",
    "Xanh dương": "#5aa8ff",
    "Tím": "#b98cff",
    "Hồng": "#ff8fc7",
    "Trắng": "#e6e6ee",
}

#: Độ sáng của các sắc độ một màu, tối tới sáng (R-1 vòng 3: bấm một màu thì
#: hiện nhiều sắc độ của màu đó). Đầu tối dừng ở 0.36: tối hơn nữa thì nút
#: màu chủ đạo chìm vào nền app vốn đã tối.
SHADE_LIGHTNESS: tuple[float, ...] = (0.36, 0.45, 0.54, 0.63, 0.72, 0.81, 0.9)

#: Màu mặc định khi người dùng bật chế độ tự chỉnh mà chưa chọn gì.
DEFAULT_ACCENT = PRESETS["Tím"]

#: Ngưỡng ĐỘ CHÓI để quyết định chữ trên màu đó là đen hay trắng.
#:
#: Phải dùng độ chói (mắt nhạy với xanh lá gấp ~3 lần đỏ, gấp ~10 lần lam), KHÔNG
#: dùng "lightness" của HLS. Đo được: #4fd68a có lightness 0.57 nên HLS bảo "tối,
#: dùng chữ trắng", trong khi độ chói là 0.70 — chữ trắng trên đó gần như không
#: đọc nổi.
_LIGHT_TEXT_BELOW = 0.45

_INK_ON_LIGHT = "#141018"
_INK_ON_DARK = "#ffffff"


def _to_hls(value: str) -> tuple[float, float, float]:
    raw = normalize_color(value).lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    red, green, blue = (int(raw[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hls(red, green, blue)


def _from_hls(hue: float, lightness: float, saturation: float) -> str:
    red, green, blue = colorsys.hls_to_rgb(hue % 1.0, _clamp(lightness), _clamp(saturation))
    return "#{:02x}{:02x}{:02x}".format(
        round(red * 255), round(green * 255), round(blue * 255)
    )


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def shades(color: str) -> list[str]:
    """Return shades of one colour, dark to light; the colour itself replaces its nearest step."""
    if not is_valid_color(color):
        return []
    hue, lightness, saturation = _to_hls(color)
    steps = [_from_hls(hue, step, saturation) for step in SHADE_LIGHTNESS]
    nearest = min(range(len(SHADE_LIGHTNESS)), key=lambda i: abs(SHADE_LIGHTNESS[i] - lightness))
    steps[nearest] = normalize_color(color)
    return steps


def luminance(value: str) -> float:
    """Return how bright a colour looks to the eye, 0 (black) to 1 (white)."""
    raw = normalize_color(value).lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    red, green, blue = (int(raw[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def ink_for(background: str) -> str:
    """Return the text colour that stays readable on this background."""
    return _INK_ON_DARK if luminance(background) < _LIGHT_TEXT_BELOW else _INK_ON_LIGHT


def palette_from_accent(accent: str) -> dict[str, str]:
    """Build every token Lumen paints with, from one accent colour.

    Nền lấy CHÍNH sắc của màu chủ đạo nhưng gần như không bão hoà: cả app ám
    nhẹ theo màu đã chọn thay vì một màu nhấn lạc lõng trên nền xám.
    """
    if not is_valid_color(accent):
        accent = DEFAULT_ACCENT
    hue, lightness, saturation = _to_hls(accent)
    # Màu quá nhợt (ví dụ trắng) thì không còn sắc để ám nền theo.
    tint = min(saturation, 0.22)

    primary = normalize_color(accent)
    palette = {
        "background": _from_hls(hue, 0.07, tint * 0.5),
        "surface": _from_hls(hue, 0.09, tint * 0.5),
        "surfaceVariant": _from_hls(hue, 0.14, tint * 0.6),
        "primary": primary,
        "onPrimary": ink_for(primary),
        "secondary": _from_hls(hue - 0.055, min(lightness + 0.05, 0.82), max(saturation * 0.7, 0.2)),
        "tertiary": _from_hls(hue + 0.075, min(lightness + 0.05, 0.82), max(saturation * 0.8, 0.25)),
        "error": "#ff6b6b",
        "onSurface": _from_hls(hue, 0.93, tint * 0.35),
        "onSurfaceVariant": _from_hls(hue, 0.76, tint * 0.35),
        "outline": _from_hls(hue, 0.34, tint * 0.6),
        "shadow": "#000000",
        "hover": primary,
    }
    palette["onSecondary"] = ink_for(palette["secondary"])
    palette["onTertiary"] = ink_for(palette["tertiary"])
    palette["onError"] = ink_for(palette["error"])
    palette["onHover"] = ink_for(palette["hover"])
    # Chốt chặn: thiếu token nào thì lấy màu dự phòng, giao diện không bao giờ
    # được nhận một bảng màu khuyết.
    return {token: palette.get(token, FALLBACK[token]) for token in TOKENS}
