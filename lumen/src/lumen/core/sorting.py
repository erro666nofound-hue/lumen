"""Sắp xếp các bài trong một track.

Thuần Python, không Qt, không SQL — nên chạy được bằng pytest mà không mở cửa
sổ nào. Bridge chỉ gọi xuống đây chứ không tự so sánh.
"""

from __future__ import annotations

from lumen.core.models import Track

#: Thứ tự người dùng tự đặt (cột `position` trong playlist_items). Đây là thứ
#: tự nhiên nhất của một track nên nó là mặc định, và là thứ tự DUY NHẤT cho
#: phép kéo thả đổi chỗ.
SORT_CUSTOM = "custom"
SORT_TITLE = "title"
SORT_ARTIST = "artist"
SORT_DURATION = "duration"
SORT_ADDED = "added"

SORT_KEYS = (SORT_CUSTOM, SORT_TITLE, SORT_ARTIST, SORT_DURATION, SORT_ADDED)

#: Nhãn tiếng Việt cho từng tiêu chí, để giao diện khỏi tự bịa mỗi nơi một kiểu.
SORT_LABELS = {
    SORT_CUSTOM: "Thứ tự của bạn",
    SORT_TITLE: "Tên",
    SORT_ARTIST: "Nghệ sĩ",
    SORT_DURATION: "Thời lượng",
    SORT_ADDED: "Mới thêm",
}


def is_valid(key: str) -> bool:
    """Report whether this is a sort key the application knows."""
    return key in SORT_KEYS


def _text(value: str) -> str:
    """Fold a title/artist for comparison: 'ABBA' and 'abba' must sit together."""
    return (value or "").strip().casefold()


#: Khoá so sánh cho từng tiêu chí. Tên bài luôn là khoá PHỤ: hai bài cùng thời
#: lượng mà nhảy chỗ mỗi lần sắp lại thì nhìn như app bị lỗi.
_RANKERS = {
    SORT_TITLE: lambda track: (_text(track.title),),
    # `artist_label`, không phải `artist`: xếp theo một chữ khác với chữ đang
    # hiện ra là người dùng thấy danh sách nhảy lung tung không lý do.
    SORT_ARTIST: lambda track: (_text(track.artist_label), _text(track.title)),
    SORT_DURATION: lambda track: (track.duration_ms, _text(track.title)),
    SORT_ADDED: lambda track: (track.added_at, _text(track.title)),
}


def sort_tracks(tracks: list[Track], key: str, *, descending: bool = False) -> list[Track]:
    """Return a new list ordered by `key`; unknown keys leave the order alone.

    Thứ tự đến đây ĐÃ là thứ tự người dùng tự đặt (SQL trả về theo `position`),
    nên SORT_CUSTOM chỉ việc giữ nguyên — và đảo lại khi được yêu cầu.
    """
    ranker = _RANKERS.get(key)
    if ranker is None:
        return list(reversed(tracks)) if descending else list(tracks)
    return sorted(tracks, key=ranker, reverse=descending)
