"""Display-unit helpers; scientific models continue to use metric internally."""

from __future__ import annotations

KM_PER_MILE = 1.609344


def default_unit_system(country_code: str | None) -> str:
    return "Imperial (mi)" if (country_code or "").upper() == "US" else "Metric (km)"


def distance_to_km(value: float, unit_system: str) -> float:
    return float(value) * KM_PER_MILE if unit_system == "Imperial (mi)" else float(value)


def format_distance(distance_km: float, unit_system: str, decimals: int = 1) -> str:
    if unit_system == "Imperial (mi)":
        return f"{distance_km / KM_PER_MILE:.{decimals}f} mi"
    return f"{distance_km:.{decimals}f} km"
