"""Row-identity SQL fragments shared by the local library (public build: no snapshot/upload).

Bản public của Lumen KHÔNG có đồng bộ: phần chụp ảnh thư viện để đẩy lên máy chủ
(`build_snapshot`) đã bị gỡ. File này chỉ còn những mảnh SQL mà thư viện trên máy
vẫn dùng để hỏi "dòng này có link YouTube không / có danh tính bền không".
"""
from __future__ import annotations

from typing import Any

# HAI câu hỏi, một thời từng bị hỏi bằng MỘT mảnh SQL (`HAS_SOURCE`, tới QĐ-027):
#
#   HAS_LINK     — "tải lại được từ link YouTube không?"
#   HAS_IDENTITY — "bản kê gọi tên được dòng này không?"  → được vào ảnh chụp
#
# Bài YouTube trả lời CÓ cho cả hai, nên suốt F-5a′ không ai thấy đó là hai câu.
# Bài nhập từ đĩa tách chúng ra: có `content_hash` thì bản kê gọi tên được nó
# (khoá kho R2 = sha256 của chính file) nhưng KHÔNG có link nào để tải lại —
# mất file thì kéo về từ kho, không phải tải lại từ YouTube.
#
# *Hình dung:* cuốn băng chép tay có mảnh giấy dán bên hông nên kho gửi đồ trả
# đúng cuốn — nhưng ngoài hiệu không ai bán lại nó cho bạn.
#
# Mỗi chỗ hỏi phải chọn ĐÚNG câu nó định hỏi. Chọn nhầm `HAS_LINK` ở chỗ đáng lẽ
# hỏi `HAS_IDENTITY` là bài custom rơi khỏi bản kê mà không ai báo. `tracks` phải
# mang bí danh `t`.
HAS_LINK = "t.source_id IS NOT NULL AND t.source_id != ''"
NO_LINK = "(t.source_id IS NULL OR t.source_id = '')"
HAS_IDENTITY = (
    "(t.source_id IS NOT NULL AND t.source_id != '' "
    "OR t.content_hash IS NOT NULL AND t.content_hash != '')"
)
NO_IDENTITY = (
    "((t.source_id IS NULL OR t.source_id = '') "
    "AND (t.content_hash IS NULL OR t.content_hash = ''))"
)

# Khoá của một dòng trong ảnh chụp: mã video nếu có, không thì hash của file.
# Hai họ khoá không bao giờ đụng nhau — mã video 11 ký tự, sha256 64 ký tự hex.
IDENTITY_KEY = "COALESCE(NULLIF(t.source_id, ''), NULLIF(t.content_hash, ''))"


def item_name(item: dict[str, Any]) -> tuple[int, str]:
    """Read one item's owner-given name as (stamp, name); a missing one is (0, "").

    Vắng khoá KHÔNG phải là "xoá tên". Máy chưa biết tính năng này đẩy lên bản kê
    không có hai khoá đó, và đọc thành mốc 0 là thứ giữ cho một vòng hoà đi qua
    nó không xoá mất tên của ai (QĐ-021).
    """
    return int(item.get("display_name_updated_at", 0)), str(item.get("display_name", ""))
