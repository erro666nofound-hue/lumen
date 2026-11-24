"""Move files around for tracks: copy an mp3 in, take one in from outside, delete.

Copying is used when the same YouTube video is added to a second track: cheaper
and kinder to YouTube than downloading it again. Deleting is used when a whole
track is thrown away. `receive_verified` is the third door: bytes arriving from
somewhere this machine does not control. No SQL, no Qt, no network.
"""

from __future__ import annotations

import filecmp
import hashlib
import logging
import shutil
from collections.abc import Iterable, Iterator
from pathlib import Path

log = logging.getLogger(__name__)

#: Đuôi của file đang viết dở. Không bao giờ trùng `.mp3` — mọi chỗ trong app
#: quét thư mục nhạc theo đuôi, và một file cụt lọt vào đó là một bài câm.
PARTIAL_SUFFIX = ".part"


class BytesNotAsPromised(Exception):
    """Dòng bytes vừa nhận băm ra một địa chỉ khác thứ đã hỏi.

    Lỗi trần, không phải `LumenError`: file này không biết bytes đến từ đâu nên
    không nói được câu tiếng Việt nào đúng. Người gọi biết, và dịch.
    """


def receive_verified(chunks: Iterator[bytes], destination: Path, address: str) -> int:
    """Write a stream to `destination` only if its sha256 is `address`; return bytes written.

    Hai luật ở đây, cả hai hỏng IM LẶNG nếu bỏ, và cả hai là lý do hàm này tồn
    tại thay vì để người gọi tự `open().write()`:

    1. **Viết ra file tạm, đổi tên vào chỗ ở bước cuối.** Đứt giữa chừng mà đã
       viết thẳng vào đích thì `tracks.file_path` trỏ tới một file cụt: app coi
       như "đã có file", không xếp nó vào hàng đợi nào nữa, bài đó câm mãi mãi.
    2. **Băm ngay lúc viết, đối chiếu trước khi đặt vào chỗ.** Kho đặt tên theo
       nội dung (QĐ-027) nên việc này làm được — không làm thì cách đặt tên ấy
       chẳng để làm gì: người dùng bấm một bài, nghe ra bài khác, không ai kêu.

    Băm CÙNG LÚC viết, không đọc lại file lần hai: 30 MiB đọc thêm một lượt cho
    mỗi bài, nhân với cả một đợt kéo về, là thời gian mua được bằng không.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + PARTIAL_SUFFIX)
    digest = hashlib.sha256()
    written = 0
    try:
        with partial.open("wb") as handle:
            for chunk in chunks:
                handle.write(chunk)
                digest.update(chunk)
                written += len(chunk)
    except BaseException:
        # `BaseException`: đứt mạng ném ra lỗi của requests, đĩa đầy ném OSError,
        # và người dùng đóng app giữa chừng ném KeyboardInterrupt. Cả ba đều
        # phải dọn cái file dở — để lại là rác không ai biết là rác.
        partial.unlink(missing_ok=True)
        raise
    if digest.hexdigest() != address:
        partial.unlink(missing_ok=True)
        raise BytesNotAsPromised(f"nhận được {digest.hexdigest()}, đã hỏi {address}")
    # `move` chứ không `rename`: thư mục tạm và thư mục nhạc có thể khác ổ đĩa.
    shutil.move(str(partial), str(destination))
    return written


def copy_into(source_file: Path, target_dir: Path) -> Path:
    """Copy an existing mp3 into another track's folder; returns the new path.

    Returns the existing path untouched if the file is already there.
    Adds a numeric suffix if a different file already occupies the name.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    destination = target_dir / source_file.name

    if destination.exists():
        if destination.samefile(source_file) or filecmp.cmp(source_file, destination, shallow=False):
            return destination
        destination = _next_available_name(destination)

    shutil.copy2(source_file, destination)
    return destination


def duplicate_into(source_file: Path, target_dir: Path) -> Path:
    """Copy an mp3 into a folder as its OWN file; returns a path nothing else uses.

    Khác `copy_into` đúng một chỗ, và chỗ đó quan trọng: gặp một file y hệt nằm
    sẵn ở đích, `copy_into` trả về chính file đó ("đã có rồi, khỏi chép"), còn
    hàm này vẫn chép ra bản mới.

    Người gọi ở đây là dòng `tracks` vừa nhân bản cho track thứ hai (CB-036).
    Nó cần bản băng của RIÊNG nó: `tracks.file_path` là UNIQUE, nên trả về
    đường dẫn của dòng kia là lấp không được, dòng mới nằm câm vĩnh viễn.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    destination = target_dir / source_file.name
    if destination.exists():
        destination = _next_available_name(destination)
    shutil.copy2(source_file, destination)
    return destination


def _next_available_name(path: Path) -> Path:
    """Return the first path.stem-N.suffix (N starting at 2) that does not exist yet."""
    counter = 2
    candidate = path.parent / f"{path.stem}-{counter}{path.suffix}"
    while candidate.exists():
        counter += 1
        candidate = path.parent / f"{path.stem}-{counter}{path.suffix}"
    return candidate


def remove_files(files: Iterable[Path]) -> int:
    """Delete exactly the paths given; return how many actually went away.

    Deliberately literal: no globbing, no recursion, no walking upwards. This
    runs when a whole track is deleted, so a bug here destroys music. One
    unlink failing must not abort the rest -- a track half-deleted on disk but
    fully gone from the database is worse than a leftover file.
    """
    removed = 0
    for path in files:
        try:
            path.unlink()
            removed += 1
        except FileNotFoundError:
            pass                      # already gone: the desired end state anyway
        except OSError:
            log.warning("Could not delete %s", path, exc_info=True)
    return removed


def remove_dir_if_empty(directory: Path) -> bool:
    """Remove a track folder only when nothing is left in it; never recursive."""
    try:
        directory.rmdir()             # raises if the folder still holds anything
        return True
    except (FileNotFoundError, OSError):
        return False
