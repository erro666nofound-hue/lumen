"""Bài tải xong đi vào thư viện: LẤP dòng chỗ trống, hay dựng dòng mới.

Đồng bộ mang danh sách đi chứ không mang mp3 đi, nên máy nhận có những dòng
`tracks` đủ tên, đủ link, không có file (`core/sync_songs.py` dựng chúng).
Tải lại một bài như thế mà gọi `add_track()` là đẻ ra dòng THỨ HAI: dòng mới có
file nhưng không nằm trong track nào, dòng cũ vẫn nằm trong track và vẫn câm.
Người dùng thấy một bài hai chỗ, và bấm vào cái nằm trong track thì vẫn không
kêu — QĐ-016.

Từ CB-036 file này còn trả lời câu ngược lại — một dòng chỗ trống lấp bằng
GÌ — vì hai câu đó là một luật nhìn từ hai phía. Máy này có thể đã có sẵn bản
mp3 của đúng bài đó, thuộc về một track khác; khi ấy chép trên đĩa là xong,
không cần phiền YouTube. Link chỉ là đường lui.

Tách khỏi `download_bridge.py` vì file đó đã 490 dòng, và vì câu hỏi ở đây
thuần dữ liệu: không Qt, không signal, không hàng đợi. Đưa vào một hàm thì kiểm
được nó mà không phải dựng cả một bridge.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from lumen.core.library_files import duplicate_into, remove_files
from lumen.core.models import Track

log = logging.getLogger(__name__)


def store(library: Any, downloaded: Track, track_id: int | None = None) -> tuple[Track, bool]:
    """Put a finished download into the library; return (row, filled_a_placeholder).

    `filled` là câu trả lời cho hạn mức: lấp một dòng chỗ trống KHÔNG phải một
    lần tải mới, đó là nhạc người dùng đã có ở máy khác.

    `track_id` là dòng mà việc tải này ĐƯỢC ĐẶT HÀNG để lấp. Có nó thì lấp đúng
    dòng đó, không đi hỏi lại theo mã video: từ CB-036 một bài có thể có nhiều
    dòng chỗ trống cùng đứng chờ, mỗi track một dòng, và `placeholder_for` chỉ
    biết trả về một cái. Người dán link bằng tay thì không có số này — đường cũ
    giữ nguyên cho họ.
    """
    if track_id is not None:
        stored = library.attach_file(track_id, downloaded)
        if stored is not None:
            return stored, True
        log.warning("Không lấp được dòng %s như đã đặt hàng, dựng dòng mới", track_id)
        return library.add_track(downloaded), False

    placeholder = library.placeholder_for(downloaded.source_id or "")
    if placeholder is not None and placeholder.id is not None:
        stored = library.attach_file(placeholder.id, downloaded)
        if stored is not None:
            return stored, True
        # Chỉ xảy ra khi ĐÚNG file đó đã thuộc về một dòng khác (`file_path` là
        # UNIQUE). Không nuốt: rơi xuống đường cũ để lỗi nói ra bằng tiếng người.
        log.warning(
            "Không lấp được dòng chỗ trống %s, dựng dòng mới", placeholder.id
        )
    return library.add_track(downloaded), False


def fill_from_disk(library: Any, waiting: Track, target_dir: Path) -> Track | None:
    """Fill a file-less row from an mp3 this machine already has; None when it cannot.

    Đây là đường NGẮN của việc tải lại: cùng một bài nằm trong hai track là hai
    dòng và hai bản mp3 (QĐ-019), nhưng bản thứ hai không việc gì phải đi qua
    mạng khi bản thứ nhất đang nằm trên đĩa. Không mạng cũng có nghĩa là không
    đụng tới hạn mức — cùng lối nghĩ với nhánh CHÉP của cửa dán link tay.

    Trả None là "chưa lấp được, cứ tải từ link đi": không có bản nào có file,
    hoặc đĩa/database từ chối. Đường lui phải luôn còn đó, nên ở đây không ném.
    """
    if waiting.id is None:
        return None
    donor = library.get_by_source(waiting.source_id or "")
    # `get_by_source` đã lọc "phải CÓ FILE" (CB-031), còn phép so id chặn ca
    # dòng tự chép cho chính mình — vô hại nhưng vô nghĩa.
    if donor is None or donor.id == waiting.id or not donor.file_path:
        return None

    try:
        copied = duplicate_into(Path(donor.file_path), target_dir)
    except OSError:
        log.exception("Không chép được bản có sẵn cho dòng %s", waiting.id)
        return None

    filled = library.attach_file(
        waiting.id,
        Track(
            source_id=waiting.source_id,
            # Link và tên THẬT lấy theo bản có sẵn: nó là bản đã tải thật, nên
            # nó biết YouTube gọi bài này là gì. Tên riêng của dòng đang chờ
            # thì `attach_file` không đụng tới (QĐ-019 luật 1).
            source_url=donor.source_url or waiting.source_url,
            real_name=donor.real_name or waiting.real_name,
            artist=donor.artist,
            duration_ms=donor.duration_ms,
            file_path=str(copied),
            # Ảnh bìa DÙNG CHUNG, không chép: `cover_path` không phải khoá duy
            # nhất, và xoá một track thì `remove_files` chỉ đụng mp3 của nó.
            cover_path=donor.cover_path,
        ),
    )
    if filled is None:
        # Lấp hụt mà vẫn để lại file là bỏ rác trên đĩa của người dùng, và lần
        # sau chép nữa lại đẻ thêm một bản "-2" nữa.
        remove_files([copied])
        log.warning("Lấp hụt dòng %s bằng bản có sẵn, đã dọn file vừa chép", waiting.id)
    return filled
