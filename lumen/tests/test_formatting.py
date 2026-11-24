from __future__ import annotations

import pytest

from lumen.core.formatting import format_duration, format_relative_date


@pytest.mark.parametrize(
    ("ms", "expected"),
    [
        (0, "0:00"),
        (-5, "0:00"),
        (999, "0:00"),
        (1000, "0:01"),
        (61_000, "1:01"),
        (201_000, "3:21"),
        (3_599_000, "59:59"),
        (3_600_000, "1:00:00"),
        (4_925_000, "1:22:05"),
    ],
)
def test_format_duration(ms: int, expected: str) -> None:
    assert format_duration(ms) == expected


@pytest.mark.parametrize(
    ("delta_seconds", "expected"),
    [
        (0, "Vừa xong"),
        (30, "Vừa xong"),
        (60, "1 phút trước"),
        (3_540, "59 phút trước"),
        (3_600, "1 giờ trước"),
        (86_399, "23 giờ trước"),
        (86_400, "Hôm qua"),
        (172_800, "2 ngày trước"),
        (2_592_000, "1 tháng trước"),
        (31_536_000, "1 năm trước"),
    ],
)
def test_format_relative_date(delta_seconds: int, expected: str) -> None:
    now = 1_800_000_000
    assert format_relative_date(now - delta_seconds, now=now) == expected


def test_format_relative_date_handles_missing_and_future_timestamps() -> None:
    now = 1_800_000_000
    assert format_relative_date(0, now=now) == ""
    assert format_relative_date(now + 5_000, now=now) == "Vừa xong"
