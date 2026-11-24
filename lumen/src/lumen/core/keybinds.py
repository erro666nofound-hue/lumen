"""Global keyboard shortcuts for Lumen, held by Hyprland (round 2 of R-1).

Wayland không cho app tự giữ phím toàn cục, nên Lumen GHI phím vào cấu hình
Hyprland rồi bảo nó nạp lại; phím bấm xong chạy shim `lumen --…`, lệnh đó nói
qua socket với bản đang chạy (core/ipc.py).

Lumen chỉ sở hữu file `custom/lumen-keys.lua`. File `custom/keybinds.lua` là
của bro — Lumen chỉ thêm đúng MỘT dòng `require` có đánh dấu, một lần.
Thuần Python, không Qt.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

#: (khoá, tên hiện ra, tham số cho shim `lumen`). "show" = gọi `lumen` trần.
ACTIONS: tuple[tuple[str, str, str], ...] = (
    ("t1", "Phát track ô 1", "--slot 1"),
    ("t2", "Phát track ô 2", "--slot 2"),
    ("t3", "Phát track ô 3", "--slot 3"),
    ("toggle", "Phát / tạm dừng", "--toggle"),
    ("next", "Bài tiếp", "--next"),
    ("prev", "Bài trước", "--prev"),
    ("mini", "Mở Mini Lumen", "--mini"),
    ("show", "Hiện cửa sổ Lumen", ""),
)
ACTION_KEYS = tuple(a[0] for a in ACTIONS)
_LABEL = {a[0]: a[1] for a in ACTIONS}
_ARGS = {a[0]: a[2] for a in ACTIONS}

MOD_ORDER = ("SUPER", "CTRL", "ALT", "SHIFT")
#: Bit modmask của Hyprland.
_MOD_BITS = {"SHIFT": 1, "CTRL": 4, "ALT": 8, "SUPER": 64}
_DESC_PREFIX = "Lumen: "
FILE_NAME = "lumen-keys.lua"
_REQUIRE_MARK = "-- Lumen: phím tắt do Lumen › Cài đặt › Phím tắt ghi vào custom/lumen-keys.lua"
_REQUIRE_LINE = 'if is_file_exists(HOME .. "/.config/hypr/custom/lumen-keys.lua") then require("custom.lumen-keys") end'


def combo(mods: list[str], key: str) -> str:
    """Spell a shortcut the way Hyprland binds it: 'SUPER + ALT + 1'."""
    ordered = [m for m in MOD_ORDER if m in mods]
    return " + ".join([*ordered, key])


def taken_binds(hyprctl_json: str) -> dict[str, str]:
    """Map every bound combo (from `hyprctl binds -j`) to its description."""
    out: dict[str, str] = {}
    try:
        rows = json.loads(hyprctl_json or "[]")
    except json.JSONDecodeError:
        return out
    for row in rows:
        key = str(row.get("key") or "")
        if not key:
            continue
        mods = [name for name, bit in _MOD_BITS.items() if int(row.get("modmask", 0)) & bit]
        desc = str(row.get("description") or "").strip() or "một phím tắt khác"
        out[combo(mods, key.upper() if len(key) == 1 else key)] = desc
    return out


def check(action: str, wanted: str, mods: list[str], taken: dict[str, str], mine: dict[str, str]) -> str:
    """Return why `wanted` cannot be used for `action`, or "" when it can."""
    if not any(m in mods for m in ("SUPER", "CTRL", "ALT")):
        return "Phải có SUPER, CTRL hoặc ALT — chỉ một phím trơn thì lúc gõ chữ cũng bị bắt. Thử phím khác."
    for other, value in mine.items():
        if value == wanted and other != action:
            return f"Không đặt được: {wanted} đã gán cho “{_LABEL.get(other, other)}”. Thử phím khác."
    holder = taken.get(wanted, "")
    if holder and not holder.startswith(_DESC_PREFIX):
        return f"Không đặt được: {wanted} đang dùng cho “{holder}”. Thử phím khác."
    return ""


def render(binds: dict[str, str], shim: str) -> str:
    """The whole lumen-keys.lua for these binds."""
    lines = ["-- Lumen tự sinh file này (Cài đặt › Phím tắt). Đừng sửa tay — mỗi lần đặt phím là ghi lại.", ""]
    for action in ACTION_KEYS:
        key = binds.get(action, "")
        if not key:
            continue
        cmd = (shim + " " + _ARGS[action]).strip()
        lines.append(f'hl.bind("{key}", hl.dsp.exec_cmd("{cmd}"), {{ description = "{_DESC_PREFIX}{_LABEL[action]}" }})')
    # Mini Lumen nổi ở góc dưới phải, ghim mọi workspace (bro, 2026-10-05).
    rule = 'hl.window_rule({match = {title = "^(Mini Lumen)$" }, %s})'
    lines += ["", "-- Mini Lumen: cửa sổ nổi nhỏ ở góc dưới phải, ghim trên mọi workspace."]
    lines += [rule % body for body in ("float = true", 'size = {"460", "230"}',
                                        'move = {"(monitor_w-480)", "(monitor_h-260)"}', "pin = true")]
    return "\n".join(lines) + "\n"


def write(binds: dict[str, str], shim: str, custom_dir: Path) -> None:
    """Write lumen-keys.lua (atomically) and make sure keybinds.lua requires it, once."""
    custom_dir.mkdir(parents=True, exist_ok=True)
    target = custom_dir / FILE_NAME
    tmp = target.with_suffix(".lua.tmp")
    tmp.write_text(render(binds, shim), encoding="utf-8")
    os.replace(tmp, target)
    keybinds = custom_dir / "keybinds.lua"
    text = keybinds.read_text(encoding="utf-8") if keybinds.exists() else ""
    if _REQUIRE_MARK not in text:
        addition = ("" if text.endswith("\n") or not text else "\n") + f"\n{_REQUIRE_MARK}\n{_REQUIRE_LINE}\n"
        tmp2 = keybinds.with_suffix(".lua.tmp")
        tmp2.write_text(text + addition, encoding="utf-8")
        os.replace(tmp2, keybinds)
