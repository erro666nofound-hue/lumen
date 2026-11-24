"""Read an mp3 sitting on the disk into the facts a `tracks` row needs.

No SQL, no Qt, no copying — this module only LOOKS at a file. Copying is
`library_files.duplicate_into`, and writing the row is the bridge's job.

DÒNG SINH RA TỪ ĐÂY KHÔNG CÓ `source_id`, và đó là chủ ý, không phải thiếu sót.
Không có link YouTube thì không có mã video, và ba việc mà mã video đang gánh
(QĐ-019) rơi như sau:

* **Đồng bộ**: được, nhờ `content_hash` (QĐ-027) — sha256 của chính byte trong
  file, cũng là địa chỉ của nó trên R2. `file_digest` dưới đây băm, cửa nhập
  cất vào cột, `sync_state.HAS_IDENTITY` hỏi tới nó. Bịa một khoá theo tên +
  độ dài mà đoán sai thì XOÁ NHẦM nhạc của máy kia — hash tránh đúng chuyện đó.
* **Tải lại từ link gốc**: không bao giờ làm được — `sync_state.HAS_LINK` trả
  lời KHÔNG, mãi mãi. Mất file thì kéo về từ kho R2, không phải tải lại.
* **Lấy ảnh**: lấy từ thẻ APIC nhúng trong chính file mp3, không đi mạng.

Vì thế giao diện phải nói thật một câu KHÁC với trước QĐ-027: danh sách thì đi
được, còn cục bytes chỉ nằm trong kho sau khi có người đẩy nó lên. Hai chuyện,
và gộp thành một câu là hứa thừa hoặc doạ thừa.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

import mutagen
from mutagen.id3 import ID3NoHeaderError
from mutagen.mp3 import MP3

from .errors import ImportFileError

log = logging.getLogger(__name__)

#: Chỉ mp3. Cả app đang là hình dạng mp3: downloader ghi ra mp3, `copy_into`
#: đặt tên theo đuôi file, ảnh bìa đọc từ thẻ ID3. Nhận .flac/.m4a vào đây là
#: mở một mặt trận khác, không phải một dòng `if`.
SUPPORTED_SUFFIXES = frozenset({".mp3"})

#: Ảnh bìa lấy từ thẻ đặt tên theo băm của ĐƯỜNG DẪN ĐÍCH, không theo tên bài:
#: hai bài trùng tên vẫn phải ra hai file ảnh, còn nhập lại đúng file đó thì
#: phải ghi đè đúng ảnh cũ chứ không đẻ ảnh mới.
_COVER_NAME_LENGTH = 16


@dataclass(frozen=True)
class ImportedSong:
    """Everything read off one mp3 — enough to build a row, not enough to be one."""

    path: Path
    title: str
    artist: str
    duration_ms: int
    cover_bytes: bytes | None = None


def local_path(raw: str) -> Path:
    """Turn what a file dialog hands back into a plain path.

    QML `FileDialog` trả về `file:///nhà/toast/a b.mp3` chứ không trả đường dẫn
    trần, và dấu cách trong tên đi qua đó thành `%20`. Nhận cả hai dạng ở một
    chỗ để mọi nơi gọi khỏi tự đoán.
    """
    text = raw.strip()
    if text.startswith("file://"):
        parsed = urlparse(text)
        return Path(unquote(parsed.path))
    return Path(text).expanduser()


#: Băm theo từng khúc, không nuốt cả file vào RAM. Trần một file của kho là 30
#: MiB (`server/worker.js`), và một đợt nhập có thể là 200 bài liên tiếp.
_DIGEST_CHUNK = 1024 * 1024


def file_digest(path: Path) -> str:
    """Return the sha256 of a file's bytes, lowercase hex — its address in the store.

    BĂM FILE NÀO thì đó là luật, không phải chi tiết: phải băm CHÍNH file mà
    `tracks.file_path` trỏ tới, tức bản đã chép vào thư mục của app — không phải
    file gốc người dùng chọn. Máy chủ băm lại thân yêu cầu và từ chối nếu lệch
    ("bytes không khớp địa chỉ"), nên một hash lấy từ file khác là cú đẩy hỏng
    ở tận đầu kia, cách xa chỗ gây ra nó.

    *Hình dung:* mảnh giấy dán bên hông vali phải tả đúng cái vali đang gửi, chứ
    không phải cái vali giống nó ở nhà.
    """
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(_DIGEST_CHUNK):
                digest.update(chunk)
    except OSError as exc:
        raise ImportFileError(
            f"Cannot hash {path}: {exc}",
            user_message=f"Không đọc được {path.name} để ghi vào bản sao lưu.",
        ) from exc
    return digest.hexdigest()


def read_song(path: Path) -> ImportedSong:
    """Read one mp3's tags; raise ImportFileError with a sentence the owner can read."""
    if not path.exists():
        raise ImportFileError(
            f"{path} does not exist",
            user_message=f"Không tìm thấy file: {path.name}",
        )
    if not path.is_file():
        raise ImportFileError(
            f"{path} is not a file",
            user_message=f"{path.name} không phải một file nhạc.",
        )
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ImportFileError(
            f"{path} is not an mp3",
            user_message=f"Lumen chỉ nhận file .mp3 — {path.name} thì chưa.",
        )

    try:
        audio = MP3(str(path))
    except (mutagen.MutagenError, OSError) as exc:
        raise ImportFileError(
            f"Cannot read {path}: {exc}",
            user_message=f"Không đọc được {path.name}. File có thể đã hỏng.",
        ) from exc

    # Thẻ thiếu là chuyện THƯỜNG với nhạc người ta tự có, không phải lỗi: rơi
    # về tên file, và để nghệ sĩ trống thay vì bịa "Unknown Artist" — chỗ nào
    # cần chữ hiển thị thì tự lo, còn database giữ đúng thứ đã biết.
    return ImportedSong(
        path=path,
        title=_tag_text(audio, "TIT2") or path.stem,
        artist=_tag_text(audio, "TPE1"),
        duration_ms=_duration_ms(audio),
        cover_bytes=_embedded_cover(audio),
    )


def save_cover(song: ImportedSong, covers_dir: Path, for_path: Path) -> Path | None:
    """Write the song's embedded artwork next to every other cover; None when it has none.

    `for_path` là chỗ file mp3 nằm SAU KHI chép, không phải chỗ nó được chọn:
    tên ảnh phải đi theo dòng `tracks` sắp sinh ra, mà dòng đó giữ đường dẫn đích.
    """
    if not song.cover_bytes:
        return None
    digest = hashlib.sha1(str(for_path).encode("utf-8")).hexdigest()[:_COVER_NAME_LENGTH]
    cover_path = covers_dir / f"local-{digest}.jpg"
    try:
        covers_dir.mkdir(parents=True, exist_ok=True)
        cover_path.write_bytes(song.cover_bytes)
    except OSError as exc:
        # Bài không có bìa vẫn là bài nghe được. Hỏng ảnh không được phép làm
        # hỏng cú nhập.
        log.warning("Failed to write cover for %s: %s", for_path, exc)
        return None
    return cover_path


def _tag_text(audio: MP3, frame: str) -> str:
    """Return the first string in an ID3 frame, or "" when the tag is not there."""
    tags = audio.tags
    if tags is None:
        return ""
    try:
        values = tags.getall(frame)
    except (ID3NoHeaderError, AttributeError):
        return ""
    for value in values:
        text = "".join(str(part) for part in getattr(value, "text", []))
        if text.strip():
            return text.strip()
    return ""


def _duration_ms(audio: MP3) -> int:
    """Length in milliseconds, 0 when the header does not say."""
    length = getattr(audio.info, "length", 0) or 0
    return int(length * 1000)


def _embedded_cover(audio: MP3) -> bytes | None:
    """Return the bytes of the first embedded picture, or None."""
    tags = audio.tags
    if tags is None:
        return None
    try:
        pictures = tags.getall("APIC")
    except (ID3NoHeaderError, AttributeError):
        return None
    for picture in pictures:
        data = getattr(picture, "data", None)
        if data:
            return bytes(data)
    return None
