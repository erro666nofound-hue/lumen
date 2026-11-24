"""Public build: no account, no sign-in, no sync server — guard that none of it comes back."""
from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "lumen"
REPO = ROOT.parent

#: Mô-đun của đăng nhập Google, gói, đồng bộ và kho file — bản public không có.
_GONE_MODULES = (
    "lumen.core.account_store", "lumen.core.google_auth", "lumen.core.plan_client",
    "lumen.core.plan_store", "lumen.core.plans", "lumen.core.entitlements",
    "lumen.core.download_quota", "lumen.core.files_client", "lumen.core.files_plan",
    "lumen.core.sync_client", "lumen.core.sync_merge", "lumen.core.sync_apply",
    "lumen.core.sync_one", "lumen.core.sync_panel", "lumen.core.sync_restore",
    "lumen.bridge.account_bridge", "lumen.bridge.account_worker",
    "lumen.bridge.entitlements_bridge", "lumen.bridge.files_bridge",
    "lumen.bridge.files_worker", "lumen.bridge.sync_bridge",
    "lumen.bridge.sync_panel_bridge", "lumen.bridge.sync_panel_jobs",
    "lumen.bridge.sync_worker",
)

#: Đối tượng QML mà bản đầy đủ gắn vào context — bản public không gắn cái nào.
_GONE_QML_OBJECTS = re.compile(r"\b(Account|Sync|SyncPanel|Backup|Gate)\.")

#: Dấu vết của máy chủ riêng / OAuth trong mã nguồn.
_SERVER_TRACES = re.compile(
    r"workers\.dev|apps\.googleusercontent\.com|GOCSPX-|accounts\.google\.com|oauth2"
)


@pytest.mark.parametrize("name", _GONE_MODULES)
def test_account_and_sync_modules_are_gone(name: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(name)


def test_no_qml_reaches_for_account_or_sync() -> None:
    offenders = [
        f"{path.relative_to(SRC)}: {line.strip()}"
        for path in (SRC / "ui").rglob("*.qml")
        for line in path.read_text(encoding="utf-8").splitlines()
        if _GONE_QML_OBJECTS.search(line)
    ]
    assert offenders == []


def test_account_and_sync_components_are_gone() -> None:
    components = {p.name for p in (SRC / "ui" / "components").glob("*.qml")}
    gone = {"AccountChip.qml", "AccountPanel.qml", "SyncSheet.qml", "SyncDeleteConfirm.qml",
            "SyncPanelSongRow.qml", "SyncPanelTrackRow.qml"}
    assert components & gone == set()


def test_app_registers_no_account_or_sync_object() -> None:
    app = (SRC / "app.py").read_text(encoding="utf-8")
    for name in ("Account", "Sync", "SyncPanel", "Backup"):
        assert f'setContextProperty("{name}"' not in app


def test_settings_have_no_account_page() -> None:
    sidebar = (SRC / "ui" / "views" / "Sidebar.qml").read_text(encoding="utf-8")
    settings = (SRC / "ui" / "views" / "SettingsView.qml").read_text(encoding="utf-8")
    assert '["sync"' not in sidebar
    assert "Tài khoản & đồng bộ" not in sidebar + settings
    assert "Đăng nhập" not in settings


def test_no_private_server_or_oauth_trace_in_the_repo() -> None:
    offenders = []
    for path in REPO.rglob("*"):
        if ".git" in path.parts or not path.is_file() or path.name == Path(__file__).name:
            continue
        if path.suffix not in {".py", ".qml", ".js", ".sh", ".md", ".toml", ".json", ".desktop", ".mjs"}:
            continue
        if _SERVER_TRACES.search(path.read_text(encoding="utf-8", errors="replace")):
            offenders.append(str(path.relative_to(REPO)))
    assert offenders == []


def test_no_server_folder_and_no_requests_dependency() -> None:
    assert not (ROOT / "server").exists()
    install = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
    assert "requests" not in install


def test_an_old_full_build_config_still_loads_and_drops_account_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A config.json written by the full build (with account keys) must open cleanly here."""
    import json

    from lumen.core import paths
    from lumen.core.config import load_config, save_config

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = paths.config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"volume": 55, "google_client_id": "x", "google_client_secret": "y",
                                "account_server_url": "https://example.invalid"}), encoding="utf-8")
    config = load_config()
    assert config.volume == 55
    assert not hasattr(config, "google_client_secret")
    save_config(config)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert not {"google_client_id", "google_client_secret", "account_server_url"} & set(saved)
