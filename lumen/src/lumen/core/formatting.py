"""Pure display formatting helpers.

Lives in core (not in a bridge) so the rules are testable without Qt and stay
identical everywhere: the library table, the player bar and the future mini
window must never disagree about how long a track is.
"""

from __future__ import annotations

import time


def format_duration(duration_ms: int) -> str:
    """Format a millisecond duration as m:ss, or h:mm:ss past an hour."""
    if duration_ms <= 0:
        return "0:00"
    total_seconds = duration_ms // 1000
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def format_relative_date(timestamp: int, *, now: int | None = None) -> str:
    """Format a unix timestamp as a short Vietnamese relative date."""
    if timestamp <= 0:
        return ""
    current = int(time.time()) if now is None else now
    delta = current - timestamp
    if delta < 0:
        return "Vừa xong"
    if delta < 60:
        return "Vừa xong"
    if delta < 3600:
        return f"{delta // 60} phút trước"
    if delta < 86400:
        return f"{delta // 3600} giờ trước"
    days = delta // 86400
    if days == 1:
        return "Hôm qua"
    if days < 30:
        return f"{days} ngày trước"
    if days < 365:
        return f"{days // 30} tháng trước"
    return f"{days // 365} năm trước"
