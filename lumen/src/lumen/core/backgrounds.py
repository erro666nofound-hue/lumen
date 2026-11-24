"""Nền của Lumen: ảnh người dùng chọn.

Thuần Python, không Qt. Một giá trị nền chỉ là một chuỗi: rỗng nghĩa là không
có nền riêng (để lộ nền máy phía sau), còn lại là đường dẫn tới file ảnh.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
from pathlib import Path

from lumen.core import paths

log = logging.getLogger(__name__)

#: Nhớ tối đa bao nhiêu ảnh đã chọn. Đủ để bấm lại cái quen dùng, không nhiều
#: tới mức thành một thư viện ảnh thứ hai.
MAX_REMEMBERED = 12

#: Độ dài vân tay nội dung gắn vào tên bản sao. Giao diện cắt đúng bấy nhiêu ký
#: tự cuối để hiện lại tên gốc.
FINGERPRINT_LEN = 8


def store_dir() -> Path:
    """Return the folder Lumen keeps its own copies of chosen wallpapers in."""
    return paths.data_dir() / "wallpapers"


def store(source: str) -> str:
    """Copy a chosen image into Lumen's own folder and return the copy's path.

    Nhớ ĐƯỜNG DẪN gốc thôi là chưa đủ: người dùng đổi tên, dọn thư mục Tải về
    hay rút USB là ảnh biến mất khỏi bảng chọn. Chép vào kho riêng thì ảnh còn
    mãi cùng app.

    Tên bản sao giữ TÊN GỐC rồi mới tới vân tay nội dung: giữ vân tay để chọn
    lại đúng ảnh đó lần nữa không sinh ra bản sao thứ hai, giữ tên gốc để bảng
    chọn còn hiện được cái tên người dùng nhận ra.
    """
    path = Path(source)
    if not path.is_file():
        return ""
    if path.parent == store_dir():
        return str(path)

    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()[:FINGERPRINT_LEN]
    stem = "".join(ch for ch in path.stem if ch.isalnum() or ch in " -_")[:40].strip()
    target = store_dir() / f"{stem or 'anh'}-{digest}{path.suffix.lower()}"
    if target.exists():
        return str(target)
    try:
        store_dir().mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    except OSError:
        log.exception("Cannot copy wallpaper %s into %s", path, store_dir())
        # Chép không được thì vẫn dùng ảnh gốc — mất tính bền, nhưng người dùng
        # vẫn đặt được nền, và đó mới là việc họ vừa yêu cầu.
        return str(path)
    return str(target)


def is_image(value: str) -> bool:
    """Report whether this value points at an image file that still exists."""
    return bool(value) and Path(value).is_file()


def clean_path(value: str) -> str:
    """Turn what a file dialog returns into a plain path."""
    cleaned = (value or "").strip()
    if cleaned.startswith("file://"):
        cleaned = cleaned[len("file://") :]
    return cleaned


def remember(history: list[str], value: str) -> list[str]:
    """Return the history with `value` in it, keeping everything where it was.

    KHÔNG đưa ảnh vừa chọn lên đầu: các ô đang bày ra trước mắt mà nhảy chỗ mỗi
    lần bấm thì lần sau tìm lại rất khó. Chỉ có cái viền chọn di chuyển.
    """
    if not value or value in history:
        return list(history)
    return [*history, value][-MAX_REMEMBERED:]


def surviving(history: list[str]) -> list[str]:
    """Drop remembered images whose file has since been deleted or moved."""
    return [item for item in history if is_image(item)]
