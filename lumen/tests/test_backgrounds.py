"""Nền của Lumen: ảnh đã chọn và các dải màu dựng sẵn."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lumen.core import backgrounds  # noqa: E402


class TestTellingImagesApart:
    def test_a_missing_file_is_not_a_usable_image(self, tmp_path: Path) -> None:
        assert not backgrounds.is_image(str(tmp_path / "khong-ton-tai.png"))

    def test_a_real_file_is(self, tmp_path: Path) -> None:
        image = tmp_path / "anh.png"
        image.write_bytes(b"x")

        assert backgrounds.is_image(str(image))

    def test_nothing_chosen_is_not_an_image(self) -> None:
        assert not backgrounds.is_image("")


class TestCleaningWhatTheDialogReturns:
    def test_the_file_url_prefix_is_stripped(self) -> None:
        assert backgrounds.clean_path("file:///home/ai/anh.png") == "/home/ai/anh.png"

    def test_a_plain_path_is_left_alone(self) -> None:
        assert backgrounds.clean_path("/home/ai/anh.png") == "/home/ai/anh.png"


class TestRemembering:
    def test_existing_tiles_never_move(self) -> None:
        """Ô đang bày ra mà nhảy chỗ mỗi lần bấm thì lần sau tìm lại rất khó."""
        after = backgrounds.remember(["/a.png", "/b.png"], "/a.png")

        assert after == ["/a.png", "/b.png"]

    def test_a_new_one_joins_the_end(self) -> None:
        after = backgrounds.remember(["/a.png"], "/b.png")

        assert after == ["/a.png", "/b.png"]

    def test_clearing_the_background_does_not_enter_the_list(self) -> None:
        after = backgrounds.remember(["/a.png"], "")

        assert after == ["/a.png"]

    def test_the_list_stops_growing(self) -> None:
        history: list[str] = []
        for index in range(backgrounds.MAX_REMEMBERED + 5):
            history = backgrounds.remember(history, f"/anh-{index}.png")

        assert len(history) == backgrounds.MAX_REMEMBERED

    def test_deleted_files_drop_out(self, tmp_path: Path) -> None:
        """Ảnh đã bị xoá mà vẫn hiện trong bảng chọn thì bấm vào là nền trống trơn."""
        alive = tmp_path / "con.png"
        alive.write_bytes(b"x")

        assert backgrounds.surviving([str(alive), str(tmp_path / "mat.png")]) == [str(alive)]


class TestKeepingACopy:
    """Nhớ đường dẫn gốc thôi thì người dùng dọn thư mục là ảnh biến mất."""

    def test_the_image_is_copied_into_lumens_own_folder(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
        source = tmp_path / "anh.png"
        source.write_bytes(b"noi dung anh")

        kept = backgrounds.store(str(source))

        assert Path(kept).is_file()
        assert Path(kept).parent == backgrounds.store_dir()

    def test_the_copy_survives_the_original_being_deleted(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
        source = tmp_path / "anh.png"
        source.write_bytes(b"noi dung anh")
        kept = backgrounds.store(str(source))

        source.unlink()

        assert backgrounds.is_image(kept)

    def test_choosing_the_same_image_twice_keeps_one_copy(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
        source = tmp_path / "anh.png"
        source.write_bytes(b"noi dung anh")

        first = backgrounds.store(str(source))
        second = backgrounds.store(str(source))

        assert first == second
        assert len(list(backgrounds.store_dir().iterdir())) == 1

    def test_an_image_already_in_the_store_is_left_alone(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
        source = tmp_path / "anh.png"
        source.write_bytes(b"noi dung anh")
        kept = backgrounds.store(str(source))

        assert backgrounds.store(kept) == kept

    def test_the_copy_keeps_the_original_name(self, tmp_path, monkeypatch) -> None:
        """Tên băm thuần thì bảng chọn hiện một chuỗi vô nghĩa."""
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
        source = tmp_path / "luna.png"
        source.write_bytes(b"noi dung anh")

        kept = Path(backgrounds.store(str(source)))

        assert kept.stem.startswith("luna-")
        assert len(kept.stem) == len("luna-") + backgrounds.FINGERPRINT_LEN

    def test_a_missing_file_gives_nothing(self, tmp_path) -> None:
        assert backgrounds.store(str(tmp_path / "khong-co.png")) == ""
