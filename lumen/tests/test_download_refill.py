"""F-5: bài đồng bộ về phải được LẤP vào đúng dòng đang chờ, không đẻ dòng thứ hai.

`sync_songs.adopt_song` dựng một dòng `tracks` chỗ trống cho bài chỉ có trong ảnh
chụp: đủ tên, đủ link, không có file. Dòng đó đã nằm trong track, đã có thứ tự,
người dùng đã nhìn thấy nó. Tải lại mà gọi `add_track()` là để lại đúng dòng ấy
nằm im trong track, câm vĩnh viễn, còn bài thật thì nằm ở một dòng khác — QĐ-016.

Câu hỏi thứ hai của file này: hạn mức của gói Free KHÔNG được chặn việc tải lại.
Đây là nhạc người dùng đã có ở máy khác, không phải một lần tải mới.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from lumen.bridge.download_bridge import DownloadBridge  # noqa: E402
from lumen.bridge.library_bridge import LibraryBridge  # noqa: E402
from lumen.core import db, paths, sync_songs  # noqa: E402
from lumen.core.downloader import DownloadResult  # noqa: E402
from lumen.core.repository import PlaylistRepository, TrackRepository  # noqa: E402
from lumen.core.youtube import parse_url  # noqa: E402

VIDEO_ID = "dQw4w9WgXcQ"
VIDEO_URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"
# Mốc "thêm vào track" của MÁY KIA. Tải lại không được đóng dấu lại (CB-024).
SNAPSHOT_ADDED_AT = 1_700_000_000


@pytest.fixture(scope="module")
def qapp() -> QGuiApplication:
    return QGuiApplication.instance() or QGuiApplication([])


class _FakeDownloader:
    """Viết ra mp3 giả, và trả về ĐÚNG mã video của link được hỏi."""

    def __init__(self, fallback_dir: Path) -> None:
        self.calls = 0
        self.fallback_dir = fallback_dir
        # Đường lấp dòng chỗ trống hỏi downloader "file rơi vào thư mục nào"
        # để CHÉP vào đúng chỗ đó (CB-036). Fake phải trả lời được, nếu không
        # nó không còn giống cái nó đang đóng thế.
        self.music_dir = fallback_dir

    def download(self, url, *, target_dir=None, on_progress=None,
                 should_cancel=None, known_artists=None):
        self.calls += 1
        video_id = parse_url(url).video_id
        out_dir = target_dir if target_dir is not None else self.fallback_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        media = out_dir / f"{video_id}.mp3"
        media.write_bytes(b"\x00fake-audio")
        return DownloadResult(
            video_id=video_id,
            source_url=url,
            title="Never Gonna Give You Up",
            artist="Rick Astley",
            uploader="Rick Astley",
            duration_ms=213_000,
            file_path=media,
            cover_path=None,
        )


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
def bridge(qapp, library, playlist_repository, tmp_path, monkeypatch) -> DownloadBridge:
    monkeypatch.setattr(paths, "music_dir", lambda: tmp_path / "Music")
    downloader = _FakeDownloader(tmp_path / "Music")
    made = DownloadBridge(downloader, library, playlist_repository)
    made.downloader = downloader  # tiện cho test đếm số lần đụng mạng
    return made


def _pump_until(predicate, timeout_ms: int = 5000) -> bool:
    """Chạy vòng lặp sự kiện thật cho tới khi predicate() đúng, hoặc hết giờ."""
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


def _placeholder(conn, playlist_repository: PlaylistRepository, video_id: str = VIDEO_ID) -> int:
    """Dựng đúng thứ một vòng đồng bộ để lại: một dòng chỗ trống, nằm sẵn trong track."""
    songs = {
        video_id: {
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "title": "Never Gonna Give You Up",
            "artist": "Rick Astley",
            "duration_ms": 213_000,
        }
    }
    track_id = sync_songs.adopt_song(conn, video_id, songs, SNAPSHOT_ADDED_AT)
    conn.commit()
    # Hai dòng chỗ trống nằm trong CÙNG một track — F-5 §1 cấm dựng track thứ
    # hai cùng tên, và cảnh thật cũng vốn là một track nhận cả hai bài.
    existing = next((p for p in playlist_repository.list_all() if p.name == "Sandbox B"), None)
    playlist = existing or playlist_repository.create("Sandbox B")
    playlist_repository.add_track(playlist.id, track_id)
    return track_id


def _count_rows(conn) -> int:
    return int(conn.execute("SELECT COUNT(*) AS n FROM tracks").fetchone()["n"])


class TestLapChuKhongThem:
    def test_tai_lai_lap_dung_dong_cho_trong(self, bridge, library, playlist_repository, conn) -> None:
        """Cùng một `id` trước và sau: dòng trong track được lấp tại chỗ."""
        track_id = _placeholder(conn, playlist_repository)

        bridge.redownload(track_id)
        assert _pump_until(lambda: bool(library.track_for(track_id).file_path)), "quá giờ"

        assert _count_rows(conn) == 1, "tải lại không được đẻ ra dòng thứ hai"
        filled = library.track_for(track_id)
        assert Path(filled.file_path).exists(), "dòng cũ phải trỏ vào file thật"
        assert filled.id == track_id, "phải là ĐÚNG dòng cũ, không phải dòng mới"

    def test_bai_van_nam_trong_track_cu_dung_cho_cu(self, bridge, playlist_repository, conn) -> None:
        """Thành viên track không được đụng tới: dòng cũ vẫn ở đó, vẫn một mình."""
        track_id = _placeholder(conn, playlist_repository)
        playlist_id = playlist_repository.list_all()[0].id

        bridge.redownload(track_id)
        assert _pump_until(lambda: _count_rows(conn) == 1 and bool(
            playlist_repository.tracks(playlist_id)[0].file_path)), "quá giờ"

        songs = playlist_repository.tracks(playlist_id)
        assert len(songs) == 1, "một bài hai dòng là đúng cái lỗi này sinh ra để chặn"
        assert songs[0].id == track_id

    def test_added_at_giu_moc_cua_anh_chup(self, bridge, library, playlist_repository, conn) -> None:
        """CB-024: đóng dấu `now()` lên dữ liệu khôi phục làm máy này nuốt máy kia."""
        track_id = _placeholder(conn, playlist_repository)

        bridge.redownload(track_id)
        assert _pump_until(lambda: bool(library.track_for(track_id).file_path)), "quá giờ"

        assert library.track_for(track_id).added_at == SNAPSHOT_ADDED_AT

    def test_ten_that_de_len_ten_tam_bang_ma_video(self, bridge, library, playlist_repository, conn) -> None:
        """Ảnh chụp thiếu tên thì dòng chỗ trống mang tên = mã video; tải xong phải có tên thật."""
        track_id = sync_songs.adopt_song(conn, VIDEO_ID, {}, SNAPSHOT_ADDED_AT)
        conn.commit()
        assert library.track_for(track_id).title == VIDEO_ID

        bridge.redownload(track_id)
        assert _pump_until(lambda: bool(library.track_for(track_id).file_path)), "quá giờ"

        assert library.track_for(track_id).title == "Never Gonna Give You Up"


class TestDanLaiChinhLinkDo:
    def test_link_cua_bai_cho_trong_khong_bi_tu_choi(self, bridge, library, playlist_repository, conn) -> None:
        """"Đã có trong thư viện" phải nghĩa là CÓ FILE, không phải "có dòng"."""
        track_id = _placeholder(conn, playlist_repository)
        errors: list[str] = []
        bridge.errorOccurred.connect(errors.append)

        bridge.add(VIDEO_URL)

        assert errors == [], "dán lại đúng link mình vừa mất mà bị từ chối là lỗi"
        assert bridge.rowCount() == 1
        assert _pump_until(lambda: bool(library.track_for(track_id).file_path)), "quá giờ"
        assert _count_rows(conn) == 1, "và nó vẫn phải LẤP, không đẻ dòng mới"

    def test_them_vao_track_khac_khong_di_nhanh_chep(self, bridge, library, playlist_repository, conn) -> None:
        """Nhánh CHÉP vớ phải dòng chỗ trống là chép một đường dẫn rỗng."""
        _placeholder(conn, playlist_repository)
        other = playlist_repository.create("Track khác")
        errors: list[str] = []
        bridge.errorOccurred.connect(errors.append)

        bridge.addToPlaylist(VIDEO_URL, other.id)
        # Chờ tới lúc việc tải XONG, không phải lúc nó vừa bắt đầu: bỏ test giữa
        # chừng là bridge bị thu gom trong khi worker còn đang emit (segfault thật).
        assert _pump_until(lambda: len(playlist_repository.tracks(other.id)) == 1), "quá giờ"

        assert errors == [], f"không được lỗi: {errors}"
        assert bridge.downloader.calls == 1, "phải TẢI, vì máy này chưa có file nào để chép"


class TestSoBaiConThieuFile:
    def test_dem_dung_so_bai_chua_co_file(self, bridge, playlist_repository, conn) -> None:
        _placeholder(conn, playlist_repository)
        _placeholder(conn, playlist_repository, video_id="abcdefghijk")

        bridge.refreshMissing()

        assert bridge.missingCount == 2

    def test_lap_xong_thi_so_do_tu_giam(self, bridge, library, playlist_repository, conn) -> None:
        """Không tự giảm thì cảnh báo "còn 3 bài chưa có file" đứng đó tới lần mở app sau."""
        track_id = _placeholder(conn, playlist_repository)
        bridge.refreshMissing()
        assert bridge.missingCount == 1

        bridge.redownload(track_id)
        assert _pump_until(lambda: bridge.missingCount == 0), "quá giờ"

    def test_bai_da_co_file_khong_bi_xep_hang(self, bridge, library, playlist_repository, conn) -> None:
        _placeholder(conn, playlist_repository)
        notices: list[str] = []
        bridge.noticeOccurred.connect(notices.append)

        bridge.redownloadMissing()
        assert _pump_until(lambda: bridge.missingCount == 0), "quá giờ"
        bridge.redownloadMissing()

        assert bridge.downloader.calls == 1, "gọi lần hai không được tải lại thứ đã có"
        assert notices[-1] == "Không có bài nào cần tải lại."


# --- CB-036: chép trên đĩa trước, link là đường lui --------------------------
#
# Từ bản vá CB-036, mỗi track giữ dòng `tracks` riêng, nên cùng một bài có thể
# có NHIỀU dòng chỗ trống đứng chờ. Hai luật đi kèm, cả hai đều đo ở đây:
# bản mp3 máy này đã có thì chép chứ không tải, và một bài chỉ tải MỘT lần dù
# bao nhiêu dòng đang chờ nó.


def _second_placeholder(conn, playlist_repository: PlaylistRepository) -> int:
    """Dòng chỗ trống thứ hai cho CÙNG một bài, nằm trong một track khác."""
    songs = {VIDEO_ID: {"url": VIDEO_URL, "title": "Never Gonna Give You Up"}}
    track_id = sync_songs.adopt_song(conn, VIDEO_ID, songs, SNAPSHOT_ADDED_AT)
    conn.commit()
    khac = playlist_repository.create("Track thứ hai")
    playlist_repository.add_track(khac.id, track_id)
    return track_id


def _downloaded_copy(library: LibraryBridge, tmp_path: Path) -> object:
    """Bản đã tải thật của đúng bài đó, có file trên đĩa, thuộc thư viện máy này."""
    from lumen.core.models import Track

    media = tmp_path / "Music" / "co-san.mp3"
    media.parent.mkdir(parents=True, exist_ok=True)
    media.write_bytes(b"\x00fake-audio")
    return library.add_track(
        Track(
            source_id=VIDEO_ID,
            source_url=VIDEO_URL,
            real_name="Never Gonna Give You Up",
            artist="Rick Astley",
            duration_ms=213_000,
            file_path=str(media),
        )
    )


class TestChepTrenDiaTruocKhiTai:
    def test_da_co_ban_tren_dia_thi_khong_dung_toi_mang(
        self, bridge, library, playlist_repository, conn, tmp_path
    ) -> None:
        """Bản mp3 nằm ngay trên đĩa thì chép, đừng đi phiền YouTube."""
        _downloaded_copy(library, tmp_path)
        cho_trong = _placeholder(conn, playlist_repository)

        bridge.redownloadMissing()

        assert bridge.downloader.calls == 0, "link là đường LUI, không phải đường đầu"
        assert library.track_for(cho_trong).file_path, "dòng phải được lấp"

    def test_ban_chep_la_file_rieng_khong_dung_chung_duong_dan(
        self, bridge, library, playlist_repository, conn, tmp_path
    ) -> None:
        """`file_path` là UNIQUE: hai dòng trỏ chung một file thì dòng sau lấp hụt."""
        co_san = _downloaded_copy(library, tmp_path)
        cho_trong = _placeholder(conn, playlist_repository)

        bridge.redownloadMissing()

        moi = library.track_for(cho_trong).file_path
        assert moi and moi != co_san.file_path
        assert Path(moi).exists() and Path(co_san.file_path).exists()

    def test_hai_dong_cho_cung_mot_bai_chi_tai_MOT_lan(
        self, bridge, library, playlist_repository, conn
    ) -> None:
        """Máy này chưa có gì: tải một bản, dòng còn lại chép theo sau."""
        mot = _placeholder(conn, playlist_repository)
        hai = _second_placeholder(conn, playlist_repository)

        bridge.redownloadMissing()
        assert _pump_until(lambda: bool(library.track_for(hai).file_path))

        assert bridge.downloader.calls == 1, "một bài thì tải một lần, dù mấy track chờ"
        duong_dan = {library.track_for(mot).file_path, library.track_for(hai).file_path}
        assert len(duong_dan) == 2 and all(duong_dan), "mỗi dòng một bản băng riêng"

    def test_moi_dong_van_nam_dung_track_cua_no(
        self, bridge, library, playlist_repository, conn
    ) -> None:
        """Lấp xong không được làm hai track dồn về một dòng — đó là gốc CB-036."""
        mot = _placeholder(conn, playlist_repository)
        hai = _second_placeholder(conn, playlist_repository)

        bridge.redownloadMissing()
        assert _pump_until(lambda: bool(library.track_for(hai).file_path))

        assert playlist_repository.playlists_of(mot) != playlist_repository.playlists_of(hai)
        assert len(playlist_repository.playlists_of(mot)) == 1
        assert len(playlist_repository.playlists_of(hai)) == 1

    def test_lap_dung_dong_da_dat_hang_khong_lap_bua(
        self, bridge, library, playlist_repository, conn
    ) -> None:
        """Hai dòng cùng chờ: bài tải xong phải vào dòng đã đặt hàng nó."""
        mot = _placeholder(conn, playlist_repository)
        hai = _second_placeholder(conn, playlist_repository)
        truoc = _count_rows(conn)

        bridge.redownload(hai)
        assert _pump_until(lambda: bool(library.track_for(hai).file_path))

        # Phân biệt được hai dòng vì chúng lấy file từ hai đường khác nhau:
        # dòng ĐẶT HÀNG lấy chính file downloader vừa viết ra, dòng còn lại lấy
        # bản chép. Thiếu `track_id` thì `store` hỏi lại theo mã video và lấp
        # vào dòng có `id` nhỏ hơn — tức là lấp bừa, đúng lỗi này canh.
        tai_ve = bridge.downloader.music_dir / f"{VIDEO_ID}.mp3"
        assert library.track_for(hai).file_path == str(tai_ve)
        assert library.track_for(mot).file_path not in ("", None, str(tai_ve))
        assert _count_rows(conn) == truoc, "không dòng thứ ba nào được đẻ ra"
        # `mot` được chép theo sau — đúng luật một bài một lần tải.
        assert bridge.downloader.calls == 1
