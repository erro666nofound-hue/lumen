"""QML face of the global shortcuts page (Settings › Phím tắt, round 2 of R-1)."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QObject, Qt, Signal, Slot

from lumen.core import keybinds

log = logging.getLogger(__name__)

_HYPRCTL_TIMEOUT_S = 3
_MODS = ((Qt.KeyboardModifier.MetaModifier, "SUPER"), (Qt.KeyboardModifier.ControlModifier, "CTRL"),
         (Qt.KeyboardModifier.AltModifier, "ALT"), (Qt.KeyboardModifier.ShiftModifier, "SHIFT"))
_NAMED = {Qt.Key.Key_Space: "space", Qt.Key.Key_Left: "left", Qt.Key.Key_Right: "right",
          Qt.Key.Key_Up: "up", Qt.Key.Key_Down: "down", Qt.Key.Key_Return: "Return"}


def key_name(qt_key: int) -> str:
    """Hyprland's name for a Qt key, or "" for keys Lumen does not offer."""
    if Qt.Key.Key_A.value <= qt_key <= Qt.Key.Key_Z.value or Qt.Key.Key_0.value <= qt_key <= Qt.Key.Key_9.value:
        return chr(qt_key)
    if Qt.Key.Key_F1.value <= qt_key <= Qt.Key.Key_F12.value:
        return f"F{qt_key - Qt.Key.Key_F1.value + 1}"
    return next((name for key, name in _NAMED.items() if key.value == qt_key), "")


class KeybindsBridge(QObject):
    """Hold the shortcut table, check a new combo, write it to Hyprland."""

    changed = Signal()

    def __init__(self, binds: dict[str, str], slots: dict[str, int], custom_dir: Path, shim: str,
                 live: bool, on_changed: Callable[[KeybindsBridge], None] | None = None,
                 parent: Any = None) -> None:
        super().__init__(parent)
        self._binds = {k: v for k, v in binds.items() if k in keybinds.ACTION_KEYS}
        self._slots = {k: int(v) for k, v in slots.items() if k in ("t1", "t2", "t3")}
        self._custom_dir = custom_dir
        self._shim = shim
        # `live` = đây là cấu hình Hyprland THẬT của máy này: chỉ khi đó mới bảo
        # Hyprland nạp lại. Sandbox ghi vào thư mục giả và không đụng Hyprland.
        self._live = live
        self._on_changed = on_changed
        # Luật cửa sổ Mini nằm cùng file — ghi ngay lúc mở app để Mini luôn nổi.
        if self._live:
            try:
                keybinds.write(self._binds, self._shim, self._custom_dir)
                self._hyprctl("reload")
            except OSError as exc:
                log.warning("Cannot write Hyprland rules: %s", exc)

    def snapshot(self) -> tuple[dict[str, str], dict[str, int]]:
        """Return (binds, slots) for saving."""
        return dict(self._binds), dict(self._slots)

    def _hyprctl(self, *args: str) -> str:
        try:
            done = subprocess.run(["hyprctl", *args], capture_output=True, text=True,
                                  timeout=_HYPRCTL_TIMEOUT_S, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            log.warning("hyprctl %s failed: %s", " ".join(args), exc)
            return ""
        return done.stdout

    def _save(self) -> str:
        """Write the file and reload Hyprland; return an error sentence or ""."""
        try:
            keybinds.write(self._binds, self._shim, self._custom_dir)
        except OSError as exc:
            log.warning("Cannot write Hyprland keybinds: %s", exc)
            return f"Không ghi được cấu hình Hyprland ({exc.strerror or exc})."
        if self._live:
            self._hyprctl("reload")
        if self._on_changed is not None:
            self._on_changed(self)
        self.changed.emit()
        return ""

    @Slot(str, int, int, result=str)
    def tryBind(self, action: str, qt_key: int, qt_modifiers: int) -> str:
        """Bind `action` to the pressed combo; return "" or why it was refused."""
        name = key_name(qt_key)
        if not name:
            return "Phím này chưa dùng được — thử chữ, số hoặc F1–F12."
        mods = [label for flag, label in _MODS if qt_modifiers & flag.value]
        wanted = keybinds.combo(mods, name)
        taken = keybinds.taken_binds(self._hyprctl("binds", "-j")) if self._live else {}
        why = keybinds.check(action, wanted, mods, taken, self._binds)
        if why:
            return why
        self._binds[action] = wanted
        return self._save()

    @Slot(str, result=str)
    def clearBind(self, action: str) -> str:
        """Drop the shortcut of one action."""
        self._binds.pop(action, None)
        return self._save()

    @Slot(str, int)
    def setSlot(self, action: str, playlist_id: int) -> None:
        """Pick which track a slot shortcut plays."""
        if action in ("t1", "t2", "t3"):
            self._slots[action] = playlist_id
            if self._on_changed is not None:
                self._on_changed(self)
            self.changed.emit()

    def slot_playlist(self, number: int) -> int:
        """The playlist id behind slot 1-3, or -1."""
        return self._slots.get(f"t{number}", -1)

    binds = Property("QVariantMap", lambda self: dict(self._binds), notify=changed)
    slots = Property("QVariantMap", lambda self: dict(self._slots), notify=changed)
    actions = Property("QVariantList", lambda self: [[k, label, k in ("t1", "t2", "t3")]
                                                    for k, label, _ in keybinds.ACTIONS], constant=True)
