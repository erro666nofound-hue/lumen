"""The three "feel" choices of design R-1: glass, bounce, animation speed.

Thuần Python: bảng giá trị + kiểm tra khoá. Theme bridge đọc ra số cho QML.
Số lấy từ dynsle (Prefs.qml: panelStyle solid/frosted/glass, anim off/fast/
normal/relaxed) để Lumen và đảo dynsle "cảm" giống nhau.
"""

from __future__ import annotations

#: Độ đặc của lớp kính (alpha), như mục Panels của dynsle.
GLASS: dict[str, float] = {"dac": 0.96, "mo": 0.88, "kinh": 0.74}
#: Cùng ba mức, cho lớp kính cửa sổ khi Lumen có ảnh nền riêng (mỏng hơn để ảnh còn hiện).
WALL_GLASS: dict[str, float] = {"dac": 0.85, "mo": 0.62, "kinh": 0.45}
#: Độ vượt của OutBack — 0 là không nảy.
BOUNCE: dict[str, float] = {"khong": 0.0, "vua": 1.7, "nhieu": 2.6}
#: Hệ số thời lượng hiệu ứng, như animFactor của dynsle.
SPEED: dict[str, float] = {"tat": 0.01, "nhanh": 0.6, "vua": 1.0, "cham": 1.6}

DEFAULT_GLASS = "kinh"
DEFAULT_BOUNCE = "vua"
DEFAULT_SPEED = "vua"

_TABLES = {"glass": (GLASS, DEFAULT_GLASS), "bounce": (BOUNCE, DEFAULT_BOUNCE), "speed": (SPEED, DEFAULT_SPEED)}


def clean(kind: str, value: str) -> str:
    """Return `value` if it is a known choice for `kind`, else that kind's default."""
    table, default = _TABLES[kind]
    return value if value in table else default


def number(kind: str, value: str) -> float:
    """Return the number a choice stands for (alpha, overshoot or time factor)."""
    table, default = _TABLES[kind]
    return table.get(value, table[default])
