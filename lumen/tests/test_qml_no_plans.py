"""QĐ-041: Lumen là máy nghe nhạc riêng của bro — giao diện không còn gói, khoá hay lời mời nâng cấp.

Hàng rào này canh cho phần QML gói/thanh toán (F-4 Gate, PlanSheet…) không mọc lại:
một khoá còn sót là một thẻ Cài đặt mờ đi hay một chip bấm vào chẳng làm gì.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "lumen"
UI = SRC / "ui"

#: Bốn file bảng gói / khoá của F-4, và hàng nghệ sĩ chỉ phần Free dùng.
_GONE = ("PlanSheet.qml", "PlanCard.qml", "UpgradeInvite.qml", "LockVeil.qml", "TopArtistsRow.qml")

#: Chữ trong QML nghĩa là còn một chỗ hỏi gói.
_PLAN_WORDS = re.compile(
    r"\bGate\b|planSheet|PlanSheet|PlanCard|UpgradeInvite|LockVeil|upgradeRequested"
    r"|Account\.plan|minimumPlan|\blocked\b|lockedOpacity|Mở khoá với"
)


def _qml_files() -> list[Path]:
    return sorted(UI.rglob("*.qml"))


def test_co_file_qml_de_kiem() -> None:
    """Chốt cho chính test này: đọc nhầm thư mục thì mọi khẳng định dưới vô nghĩa."""
    assert len(_qml_files()) > 20


def test_file_goi_da_xoa() -> None:
    con = sorted(p.name for p in _qml_files() if p.name in _GONE)
    assert not con, f"file QML của gói vẫn còn: {con}"


def test_khong_qml_nao_hoi_goi() -> None:
    found = {
        f"{path.relative_to(UI)}:{n}": line.strip()
        for path in _qml_files()
        for n, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1)
        if _PLAN_WORDS.search(line)
    }
    assert not found, f"QML vẫn còn chỗ hỏi gói / khoá: {found}"


def test_khong_nhac_gia_hay_nang_cap_tren_giao_dien() -> None:
    """Chữ người dùng đọc được: không rao gói nào."""
    loi = re.compile(r'"[^"\n]*(Nâng cấp|gói (Free|Pro|Max)|Gói (Free|Pro|Max)|chưa mở bán)[^"\n]*"')
    found = {
        path.name: m.group(0)
        for path in _qml_files()
        if (m := loi.search(path.read_text(encoding="utf-8")))
    }
    assert not found, f"giao diện vẫn nhắc gói: {found}"


def test_kham_pha_chi_mot_cua_goi_mang() -> None:
    """Mỗi nghệ sĩ ~1.4s mạng: hai chỗ gọi là sớm muộn có một chỗ gọi thừa."""
    code = (UI / "views" / "LibraryView.qml").read_text(encoding="utf-8")
    assert code.count("Discovery.refresh(") == 1
