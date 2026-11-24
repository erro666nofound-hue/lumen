"""Tìm những chương trình ngoài mà Lumen cần: libmpv và ffmpeg.

Chạy từ mã nguồn thì hai thứ này nằm sẵn trong hệ thống. Nhưng khi đã đóng gói
thành một file chạy, máy người dùng KHÔNG có chúng — ta phải gói kèm và tự chỉ
đường, nếu không app mở lên là chết ngay ở bước phát nhạc.

Thuần Python, không Qt.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path

from lumen.core import paths

log = logging.getLogger(__name__)

#: Thư mục con trong gói, nơi đặt libmpv/ffmpeg đi kèm.
BUNDLED_DIR_NAME = "runtime"


def is_frozen() -> bool:
    """Report whether Lumen is running from a packaged build, not from source.

    Nuitka đặt `__compiled__` vào module; PyInstaller đặt `sys.frozen`. Kiểm cả
    hai để không phải sửa lại chỗ này khi đổi công cụ đóng gói.
    """
    return bool(getattr(sys, "frozen", False)) or "__compiled__" in globals()


def bundle_dir() -> Path | None:
    """Return the folder holding bundled binaries, or None when running from source."""
    if not is_frozen():
        return None
    return Path(sys.executable).resolve().parent / BUNDLED_DIR_NAME


def _bundled(name: str) -> Path | None:
    """Tìm một chương trình đi kèm trong gói, kèm đuôi .exe khi ở Windows."""
    folder = bundle_dir()
    if folder is None:
        return None
    candidate = folder / (f"{name}.exe" if paths.on_windows() else name)
    return candidate if candidate.is_file() else None


def ffmpeg_path() -> str:
    """Return the ffmpeg to run: the bundled one if present, else whatever is on PATH.

    Trả về CHUỖI chứ không phải Path: khi không có bản đi kèm thì câu trả lời
    đúng là chữ "ffmpeg" trần, để hệ điều hành tự tra trong PATH.
    """
    bundled = _bundled("ffmpeg")
    if bundled is not None:
        return str(bundled)
    return shutil.which("ffmpeg") or "ffmpeg"


def prepare_runtime() -> None:
    """Make bundled libraries findable BEFORE anything tries to load them.

    Phải gọi TRƯỚC khi tạo trình phát: `python-mpv` tìm libmpv bằng cách tra
    `%PATH%` (Windows) hoặc đường dẫn thư viện hệ thống (Linux) ngay lúc nạp.
    Gọi sau là muộn — nó đã bỏ cuộc và ném lỗi rồi.
    """
    folder = bundle_dir()
    if folder is None or not folder.is_dir():
        return

    os.environ["PATH"] = f"{folder}{os.pathsep}{os.environ.get('PATH', '')}"
    if paths.on_windows():
        # Từ Python 3.8, Windows KHÔNG còn tra PATH khi nạp DLL bằng ctypes —
        # phải khai báo thư mục một cách tường minh.
        add_dll_directory = getattr(os, "add_dll_directory", None)
        if add_dll_directory is not None:
            add_dll_directory(str(folder))
    else:
        existing = os.environ.get("LD_LIBRARY_PATH", "")
        os.environ["LD_LIBRARY_PATH"] = f"{folder}{os.pathsep}{existing}" if existing else str(folder)
    log.info("Bundled runtime at %s", folder)
