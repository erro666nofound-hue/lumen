from __future__ import annotations

import ast
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parent.parent / "src" / "lumen" / "core"

_FORBIDDEN_ROOTS = {"PySide6", "PyQt5", "PyQt6", "PySide2"}


def _core_py_files() -> list[Path]:
    return sorted(CORE_DIR.rglob("*.py"))  # rglob: thư mục con sau này cũng phải bị soi


def _imported_roots(tree: ast.AST) -> set[str]:
    """Collect the top-level package name of every import in a module, at any nesting depth."""
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


def test_core_files_exist() -> None:
    """Sanity check: the core/ directory actually has python files to scan."""
    assert _core_py_files(), f"No .py files found under {CORE_DIR}"


def test_core_never_imports_qt() -> None:
    """No file under core/ may import PySide6 (or any Qt binding), including inside functions."""
    offenders: dict[str, set[str]] = {}
    for path in _core_py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        forbidden = _imported_roots(tree) & _FORBIDDEN_ROOTS
        if forbidden:
            offenders[path.name] = forbidden

    assert not offenders, f"core/ files importing Qt: {offenders}"


def test_core_never_mentions_pythonpath() -> None:
    """No file under core/ may contain the literal string 'PYTHONPATH' (repo path-safety rule)."""
    offenders = [
        path.name
        for path in _core_py_files()
        if "PYTHONPATH" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, f"core/ files mentioning PYTHONPATH: {offenders}"

