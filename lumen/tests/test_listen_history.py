"""Tests for the listening history grouped by day."""

from __future__ import annotations

from datetime import date, datetime

from lumen.core import db
from lumen.core.listen_history import day_label, recent_days
from tests.conftest import make_track
from lumen.core.repository import TrackRepository


def test_day_labels() -> None:
    today = date(2026, 10, 5)
    assert day_label(today, today) == "Hôm nay"
    assert day_label(date(2026, 10, 4), today) == "Hôm qua"
    assert day_label(date(2026, 10, 2), today) == "Thứ Sáu, 2/10"


def test_recent_days_groups_newest_first(tmp_path) -> None:
    conn = db.connect(tmp_path / "library.db")
    repo = TrackRepository(conn)
    a = repo.add(make_track())
    b = repo.add(make_track())
    c = repo.add(make_track())
    stamps = {a.id: datetime(2026, 10, 5, 9, 0), b.id: datetime(2026, 10, 5, 18, 40), c.id: datetime(2026, 10, 2, 8, 0)}
    for tid, when in stamps.items():
        conn.execute("UPDATE tracks SET last_played_at = ? WHERE id = ?", (int(when.timestamp()), tid))
    conn.commit()
    days = recent_days(conn, now=datetime(2026, 10, 5, 20, 0))
    assert [d["label"] for d in days] == ["Hôm nay", "Thứ Sáu, 2/10"]
    assert [r["id"] for r in days[0]["rows"]] == [b.id, a.id]
    assert days[0]["rows"][0]["time"] == "18:40"
