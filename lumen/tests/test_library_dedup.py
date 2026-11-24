"""Thư viện là danh sách BÀI HÁT, không phải danh sách FILE.

Từ UT-4b mỗi track có thư mục riêng, nên bỏ một bài vào track sẽ tạo thêm một
bản sao trên đĩa VÀ một dòng nữa trong bảng `tracks`. Chủ dự án báo lỗi: thư
viện hiện hai bài y hệt nhau. Các test này canh cho lần sửa đó.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402

from lumen.bridge.library_bridge import LibraryBridge  # noqa: E402
from lumen.core import db  # noqa: E402
from lumen.core.repository import TrackRepository  # noqa: E402
from tests.conftest import make_track  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QGuiApplication:
    return QGuiApplication.instance() or QGuiApplication([])


@pytest.fixture
def repo(tmp_path: Path) -> TrackRepository:
    return TrackRepository(db.connect(tmp_path / "library.db"))


def _titles(bridge: LibraryBridge) -> list[str]:
    return [
        bridge.data(bridge.index(row, 0), LibraryBridge.TitleRole)
        for row in range(bridge.count)
    ]


class TestLibraryShowsEachSongOnce:
    def test_track_copy_does_not_duplicate_the_song(self, qapp, repo: TrackRepository) -> None:
        repo.add(make_track(source_id="vid1", title="Bài A", file_path="/m/Lumen/a.mp3"))
        repo.add(make_track(source_id="vid1", title="Bài A", file_path="/m/Lumen/Cozy/a.mp3"))

        bridge = LibraryBridge(repo)

        assert repo.count() == 2, "cả hai file vẫn phải nằm trong database"
        assert _titles(bridge) == ["Bài A"], "nhưng thư viện chỉ hiện MỘT bài"

    def test_keeps_the_library_root_copy(self, qapp, repo: TrackRepository) -> None:
        """Giữ dòng cũ nhất — đó là bản nằm ở thư mục gốc, không phải bản trong track."""
        first = repo.add(make_track(source_id="vid1", file_path="/m/Lumen/a.mp3"))
        repo.add(make_track(source_id="vid1", file_path="/m/Lumen/Cozy/a.mp3"))

        bridge = LibraryBridge(repo)

        assert bridge.data(bridge.index(0, 0), LibraryBridge.TrackIdRole) == first.id

    def test_three_copies_still_show_once(self, qapp, repo: TrackRepository) -> None:
        for folder in ("Lumen", "Lumen/Cozy", "Lumen/Gaming"):
            repo.add(make_track(source_id="vid1", title="Bài A", file_path=f"/m/{folder}/a.mp3"))

        assert LibraryBridge(repo).count == 1

    def test_different_songs_are_not_merged(self, qapp, repo: TrackRepository) -> None:
        repo.add(make_track(source_id="vid1", title="Bài A", file_path="/m/a.mp3"))
        repo.add(make_track(source_id="vid2", title="Bài B", file_path="/m/b.mp3"))

        assert sorted(_titles(LibraryBridge(repo))) == ["Bài A", "Bài B"]

    def test_rows_without_source_id_are_never_merged(self, qapp, repo: TrackRepository) -> None:
        """Không có source_id thì không có gì để nhận dạng — đừng gộp bừa."""
        repo.add(make_track(source_id=None, title="Bài rời 1", file_path="/m/x.mp3"))
        repo.add(make_track(source_id=None, title="Bài rời 2", file_path="/m/y.mp3"))

        assert LibraryBridge(repo).count == 2

    def test_queue_order_also_has_no_duplicates(self, qapp, repo: TrackRepository) -> None:
        """Hàng đợi phát lấy từ đây, nên nó cũng không được lặp bài."""
        repo.add(make_track(source_id="vid1", file_path="/m/Lumen/a.mp3"))
        repo.add(make_track(source_id="vid1", file_path="/m/Lumen/Cozy/a.mp3"))
        repo.add(make_track(source_id="vid2", file_path="/m/Lumen/b.mp3"))

        ids = LibraryBridge(repo).ordered_track_ids()

        assert len(ids) == len(set(ids)) == 2
