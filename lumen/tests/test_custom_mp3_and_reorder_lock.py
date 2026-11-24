"""Bài custom không có tác giả (QĐ-025), và khoá kéo-thả phải nói ra lý do (CB-043).

Hai luật này đều là luật CỐ Ý VỨT thứ đang có — một cái vứt tag TPE1, một cái
vứt quyền kéo thả. Không có test thì phiên sau nhìn thấy "thiếu sót" rồi đi
"sửa" lại đúng cái vừa chốt.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402

from lumen.bridge.track_songs_bridge import TrackSongsBridge  # noqa: E402
from lumen.core import artwork, db, sorting  # noqa: E402
from lumen.core.errors import LumenError  # noqa: E402
from lumen.core.models import CUSTOM_ARTIST, Track  # noqa: E402
from lumen.core.repository import PlaylistRepository, TrackRepository  # noqa: E402
from tests.conftest import make_track  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QGuiApplication:
    return QGuiApplication.instance() or QGuiApplication([])


@pytest.fixture
def repo(tmp_path: Path) -> PlaylistRepository:
    return PlaylistRepository(db.connect(tmp_path / "library.db"))


@pytest.fixture
def track_repo(tmp_path: Path) -> TrackRepository:
    return TrackRepository(db.connect(tmp_path / "library.db"))


@pytest.fixture
def bridge(repo: PlaylistRepository, track_repo: TrackRepository) -> TrackSongsBridge:
    bridge = TrackSongsBridge(repo, track_repo)
    bridge._kept_repo = repo
    return bridge


class TestCustomMp3HasNoArtist:
    def test_a_row_without_source_id_reports_custom_mp3(self) -> None:
        track = Track(real_name="dreamscape", artist="dreamscape", source_id=None)

        assert track.artist_label == CUSTOM_ARTIST

    def test_a_downloaded_row_keeps_its_real_artist(self) -> None:
        track = Track(real_name="Nắng ấm xa dần", artist="Sơn Tùng", source_id="abc123")

        assert track.artist_label == "Sơn Tùng"

    def test_the_tag_is_never_trusted_even_when_it_looks_like_a_name(self) -> None:
        """Lý do của cả luật: file lạ hay ghi TÊN BÀI vào ô tác giả.

        Tin vào tag là app bịa ra một nghệ sĩ tên "dreamscape" và xếp bài dưới
        cái tên đó mãi mãi.
        """
        track = Track(real_name="dreamscape", artist="dreamscape", source_id=None)

        assert track.artist_label != track.artist

    def test_sorting_by_artist_groups_every_custom_song_together(self) -> None:
        tracks = [
            Track(real_name="b", artist="Zzz", source_id=None),
            Track(real_name="a", artist="Aaa", source_id="vid1"),
            Track(real_name="c", artist="Aaa", source_id=None),
        ]

        ordered = sorting.sort_tracks(tracks, sorting.SORT_ARTIST)

        # "Aaa" < "Custom mp3", và hai bài custom đứng cạnh nhau bất kể tag.
        assert [t.title for t in ordered] == ["a", "b", "c"]

    def test_the_bridge_shows_the_label_not_the_stored_artist(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        playlist = repo.create("Nhập")
        stored = track_repo.add(make_track(title="dreamscape", artist="dreamscape", source_id=None))
        repo.add_track(playlist.id, stored.id)
        bridge.setPlaylist(playlist.id)

        index = bridge.index(0, 0)

        assert bridge.data(index, TrackSongsBridge.ArtistRole) == CUSTOM_ARTIST

    def test_searching_for_custom_finds_the_imported_songs(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository, track_repo: TrackRepository
    ) -> None:
        playlist = repo.create("Trộn")
        imported = track_repo.add(make_track(title="dreamscape", artist="", source_id=None))
        downloaded = track_repo.add(make_track(title="Chạy ngay đi", source_id="vid9"))
        repo.add_track(playlist.id, imported.id)
        repo.add_track(playlist.id, downloaded.id)
        bridge.setPlaylist(playlist.id)

        bridge.setSearch("custom")

        assert bridge.orderedIds() == [imported.id]


class TestReorderLockExplainsItself:
    def test_a_fresh_track_can_be_reordered_and_says_nothing(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository
    ) -> None:
        bridge.setPlaylist(repo.create("Mới").id)

        assert bridge.canReorder is True
        assert bridge.reorderBlockedReason == ""

    def test_another_sort_key_blocks_reorder_and_names_the_way_back(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository
    ) -> None:
        bridge.setPlaylist(repo.create("Sắp").id)

        bridge.setSort(sorting.SORT_ADDED)

        assert bridge.canReorder is False
        assert "Mới thêm" in bridge.reorderBlockedReason
        assert "Thứ tự của bạn" in bridge.reorderBlockedReason

    def test_a_search_blocks_reorder_and_says_so(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository
    ) -> None:
        bridge.setPlaylist(repo.create("Tìm").id)

        bridge.setSearch("abc")

        assert bridge.canReorder is False
        assert "ô tìm" in bridge.reorderBlockedReason

    def test_pressing_your_own_order_twice_never_flips_it(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository
    ) -> None:
        """CB-043: lật ngược thứ tự tự xếp KHOÁ kéo-thả trong khi chip vẫn sáng.

        Người dùng thấy nút nắm biến mất mà chip trông y hệt lúc đang chạy —
        nhìn đúng như app hỏng. Thứ tự tự tay xếp không có chiều ngược, nên bấm
        lần hai không được làm gì cả.
        """
        bridge.setPlaylist(repo.create("Bấm hai lần").id)

        bridge.setSort(sorting.SORT_CUSTOM)
        bridge.setSort(sorting.SORT_CUSTOM)

        assert bridge.sortDescending is False
        assert bridge.canReorder is True
        assert bridge.reorderBlockedReason == ""


class TestArtworkAdopt:
    def _png(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 64)
        return path

    def test_the_image_is_copied_into_the_store_and_the_original_stays(
        self, tmp_path: Path
    ) -> None:
        source = self._png(tmp_path / "ngoài" / "bìa.png")
        covers = tmp_path / "covers"

        stored = artwork.adopt(source, covers)

        assert stored.parent == covers
        assert stored.read_bytes() == source.read_bytes()
        # Chép chứ không chuyển: ảnh riêng của chủ dự án phải còn nguyên chỗ cũ.
        assert source.exists()

    def test_the_same_image_twice_lands_on_one_file(self, tmp_path: Path) -> None:
        covers = tmp_path / "covers"
        first = artwork.adopt(self._png(tmp_path / "a.png"), covers)
        second = artwork.adopt(self._png(tmp_path / "b.png"), covers)

        assert first == second
        assert len(list(covers.iterdir())) == 1

    def test_a_non_image_is_refused_with_a_sentence_the_owner_can_read(
        self, tmp_path: Path
    ) -> None:
        source = tmp_path / "bài.mp3"
        source.write_bytes(b"not an image")

        with pytest.raises(LumenError) as caught:
            artwork.adopt(source, tmp_path / "covers")

        assert ".jpg" in caught.value.user_message

    def test_an_empty_file_is_refused(self, tmp_path: Path) -> None:
        source = tmp_path / "rỗng.png"
        source.write_bytes(b"")

        with pytest.raises(LumenError):
            artwork.adopt(source, tmp_path / "covers")


class TestSetCover:
    def test_setting_a_cover_updates_the_row_and_the_model(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository,
        track_repo: TrackRepository, tmp_path: Path,
    ) -> None:
        playlist = repo.create("Bìa")
        stored = track_repo.add(make_track(title="Bài", source_id="vid7"))
        repo.add_track(playlist.id, stored.id)
        bridge.setPlaylist(playlist.id)
        image = tmp_path / "bìa mới.png"
        image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"y" * 32)

        assert bridge.setCover(stored.id, image.as_uri()) is True

        assert track_repo.get(stored.id).cover_path.endswith(".png")
        assert bridge.data(bridge.index(0, 0), TrackSongsBridge.CoverPathRole).endswith(".png")

    def test_a_bad_image_leaves_the_row_alone(
        self, qapp, bridge: TrackSongsBridge, repo: PlaylistRepository,
        track_repo: TrackRepository, tmp_path: Path,
    ) -> None:
        playlist = repo.create("Bìa hỏng")
        stored = track_repo.add(make_track(title="Bài", source_id="vid8"))
        repo.add_track(playlist.id, stored.id)
        bridge.setPlaylist(playlist.id)
        before = track_repo.get(stored.id).cover_path
        bad = tmp_path / "không phải ảnh.txt"
        bad.write_text("xin chào")

        assert bridge.setCover(stored.id, bad.as_uri()) is False

        assert track_repo.get(stored.id).cover_path == before
