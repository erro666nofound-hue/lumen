"""Dùng `QQC.` thì phải import `QtQuick.Controls as QQC`.

Đã xảy ra thật ở HistoryList.qml: thiếu import nên `closePolicy` ném
ReferenceError lúc chạy, và bảng chi tiết "Nhạc của tôi" tự đóng khi bảng chọn
track hiện lên. qmllint KHÔNG bắt được, chỉ nạp QML thật mới lộ — nên phải có
test đọc mã nguồn.
"""

from __future__ import annotations

import re
from pathlib import Path

UI = Path(__file__).resolve().parent.parent / "src" / "lumen" / "ui"
CONTROLS_IMPORT = "import QtQuick.Controls as QQC"


def _qml_files() -> list[Path]:
    return sorted(UI.rglob("*.qml"))


def _uses_controls(text: str) -> bool:
    """Có dùng QQC. ở CHỖ THẬT không (bỏ qua chú thích)."""
    code = re.sub(r"//.*", "", text)
    return bool(re.search(r"\bQQC\.", code))


def test_there_are_qml_files_to_check() -> None:
    assert len(_qml_files()) > 20


def test_every_file_using_qqc_imports_it() -> None:
    missing = [
        path.name
        for path in _qml_files()
        if _uses_controls(path.read_text(encoding="utf-8"))
        and CONTROLS_IMPORT not in path.read_text(encoding="utf-8")
    ]

    assert not missing, f"dùng QQC. mà không import: {missing}"


def test_nobody_imports_controls_without_the_namespace() -> None:
    """`import QtQuick.Controls` trần thay SearchField của dự án bằng kiểu cùng tên của Qt.

    Đây là bug đã làm app không mở được một lần — xem CLAUDE.md mục 5.
    """
    bare = [
        path.name
        for path in _qml_files()
        if re.search(r"^import QtQuick\.Controls\s*$", path.read_text(encoding="utf-8"), re.M)
    ]

    assert not bare, f"import QtQuick.Controls trần (phải có 'as QQC'): {bare}"


#: `Item` có sẵn năm đường neo này, và chúng là FINAL. Đặt trùng tên một cái là
#: QML không nạp nổi file đó -- kéo theo CẢ APP không mở được. Đã dính thật với
#: `readonly property var top:` trong LibraryView (CB-020).
ANCHOR_LINE_NAMES = ("top", "bottom", "left", "right", "baseline")

_DECLARE_RE = re.compile(
    r"^\s*(?:readonly\s+|required\s+|default\s+)*property\s+\w+\s+(\w+)\s*:", re.M
)


def test_khong_ai_dat_ten_thuoc_tinh_trung_duong_neo() -> None:
    """Lỗi này KHÔNG âm thầm -- nó làm app không mở được, nên phải bắt sớm.

    Năm cái tên này là thứ người ta với tay lấy rất tự nhiên ("top" cho danh
    sách đầu bảng), mà thông báo lỗi thì chỉ nói "Cannot override FINAL
    property" kèm số dòng, không nói tên nào đâm vào tên nào.
    """
    clashes = {
        path.name: names
        for path in _qml_files()
        if (names := [
            name
            for name in _DECLARE_RE.findall(path.read_text(encoding="utf-8"))
            if name in ANCHOR_LINE_NAMES
        ])
    }

    assert not clashes, f"trùng tên đường neo FINAL của Item, app sẽ không mở được: {clashes}"
