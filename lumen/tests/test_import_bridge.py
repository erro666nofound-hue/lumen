"""Coverage for ImportBridge: an mp3 from the owner's disk becoming a track row.

The architectural claim this file exists to guard is the last one: a row born
here has NO `source_id`, and therefore never appears in a sync snapshot. That
is F-5a′'s decision, and it is the reason the UI has to say out loud that these
songs are not backed up (QĐ-019, last section).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from lumen.bridge.import_bridge import ImportBridge  # noqa: E402
from lumen.bridge.library_bridge import LibraryBridge  # noqa: E402
from lumen.core import db, mp3_import, paths  # noqa: E402
from lumen.core.repository import PlaylistRepository, TrackRepository  # noqa: E402
from tests.test_mp3_import import write_mp3  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QGuiApplication:
    return QGuiApplication.instance() or QGuiApplication([])


@pytest.fixture
def conn(tmp_path: Path):
    return db.connect(tmp_path / "library.db")


@pytest.fixture
def library(conn) -> LibraryBridge:
    return LibraryBridge(TrackRepository(conn))


@pytest.fixture
def playlist_repository(conn) -> PlaylistRepository:
    return PlaylistRepository(conn)


@pytest.fixture
def music_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point both the music folder and the cover folder somewhere disposable."""
    monkeypatch.setattr(paths, "music_dir", lambda: tmp_path / "Music")
    monkeypatch.setattr(paths, "covers_dir", lambda: tmp_path / "covers")
    return tmp_path


def _pump_until(predicate, timeout_ms: int = 5000) -> bool:
    """Run a real event loop until predicate() is true or the timeout expires."""
    loop = QEventLoop()
    ticker = QTimer()
    ticker.setInterval(10)
    ticker.timeout.connect(lambda: loop.quit() if predicate() else None)
    guard = QTimer()
    guard.setSingleShot(True)
    guard.timeout.connect(loop.quit)
    ticker.start()
    guard.start(timeout_ms)
    loop.exec()
    ticker.stop()
    guard.stop()
    return predicate()


def _import(bridge: ImportBridge, files: list[Path], playlist_id: int) -> list[int]:
    added: list[int] = []
    bridge.trackAdded.connect(added.append)
    finished: list[bool] = []
    bridge.playlistContentsChanged.connect(lambda _pid: finished.append(True))
    bridge.importFiles([str(path) for path in files], playlist_id)
    _pump_until(lambda: bool(finished))
    return added


def test_imported_file_lands_in_the_track_folder_with_its_tags(
    qapp, library, playlist_repository, music_home
) -> None:
    source = write_mp3(music_home / "ngoài" / "a.mp3", title="Bài của tôi", artist="Ai đó")
    playlist = playlist_repository.create("Roadtrip")
    bridge = ImportBridge(library, playlist_repository)

    assert len(_import(bridge, [source], playlist.id)) == 1

    tracks = playlist_repository.tracks(playlist.id)
    assert len(tracks) == 1
    track = tracks[0]
    assert track.title == "Bài của tôi"
    # Tên bài lấy từ tag, TÁC GIẢ THÌ KHÔNG (QĐ-025): file lạ rất hay ghi tên bài
    # vào ô tác giả, nên bài custom không mang tác giả nào cả.
    assert track.artist == ""
    assert track.artist_label == "Custom mp3"
    assert 900 < track.duration_ms < 1200
    # Chép vào thư mục CỦA TRACK, không trỏ vào file gốc: cả app giả định nó
    # sở hữu file, và xoá track là xoá file. Trỏ thẳng vào nhạc riêng của chủ
    # dự án thì một cú xoá trong app là xoá nhạc ngoài đời.
    assert Path(track.file_path).parent == music_home / "Music" / "Roadtrip"
    assert Path(track.file_path).exists()
    assert source.exists()


def test_an_imported_row_has_no_source_id_at_all(
    qapp, library, playlist_repository, music_home
) -> None:
    source = write_mp3(music_home / "ngoài" / "a.mp3", title="Bài của tôi")
    playlist = playlist_repository.create("Roadtrip")

    _import(ImportBridge(library, playlist_repository), [source], playlist.id)

    track = playlist_repository.tracks(playlist.id)[0]
    # NULL, không phải "". Hai dạng rỗng là hai lần phải nhớ, và `NO_LINK`
    # của sync_state chỉ đúng khi cả code đồng ý một dạng.
    assert track.source_id is None
    assert track.source_url is None


def test_an_imported_song_keeps_its_file_hash_as_identity(
    qapp, library, playlist_repository, music_home, conn
) -> None:
    """Bài nhập từ đĩa không có link, nhưng giữ sha256 của file làm danh tính bền."""
    source = write_mp3(music_home / "ngoài" / "a.mp3", title="Bài của tôi")
    playlist = playlist_repository.create("Roadtrip")

    _import(ImportBridge(library, playlist_repository), [source], playlist.id)

    key = mp3_import.file_digest(Path(playlist_repository.tracks(playlist.id)[0].file_path))
    row = conn.execute("SELECT source_id, content_hash FROM tracks").fetchone()
    assert (row["source_id"] or "") == ""
    assert row["content_hash"] == key


def test_the_hash_stored_is_the_hash_of_the_COPIED_file(
    qapp, library, playlist_repository, music_home
) -> None:
    """Cột `content_hash` phải tả đúng cục bytes mà `file_path` đang trỏ tới.

    Băm file nguồn thay vì bản đã chép thì hai cái BẰNG NHAU hôm nay và lệch
    nhau ngày cú chép hỏng — mà lúc đó máy chủ mới kêu, ở tận đầu kia đường
    dây, bằng câu "bytes không khớp địa chỉ" không chỉ về đây.
    """
    source = write_mp3(music_home / "ngoài" / "a.mp3", title="Bài của tôi")
    playlist = playlist_repository.create("Roadtrip")

    _import(ImportBridge(library, playlist_repository), [source], playlist.id)

    track = playlist_repository.tracks(playlist.id)[0]
    copied = Path(track.file_path)
    assert copied != source                      # đã chép sang thư mục của app
    assert track.content_hash == mp3_import.file_digest(copied)
    assert len(track.content_hash) == 64         # hình dạng máy chủ đòi
    assert track.content_hash == track.content_hash.lower()


def test_two_copies_of_one_file_share_one_address(
    qapp, library, playlist_repository, music_home
) -> None:
    """Nhập hai lần = hai dòng, hai file trên đĩa, MỘT địa chỉ trong kho.

    Đây là thứ QĐ-027 mua bằng cách đặt tên theo nội dung, và là lý do
    `content_hash` cố ý KHÔNG `UNIQUE`: kho chỉ tốn một chỗ, còn database vẫn
    được phép có hai dòng (CB-036 — mỗi track một bản băng riêng).
    """
    source = write_mp3(music_home / "ngoài" / "a.mp3", title="Bài của tôi")
    playlist = playlist_repository.create("Roadtrip")
    bridge = ImportBridge(library, playlist_repository)

    _import(bridge, [source], playlist.id)
    _import(bridge, [source], playlist.id)

    rows = playlist_repository.tracks(playlist.id)
    assert len({row.file_path for row in rows}) == 2
    assert len({row.content_hash for row in rows}) == 1


def test_the_same_file_imported_twice_becomes_two_independent_rows(
    qapp, library, playlist_repository, music_home
) -> None:
    # `tracks.file_path` là UNIQUE. Trả về chính file cũ ở lần thứ hai là dòng
    # mới lấp hụt rồi nằm câm vĩnh viễn (CB-036) — nên mỗi lần nhập là một bản
    # băng riêng.
    source = write_mp3(music_home / "ngoài" / "a.mp3", title="Bài của tôi")
    playlist = playlist_repository.create("Roadtrip")
    bridge = ImportBridge(library, playlist_repository)

    _import(bridge, [source], playlist.id)
    _import(bridge, [source], playlist.id)

    tracks = playlist_repository.tracks(playlist.id)
    assert len(tracks) == 2
    assert tracks[0].file_path != tracks[1].file_path
    assert all(Path(track.file_path).exists() for track in tracks)


def test_one_bad_file_does_not_stop_the_rest_of_the_batch(
    qapp, library, playlist_repository, music_home
) -> None:
    good = write_mp3(music_home / "ngoài" / "a.mp3", title="Bài tốt")
    bad = music_home / "ngoài" / "ảnh.png"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_bytes(b"\x89PNG")
    playlist = playlist_repository.create("Roadtrip")
    bridge = ImportBridge(library, playlist_repository)
    errors: list[str] = []
    bridge.errorOccurred.connect(errors.append)

    added = _import(bridge, [bad, good], playlist.id)

    assert len(added) == 1
    assert len(errors) == 1 and "ảnh.png" in errors[0]
    assert playlist_repository.tracks(playlist.id)[0].title == "Bài tốt"


def test_embedded_artwork_becomes_the_cover(
    qapp, library, playlist_repository, music_home
) -> None:
    # Việc thứ ba của mã video (lấy ảnh) không mất hẳn: bài nhập tay lấy bìa từ
    # thẻ nhúng trong chính file, không đi mạng.
    cover = b"\xff\xd8" + b"fake-cover"
    source = write_mp3(music_home / "ngoài" / "a.mp3", title="Bài", cover=cover)
    playlist = playlist_repository.create("Roadtrip")

    _import(ImportBridge(library, playlist_repository), [source], playlist.id)

    track = playlist_repository.tracks(playlist.id)[0]
    assert track.cover_path and Path(track.cover_path).read_bytes() == cover


def test_importing_into_a_track_that_is_gone_says_so(
    qapp, library, playlist_repository, music_home
) -> None:
    source = write_mp3(music_home / "ngoài" / "a.mp3", title="Bài")
    bridge = ImportBridge(library, playlist_repository)
    errors: list[str] = []
    bridge.errorOccurred.connect(errors.append)

    bridge.importFiles([str(source)], 999)

    assert errors and "không còn" in errors[0]


def test_file_urls_from_the_dialog_are_accepted(
    qapp, library, playlist_repository, music_home
) -> None:
    source = write_mp3(music_home / "ngoài" / "a b.mp3", title="Bài")
    playlist = playlist_repository.create("Roadtrip")
    bridge = ImportBridge(library, playlist_repository)
    added: list[int] = []
    bridge.trackAdded.connect(added.append)
    finished: list[bool] = []
    bridge.playlistContentsChanged.connect(lambda _pid: finished.append(True))

    bridge.importFiles([source.as_uri()], playlist.id)
    assert _pump_until(lambda: bool(finished))
    assert len(added) == 1
