"""Coverage for core/mp3_import: what an mp3 on the disk says about itself.

Only the reading half lives here — copying and row-writing are the bridge's,
and they are covered in tests/test_import_bridge.py.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from mutagen.id3 import APIC, ID3, TIT2, TPE1
from mutagen.mp3 import MP3

from lumen.core import mp3_import
from lumen.core.errors import ImportFileError

# Một khung MPEG1 Layer3 128kbps 44.1kHz đúng luật: 4 byte header + 413 byte
# im lặng. Bốn mươi khung ≈ 1.04 giây — đủ để mutagen đọc ra độ dài thật.
_FRAME = b"\xff\xfb\x90\x00" + b"\x00" * 413
_JPEG = b"\xff\xd8" + b"fake-cover"


def write_mp3(
    path: Path, *, title: str = "", artist: str = "", cover: bytes | None = None
) -> Path:
    """Write a real, tiny, playable-looking mp3 with the tags asked for."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_FRAME * 40)
    if not (title or artist or cover):
        return path
    audio = MP3(str(path), ID3=ID3)
    audio.add_tags()
    if title:
        audio.tags.add(TIT2(encoding=3, text=title))
    if artist:
        audio.tags.add(TPE1(encoding=3, text=artist))
    if cover:
        audio.tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=cover))
    audio.save()
    return path


def test_reads_title_artist_duration_and_cover(tmp_path: Path) -> None:
    path = write_mp3(tmp_path / "a.mp3", title="Bài thử", artist="Nghệ sĩ", cover=_JPEG)

    song = mp3_import.read_song(path)

    assert song.title == "Bài thử"
    assert song.artist == "Nghệ sĩ"
    assert 900 < song.duration_ms < 1200
    assert song.cover_bytes == _JPEG


def test_untagged_file_falls_back_to_the_filename(tmp_path: Path) -> None:
    # Nhạc người ta tự có thường KHÔNG có thẻ. Đó là chuyện thường, không phải
    # lỗi: tên file là thứ duy nhất còn lại, và nó phải được dùng.
    path = write_mp3(tmp_path / "Chiều xuân.mp3")

    song = mp3_import.read_song(path)

    assert song.title == "Chiều xuân"
    assert song.artist == ""
    assert song.cover_bytes is None


def test_a_file_that_is_not_an_mp3_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "ảnh.png"
    path.write_bytes(b"\x89PNG")

    with pytest.raises(ImportFileError) as caught:
        mp3_import.read_song(path)
    assert ".mp3" in caught.value.user_message


def test_a_missing_file_is_refused_by_name(tmp_path: Path) -> None:
    with pytest.raises(ImportFileError) as caught:
        mp3_import.read_song(tmp_path / "không có.mp3")
    assert "không có.mp3" in caught.value.user_message


def test_a_broken_mp3_is_refused_instead_of_crashing(tmp_path: Path) -> None:
    path = tmp_path / "hỏng.mp3"
    path.write_bytes(b"not audio at all")

    with pytest.raises(ImportFileError):
        mp3_import.read_song(path)


def test_file_url_from_the_dialog_becomes_a_plain_path() -> None:
    # QML FileDialog trả về file:// và mã hoá dấu cách. Sai chỗ này là mọi bài
    # có dấu cách trong tên đều "không tìm thấy file".
    assert mp3_import.local_path("file:///nhà/toast/a%20b.mp3") == Path("/nhà/toast/a b.mp3")
    assert mp3_import.local_path("  /nhà/toast/c.mp3  ") == Path("/nhà/toast/c.mp3")


def test_cover_is_written_once_per_destination(tmp_path: Path) -> None:
    path = write_mp3(tmp_path / "a.mp3", title="A", cover=_JPEG)
    song = mp3_import.read_song(path)
    covers = tmp_path / "covers"

    first = mp3_import.save_cover(song, covers, tmp_path / "Music" / "Track" / "a.mp3")
    again = mp3_import.save_cover(song, covers, tmp_path / "Music" / "Track" / "a.mp3")
    other = mp3_import.save_cover(song, covers, tmp_path / "Music" / "Khác" / "a.mp3")

    assert first is not None and first.read_bytes() == _JPEG
    # Cùng một đích thì cùng một ảnh; đích khác thì ảnh khác — tên ảnh đi theo
    # DÒNG sắp sinh ra, không đi theo tên bài (hai bài trùng tên vẫn hai ảnh).
    assert again == first
    assert other != first


def test_a_song_without_artwork_saves_nothing(tmp_path: Path) -> None:
    song = mp3_import.read_song(write_mp3(tmp_path / "a.mp3", title="A"))

    assert mp3_import.save_cover(song, tmp_path / "covers", tmp_path / "a.mp3") is None


# ---------------------------------------------------------------------------
# Địa chỉ trong kho — QĐ-027
# ---------------------------------------------------------------------------


def test_the_digest_is_the_sha256_of_the_bytes_on_disk(tmp_path: Path) -> None:
    """Cùng một mảnh giấy dán bên hông với thứ máy chủ tự tính lại khi nhận."""
    path = write_mp3(tmp_path / "a.mp3", title="A")

    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    assert mp3_import.file_digest(path) == expected
    assert len(expected) == 64                          # hình dạng `FILE_ADDRESS` đòi


def test_two_files_with_the_same_bytes_get_the_same_address(tmp_path: Path) -> None:
    """Chép ra chỗ khác, đổi TÊN — vẫn một địa chỉ. Kho vì thế chỉ tốn một chỗ."""
    first = write_mp3(tmp_path / "a.mp3", title="A")
    second = tmp_path / "thư mục khác" / "tên hoàn toàn khác.mp3"
    second.parent.mkdir()
    second.write_bytes(first.read_bytes())

    assert mp3_import.file_digest(second) == mp3_import.file_digest(first)


def test_one_changed_byte_changes_the_address(tmp_path: Path) -> None:
    """Ghi thẻ vào file là ĐỔI ĐỊA CHỈ của nó — lý do không chỗ nào trong Lumen ghi thẻ.

    QĐ-027 đo được rằng `artwork.adopt()` chép ảnh ra thư mục riêng chứ không
    viết vào mp3, và đóng cái nếp đó thành luật. Test này là chỗ nếp ấy gãy
    thành tiếng nếu có ai mở lại.
    """
    path = write_mp3(tmp_path / "a.mp3", title="A")
    before = mp3_import.file_digest(path)

    tags = ID3(path)
    tags.add(TPE1(encoding=3, text=["Ai đó"]))
    tags.save(path)

    assert mp3_import.file_digest(path) != before


def test_a_file_larger_than_one_chunk_hashes_whole(tmp_path: Path) -> None:
    """Băm theo khúc phải ra đúng như băm một phát — vòng lặp đọc thiếu thì im lặng."""
    path = tmp_path / "dài.mp3"
    path.write_bytes(_FRAME * 6000)                     # ~2.5 MiB, qua 1 MiB một khúc

    assert mp3_import.file_digest(path) == hashlib.sha256(path.read_bytes()).hexdigest()


def test_a_file_that_cannot_be_read_says_so_in_the_owner_s_words(tmp_path: Path) -> None:
    """Đĩa hỏng giữa chừng không được thành một hash sai — phải là lỗi có tên."""
    with pytest.raises(ImportFileError) as caught:
        mp3_import.file_digest(tmp_path / "không có thật.mp3")

    assert "không có thật.mp3" in caught.value.user_message
