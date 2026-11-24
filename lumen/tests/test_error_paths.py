"""Mọi lỗi bridge phát ra đều phải tới được mắt người dùng.

Đã xảy ra thật: `Search.errorOccurred` và `Artists.errorOccurred` được phát ra
nhưng KHÔNG ai nghe — tìm nhạc lúc mạng chết thì danh sách rỗng và không một lời
giải thích. Không có test thì loại lỗi này quay lại lúc nào không hay: thêm một
bridge mới, quên nối, và mọi thứ vẫn "chạy bình thường".
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

SRC = Path(__file__).resolve().parent.parent / "src" / "lumen"
APP = SRC / "app.py"
MAIN_QML = SRC / "ui" / "Main.qml"


def _classes_that_report_errors() -> set[str]:
    """Tên các lớp bridge có khai báo `errorOccurred`."""
    found: set[str] = set()
    for path in (SRC / "bridge").glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"^class (\w+)\(", text, re.M):
            body = text[match.end() :]
            nxt = re.search(r"^class \w+\(", body, re.M)
            if "errorOccurred = Signal" in (body[: nxt.start()] if nxt else body):
                found.add(match.group(1))
    return found


def _qml_names_by_class() -> dict[str, str]:
    """Tên dùng trong QML -> lớp bridge đứng sau nó, đọc từ app.py."""
    text = APP.read_text(encoding="utf-8")
    var_class = dict(re.findall(r"^\s*(\w+) = (\w+Bridge)\(", text, re.M))
    names: dict[str, str] = {}
    for qml_name, expr in re.findall(r'setContextProperty\("(\w+)",\s*([\w()]+)\)', text):
        cls = var_class.get(expr) or (expr[:-2] if expr.endswith("()") else None)
        if cls:
            names[qml_name] = cls
    return names


def _qml_names_listening_for_errors() -> set[str]:
    """Ai đang nghe lỗi, đọc từ MỌI file QML.

    Cắt theo từng `Connections {` rồi lấy tới cái kế tiếp, KHÔNG dùng regex bắt
    cả khối: khối trước có dấu ngoặc lồng sẽ nuốt luôn khối sau, và bản đầu của
    test này đã báo nhầm đúng vì thế.
    """
    listening: set[str] = set()
    for path in (SRC / "ui").rglob("*.qml"):
        chunks = path.read_text(encoding="utf-8").split("Connections {")[1:]
        for chunk in chunks:
            body = chunk.split("Connections {")[0]
            target = re.search(r"target:\s*(\w+)", body)
            if target and "onErrorOccurred" in body:
                listening.add(target.group(1))
    return listening


def test_the_audit_can_see_the_bridges() -> None:
    """Chốt chặn cho chính test này: đọc hỏng thì mọi khẳng định dưới thành vô nghĩa."""
    assert len(_classes_that_report_errors()) >= 5
    assert len(_qml_names_by_class()) >= 8


def test_every_error_a_bridge_reports_is_shown_to_someone() -> None:
    reporting = _classes_that_report_errors()
    listening = _qml_names_listening_for_errors()

    unheard = sorted(
        qml_name
        for qml_name, cls in _qml_names_by_class().items()
        if cls in reporting and qml_name not in listening
    )

    assert not unheard, f"lỗi của {unheard} phát ra mà không ai nghe"
