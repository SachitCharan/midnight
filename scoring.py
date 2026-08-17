"""Composite stargazing scoring model."""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from astronomy import is_astronomical_darkness, moon_altitude, moon_illumination
from light_pollution import darkness_score

WEIGHTS = {
    "cloud_cover": 0.40,
    "light_pollution": 0.30,
    "moon": 0.20,
    "atmosphere": 0.10,
}


def normalize_hourly_data(hourly_data: list[dict]) -> list[dict]:
    """Sort ascending and keep the first row for each timezone-aware timestamp."""
    normalized = []
    seen = set()
    for row in sorted(hourly_data, key=lambda item: item["time"]):
        when = row["time"]
        if when.tzinfo is None:
            raise ValueError("Hourly forecast timestamps must be timezone-aware")
        if when in seen:
            continue
        seen.add(when)
        normalized.append(row)
    return normalized


def build_score_timeline(hourly_data: list[dict], lat: float, lon: float) -> list[dict]:
    """Return one point per hour, using NaN to break the line during daylight."""
    timeline = []
    segment = 0
    was_dark = False
    for hour in normalize_hourly_data(hourly_data):
        when = hour["time"]
        score = float("nan")
        dark = is_astronomical_darkness(when, lat, lon)
        if dark:
            if not was_dark:
                segment += 1
            score, _ = compute_stargazing_score(
                hour.get("cloud_cover", 0), hour["brightness_index"], moon_illumination(when),
                moon_altitude(when, lat, lon), hour.get("visibility", 20000),
                hour.get("relative_humidity_2m", 50),
            )
        timeline.append({"time": when, "score": score, "segment": segment if dark else None})
        was_dark = dark
    return timeline


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def compute_stargazing_score(
    cloud_pct: float,
    brightness_index: float,
    moon_illum: float,
    moon_alt: float,
    visibility_m: float,
    humidity_pct: float,
    *,
    dt_utc: datetime | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> tuple[float | None, dict]:
    if dt_utc is not None and lat is not None and lon is not None:
        if not is_astronomical_darkness(dt_utc, lat, lon):
            return None, {"state": "not dark yet"}

    cloud = _clamp(100.0 - cloud_pct)
    light = darkness_score(brightness_index)
    if moon_alt < 0:
        moon = 100.0
    else:
        altitude_factor = min(1.0, moon_alt / 90.0)
        moon = _clamp(100.0 - moon_illum * 100.0 * altitude_factor)
    visibility_score = _clamp(visibility_m / 20000.0 * 100.0)
    humidity_score = _clamp(100.0 - max(0.0, humidity_pct - 40.0) / 60.0 * 100.0)
    atmosphere = (visibility_score + humidity_score) / 2.0
    subscores = {
        "cloud_cover": round(cloud, 1),
        "light_pollution": round(light, 1),
        "moon": round(moon, 1),
        "atmosphere": round(atmosphere, 1),
    }
    composite = sum(subscores[factor] * weight for factor, weight in WEIGHTS.items())
    return round(composite, 1), subscores


def score_label(score: float) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "Good"
    if score >= 50:
        return "Fair"
    if score >= 30:
        return "Poor"
    return "Don't bother"


def limiting_factor(subscores: dict) -> str:
    labels = {
        "cloud_cover": "Cloud cover",
        "light_pollution": "Light pollution",
        "moon": "Moonlight",
        "atmosphere": "Atmospheric conditions",
    }
    factor = max(
        (key for key in WEIGHTS if key in subscores),
        key=lambda key: (100.0 - subscores[key]) * WEIGHTS[key],
    )
    return f"{labels[factor]} is the biggest limitation tonight."


def find_best_window(hourly_data: list[dict], lat: float, lon: float) -> dict:
    scored = []
    for hour in hourly_data:
        when = hour["time"]
        if not is_astronomical_darkness(when, lat, lon):
            continue
        score, subscores = compute_stargazing_score(
            hour.get("cloud_cover", 0),
            hour["brightness_index"],
            moon_illumination(when),
            moon_altitude(when, lat, lon),
            hour.get("visibility", 20000),
            hour.get("relative_humidity_2m", 50),
        )
        scored.append({"time": when, "score": score, "subscores": subscores})
    if not scored:
        return {}
    # This function's contract is tonight, not the strongest hour anywhere in
    # the multi-day forecast. Keep only the first contiguous upcoming dark run.
    tonight = [scored[0]]
    for item in scored[1:]:
        if (item["time"] - tonight[-1]["time"]).total_seconds() > 5400:
            break
        tonight.append(item)
    scored = tonight
    best_score = max(item["score"] for item in scored)
    threshold = max(0.0, best_score - 5.0)
    best_index = max(range(len(scored)), key=lambda index: scored[index]["score"])
    start = end = best_index
    while (
        start > 0
        and scored[start - 1]["score"] >= threshold
        and (scored[start]["time"] - scored[start - 1]["time"]).total_seconds() <= 5400
    ):
        start -= 1
    while (
        end + 1 < len(scored)
        and scored[end + 1]["score"] >= threshold
        and (scored[end + 1]["time"] - scored[end]["time"]).total_seconds() <= 5400
    ):
        end += 1
    return {
        "start": scored[start]["time"],
        "end": scored[end]["time"],
        "best_score": best_score,
        "hours": scored[start : end + 1],
        "all_hours": scored,
    }


def summarize_nights(hourly_data: list[dict], lat: float, lon: float, timezone_name: str = "UTC") -> list[dict]:
    """Return the best dark hour for each observing night in the forecast."""
    try:
        local_zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        local_zone = timezone.utc
    nights: dict = {}
    for hour in hourly_data:
        when = hour["time"]
        if not is_astronomical_darkness(when, lat, lon):
            continue
        score, subscores = compute_stargazing_score(
            hour.get("cloud_cover", 0), hour["brightness_index"], moon_illumination(when),
            moon_altitude(when, lat, lon), hour.get("visibility", 20000),
            hour.get("relative_humidity_2m", 50),
        )
        local_time = when.astimezone(local_zone)
        observing_date = (local_time - timedelta(hours=12)).date()
        candidate = {"date": observing_date, "time": when, "score": score, "subscores": subscores}
        if observing_date not in nights or score > nights[observing_date]["score"]:
            nights[observing_date] = candidate
    return [nights[key] for key in sorted(nights)]
