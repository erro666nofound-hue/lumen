"""Listening history for the History view: recent plays grouped by day (design R-1).

Đọc `tracks.last_played_at` — lần nghe CUỐI của mỗi bài, không phải sổ từng
lần nghe (Lumen không giữ sổ đó). Mỗi bài hiện một lần, ở ngày nghe gần nhất.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import date, datetime, timedelta

log = logging.getLogger(__name__)

_WEEKDAYS = ("Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ nhật")


def day_label(day: date, today: date) -> str:
    """Name a day the way the History view heads it: Hôm nay, Hôm qua, Thứ Sáu, 2/10."""
    if day == today:
        return "Hôm nay"
    if day == today - timedelta(days=1):
        return "Hôm qua"
    return f"{_WEEKDAYS[day.weekday()]}, {day.day}/{day.month}"


def recent_days(conn: sqlite3.Connection, limit: int = 60, now: datetime | None = None) -> list[dict]:
    """Return recent plays as [{label, rows: [...]}], newest day and newest play first."""
    try:
        rows = conn.execute(
            "SELECT t.id, COALESCE(NULLIF(t.display_name, ''), t.real_name) AS title, t.artist, "
            "       t.duration_ms, t.cover_path, t.last_played_at, "
            "       (SELECT pi.playlist_id FROM playlist_items pi WHERE pi.track_id = t.id LIMIT 1) AS playlist_id "
            "FROM tracks t WHERE t.last_played_at IS NOT NULL "
            "ORDER BY t.last_played_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    except sqlite3.Error:
        log.exception("Cannot read listening history")
        return []
    today = (now or datetime.now()).date()
    days: list[dict] = []
    for row in rows:
        played = datetime.fromtimestamp(row["last_played_at"])
        label = day_label(played.date(), today)
        if not days or days[-1]["label"] != label:
            days.append({"label": label, "rows": []})
        days[-1]["rows"].append({
            "id": int(row["id"]),
            "title": row["title"] or "",
            "artist": row["artist"] or "",
            "durationMs": int(row["duration_ms"] or 0),
            "coverPath": row["cover_path"] or "",
            "time": played.strftime("%H:%M"),
            "playlistId": int(row["playlist_id"]) if row["playlist_id"] is not None else -1,
        })
    return days
