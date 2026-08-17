"""Static calendar for major annual meteor showers."""

from __future__ import annotations

from datetime import date, datetime, timedelta

SHOWERS = [
    {"name": "Quadrantids", "start": (12, 28), "end": (1, 12), "peak": (1, 3), "zhr": 120},
    {"name": "Lyrids", "start": (4, 14), "end": (4, 30), "peak": (4, 22), "zhr": 18},
    {"name": "Eta Aquariids", "start": (4, 19), "end": (5, 28), "peak": (5, 6), "zhr": 50},
    {"name": "Southern Delta Aquariids", "start": (7, 18), "end": (8, 21), "peak": (7, 30), "zhr": 25},
    {"name": "Perseids", "start": (7, 17), "end": (8, 24), "peak": (8, 12), "zhr": 100},
    {"name": "Orionids", "start": (10, 2), "end": (11, 7), "peak": (10, 21), "zhr": 20},
    {"name": "Leonids", "start": (11, 3), "end": (12, 2), "peak": (11, 17), "zhr": 15},
    {"name": "Geminids", "start": (11, 19), "end": (12, 24), "peak": (12, 14), "zhr": 120},
]


def _window_for_year(shower: dict, year: int) -> tuple[date, date, date]:
    start = date(year, *shower["start"])
    end_year = year + 1 if shower["end"] < shower["start"] else year
    peak_year = year + 1 if shower["peak"] < shower["start"] else year
    return start, date(end_year, *shower["end"]), date(peak_year, *shower["peak"])


def meteor_activity(when: datetime | date, upcoming_days: int = 45) -> dict:
    today = when.date() if isinstance(when, datetime) else when
    active = []
    peaks = []
    for shower in SHOWERS:
        for base_year in (today.year - 1, today.year, today.year + 1):
            start, end, peak = _window_for_year(shower, base_year)
            if start <= today <= end:
                active.append(shower | {"peak_date": peak})
            if today <= peak <= today + timedelta(days=upcoming_days):
                peaks.append(shower | {"peak_date": peak, "days_until": (peak - today).days})
    active = list({item["name"]: item for item in active}.values())
    peaks = sorted({item["name"]: item for item in peaks}.values(), key=lambda item: item["peak_date"])
    return {"active": active, "upcoming": peaks}
