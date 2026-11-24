"""Mức yêu thích của một nghệ sĩ, suy từ số bài người dùng đã tải.

Tách khỏi discovery.py vì đây là một câu hỏi độc lập — "người này thích ai đến
mức nào" — trả lời được mà không cần biết gì về YouTube, xếp hạng hay mạng.
Không Qt, không sqlite, không gọi mạng.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence



# Hậu tố tên kênh không phải tên nghệ sĩ, khớp ở TẬN CÙNG chuỗi (có thể có
# dấu gạch nối phía trước). Neo ở cuối để không đụng vào gạch nối là một
# phần của tên thật, vd. "Sơn Tùng M-TP" giữ nguyên khi cắt " - Topic".
# Dấu nối danh sách hợp tác của YouTube. Cố ý KHÔNG có "&" và " x ": chúng
# nằm trong tên thật ("Clovis Reyes & VDYCD", "øneheart x reidenshi").
_COLLAB_SPLIT_RE = re.compile(r"\s*,\s*|\s+(?:feat\.|ft\.|featuring)\s+", re.IGNORECASE)

_JUNK_SUFFIX_RE = re.compile(
    r"""
    \s*(?:[-–—]\s*)?
    (?:official\ (?:artist\ channel|music\ video|video|audio|channel)
       |official
       |topic
       |vevo)
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


def primary_artist(raw: str) -> str:
    """Nghệ sĩ CHÍNH trong một danh sách hợp tác.

    YouTube Music trả về cả dàn hợp tác trong một chuỗi:
    "Zachz Winner, springs!, maxwell4k". Đếm nguyên chuỗi thì mỗi lần hợp tác
    khác nhau lại thành một "nghệ sĩ" mới — người dùng tải 6 bài Zachz Winner
    mà app thấy ba nghệ sĩ, mỗi người 1-3 bài, nên không ai đủ ngưỡng và trang
    khám phá không bao giờ bật lên.

    Chỉ cắt ở dấu phẩy và "feat."/"ft.": đó là cách YouTube nối danh sách.
    KHÔNG cắt ở "&" hay " x " — chúng nằm trong tên thật khá nhiều
    ("Clovis Reyes & VDYCD", "øneheart x reidenshi").

    Lấy tên ĐẦU: vai phụ trong một bài hợp tác không nói lên rằng người dùng
    thích người đó.
    """
    return _COLLAB_SPLIT_RE.split(raw, maxsplit=1)[0].strip()


def normalise_artist(raw: str) -> str:
    """Chuẩn hoá tên uploader YouTube thành tên nghệ sĩ để nhóm/đếm.

    Lặp tới khi không còn hậu tố rác nào bị cắt: một kênh tổng hợp có thể
    xếp chồng nhiều hậu tố (vd. "... - Topic - VEVO"), mà mỗi lượt regex chỉ
    ăn được đúng một hậu tố ở tận cùng. Trả về "" nếu cắt hết chẳng còn gì.
    """
    text = re.sub(r"\s+", " ", primary_artist(raw)).strip()
    while text:
        stripped = _JUNK_SUFFIX_RE.sub("", text).strip(" -–—")
        stripped = re.sub(r"\s+", " ", stripped).strip()
        if stripped == text:
            break
        text = stripped
    return text


def top_artists(names: Iterable[str], *, limit: int) -> list[str]:
    """Nghệ sĩ hay gặp nhất trong `names`, đã chuẩn hoá & đếm không phân biệt hoa/thường.

    Hoà tần suất thì xếp theo bảng chữ cái (casefold) — không dựa vào thứ tự
    dict/set thô, vì hash của Python có thể đổi giữa các lần chạy, làm test
    không tất định.
    """
    counts: dict[str, int] = {}
    variants: dict[str, dict[str, int]] = {}
    for raw in names:
        clean = normalise_artist(raw)
        if not clean:
            continue
        key = clean.casefold()
        counts[key] = counts.get(key, 0) + 1
        seen = variants.setdefault(key, {})
        seen[clean] = seen.get(clean, 0) + 1

    def display(key: str) -> str:
        # Dạng hiển thị hay gặp nhất; hoà thì theo bảng chữ cái, cũng để tất định.
        return min(variants[key].items(), key=lambda kv: (-kv[1], kv[0]))[0]

    displays = {key: display(key) for key in counts}
    ordered = sorted(counts, key=lambda key: (-counts[key], displays[key].casefold()))
    return [displays[key] for key in ordered[:limit]]


# Ba mức yêu thích, suy từ SỐ BÀI người dùng đã tải của nghệ sĩ đó. Tải nhiều
# của một người là tín hiệu mạnh hơn hẳn tải đúng một bài -- một bài rất có thể
# chỉ là nghe thoáng qua rồi thôi.
TIER_VERY = "very"       # rất yêu thích: từ 7 bài trở lên
TIER_FAV = "fav"         # yêu thích: 4-6 bài
TIER_NORMAL = "normal"   # bình thường: 1-3 bài

# Số hàng tối đa mỗi mức được lên trang. Cố định, không co giãn theo việc mức
# trên có hay không: trang phải đoán trước được, và mức dưới không được lấn chỗ
# chỉ vì mức trên còn trống.
SHELF_LIMITS = {TIER_VERY: 3, TIER_FAV: 2, TIER_NORMAL: 1}

_TIER_ORDER = (TIER_VERY, TIER_FAV, TIER_NORMAL)


def tier_for(count: int) -> str:
    """Mức yêu thích ứng với số bài đã tải của một nghệ sĩ."""
    if count >= 7:
        return TIER_VERY
    if count >= 4:
        return TIER_FAV
    return TIER_NORMAL


@dataclass(frozen=True, slots=True)
class ArtistTier:
    """Một nghệ sĩ, kèm số bài đã tải và mức yêu thích.

    `rated` là đánh giá người dùng đặt tay (None = chưa đánh giá). Có đánh giá
    thì nó THẮNG phép đoán theo số bài: người dùng nói thẳng bao giờ cũng đúng
    hơn app suy từ số lần tải.
    """

    artist: str
    count: int
    rated: str | None = None

    @property
    def tier(self) -> str:
        return self.rated if self.rated is not None else tier_for(self.count)


def artist_tiers(
    names: Iterable[str], ratings: Mapping[str, str | None] | None = None
) -> list[ArtistTier]:
    """Đếm số bài mỗi nghệ sĩ rồi xếp giảm dần. Cùng phép chuẩn hoá như top_artists.

    `ratings` ánh xạ tên (đã chuẩn hoá) -> mức người dùng đặt tay, hoặc None cho
    nghệ sĩ bị CHẶN. Nghệ sĩ bị chặn bị loại hẳn khỏi kết quả.

    Nghệ sĩ có đánh giá nhưng CHƯA tải bài nào vẫn được đưa vào với count = 0 —
    người dùng có thể thêm một kênh rồi mới nghe, không phải ngược lại.
    """
    counts: dict[str, int] = {}
    variants: dict[str, dict[str, int]] = {}
    for raw in names:
        clean = normalise_artist(raw)
        if not clean:
            continue
        key = clean.casefold()
        counts[key] = counts.get(key, 0) + 1
        seen = variants.setdefault(key, {})
        seen[clean] = seen.get(clean, 0) + 1

    def display(key: str) -> str:
        return min(variants[key].items(), key=lambda kv: (-kv[1], kv[0]))[0]

    given = dict(ratings or {})
    # Nghệ sĩ được đánh giá nhưng chưa có bài nào: vẫn phải lên trang.
    for name in given:
        key = name.casefold()
        counts.setdefault(key, 0)
        variants.setdefault(key, {name: 1})

    displays = {key: display(key) for key in counts}
    ordered = sorted(counts, key=lambda key: (-counts[key], displays[key].casefold()))

    rated_by_key = {name.casefold(): tier for name, tier in given.items()}
    result: list[ArtistTier] = []
    for key in ordered:
        if key in rated_by_key and rated_by_key[key] is None:
            continue                       # bị chặn: không bao giờ đề xuất
        result.append(ArtistTier(
            artist=displays[key], count=counts[key], rated=rated_by_key.get(key)
        ))
    return result


def select_shelves(tiers: Sequence[ArtistTier]) -> list[ArtistTier]:
    """Chọn nghệ sĩ lên trang: tối đa 3 rất-yêu-thích, 2 yêu-thích, 1 bình-thường.

    Trả về đã xếp theo mức, nên khi chưa có mức "rất yêu thích" thì "yêu thích"
    tự lên đầu — không cần nhánh riêng cho trường hợp đó.
    """
    chosen: list[ArtistTier] = []
    for tier in _TIER_ORDER:
        matching = [t for t in tiers if t.tier == tier]
        chosen.extend(matching[: SHELF_LIMITS[tier]])
    return chosen
