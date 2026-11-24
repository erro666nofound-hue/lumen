"""Tests for Lumen's global shortcuts."""

from __future__ import annotations

import json

from lumen.core import keybinds


def test_combo_orders_modifiers() -> None:
    assert keybinds.combo(["ALT", "SUPER"], "1") == "SUPER + ALT + 1"


def test_taken_reads_hyprctl_json() -> None:
    raw = json.dumps([{"modmask": 64, "key": "d", "description": "Shell: Launcher"},
                      {"modmask": 72, "key": "P", "description": "Lumen: Phát / tạm dừng"}])
    taken = keybinds.taken_binds(raw)
    assert taken["SUPER + D"] == "Shell: Launcher"
    assert "SUPER + ALT + P" in taken


def test_check_refuses_with_reason() -> None:
    taken = {"SUPER + D": "Shell: Launcher", "SUPER + ALT + P": "Lumen: Phát / tạm dừng"}
    assert "Launcher" in keybinds.check("t1", "SUPER + D", ["SUPER"], taken, {})
    assert "SUPER, CTRL hoặc ALT" in keybinds.check("t1", "K", [], taken, {})
    assert "Phát track ô 2" in keybinds.check("t1", "SUPER + ALT + 2", ["SUPER", "ALT"], taken, {"t2": "SUPER + ALT + 2"})
    # Lumen's own old bind is not a conflict
    assert keybinds.check("toggle", "SUPER + ALT + P", ["SUPER", "ALT"], taken, {}) == ""


def test_write_owns_its_file_and_requires_it_once(tmp_path) -> None:
    custom = tmp_path / "custom"
    custom.mkdir()
    (custom / "keybinds.lua").write_text("-- của bro\nhl.bind(\"F10\", function() end, {})\n")
    keybinds.write({"t1": "SUPER + ALT + 1", "mini": ""}, "/home/x/.local/bin/lumen", custom)
    keybinds.write({"t1": "SUPER + ALT + 1"}, "/home/x/.local/bin/lumen", custom)
    mine = (custom / "lumen-keys.lua").read_text()
    assert 'hl.bind("SUPER + ALT + 1", hl.dsp.exec_cmd("/home/x/.local/bin/lumen --slot 1")' in mine
    theirs = (custom / "keybinds.lua").read_text()
    assert theirs.startswith("-- của bro\nhl.bind(\"F10\"")
    assert theirs.count('require("custom.lumen-keys")') == 1


def test_cli_sends_playback_commands(monkeypatch) -> None:
    """--toggle/--next/--prev/--slot go to the running Lumen and never start the app."""
    from lumen.core import cli, ipc

    sent = []
    monkeypatch.setattr(ipc, "send", lambda command: sent.append(command) or True)
    assert cli.handle_fast_path(["--toggle"]) == 0
    assert cli.handle_fast_path(["--slot", "2"]) == 0
    assert sent == [ipc.CMD_TOGGLE, "slot2"]
    monkeypatch.setattr(ipc, "send", lambda command: False)
    assert cli.handle_fast_path(["--next"]) == 1
    assert ipc.is_valid("slot3") and not ipc.is_valid("slot4")
