"""Đổi ảnh bìa của một bài bằng một ảnh có sẵn trên đĩa.

Thuần Python + đĩa: không Qt, không SQL, không mạng — nên pytest chạy được mà
không mở cửa sổ nào. Ai gọi thì tự lo phần ghi đường dẫn mới xuống database.

Ảnh được CHÉP vào kho bìa của app chứ không trỏ thẳng vào file gốc, cùng một lý
do với mp3 nhập từ đĩa (QĐ-024): app coi như nó SỞ HỮU thứ nằm trong kho, nên
trỏ ra ngoài là một ngày nào đó Lumen tự xoá ảnh trong thư mục riêng của chủ dự án.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
from pathlib import Path

from lumen.core.errors import LumenError

log = logging.getLogger(__name__)

#: Đuôi file ảnh nhận vào. Danh sách ĐÓNG: mở rộng ra thì Qt có thể không vẽ
#: được và người dùng chỉ thấy một ô trống, không thấy lỗi.
ALLOWED_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp"})

#: Ảnh bìa to hơn ngần này gần như chắc chắn là ảnh chụp chọn nhầm, không phải
#: bìa album. Chép vào là phình kho bìa mà nhìn không khác gì.
MAX_BYTES = 12 * 1024 * 1024


def adopt(source: Path, covers_dir: Path) -> Path:
    """Chép `source` vào kho bìa và trả về đường dẫn trong kho.

    Tên file trong kho lấy theo VÂN TAY nội dung: cùng một ảnh chọn lại lần hai
    thì rơi đúng vào file cũ, không sinh bản sao. Ném LumenError khi ảnh không
    dùng được — người gọi có câu tiếng Việt sẵn để đưa lên màn hình.
    """
    suffix = source.suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise LumenError(
            f"Unsupported artwork suffix: {suffix!r}",
            user_message="Ảnh bìa phải là file .jpg, .png hoặc .webp.",
        )
    try:
        size = source.stat().st_size
    except OSError as exc:
        raise LumenError(
            f"Cannot read artwork {source}: {exc}",
            user_message="Không đọc được file ảnh vừa chọn.",
        ) from exc
    if size == 0:
        raise LumenError(
            f"Empty artwork file: {source}",
            user_message="File ảnh vừa chọn rỗng.",
        )
    if size > MAX_BYTES:
        raise LumenError(
            f"Artwork too large: {size} bytes",
            user_message="Ảnh bìa quá nặng — chọn ảnh dưới 12 MB.",
        )

    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    target = covers_dir / f"custom-{digest}{suffix}"
    if target.exists():
        return target
    try:
        covers_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    except OSError as exc:
        raise LumenError(
            f"Cannot copy artwork to {target}: {exc}",
            user_message="Không chép được ảnh bìa vào thư viện.",
        ) from exc
    return target
