"""Rank real populated-place dark-sky candidates without new API calls."""

from __future__ import annotations

import math

from light_pollution import artificial_brightness, bortle_class, darkness_score

EARTH_RADIUS_KM = 6371.0


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def find_dark_sites(
    lat: float,
    lon: float,
    population_centers: list,
    max_distance_km: float = 100,
    top_n: int = 8,
    sort_by: str = "Best balance",
) -> list[dict]:
    """Return named populated places ranked by darkness and travel distance."""
    if max_distance_km <= 0 or top_n <= 0:
        return []
    candidates = []
    seen = set()
    for place in population_centers:
        if place.get("feature_class", "P") != "P":
            continue
        try:
            candidate_lat = float(place["lat"])
            candidate_lon = float(place["lon"])
            name = str(place["name"]).strip()
        except (KeyError, TypeError, ValueError):
            continue
        identity = (name.casefold(), round(candidate_lat, 5), round(candidate_lon, 5))
        if not name or identity in seen:
            continue
        seen.add(identity)
        distance = distance_km(lat, lon, candidate_lat, candidate_lon)
        if distance < 5 or distance > max_distance_km:
            continue
        brightness = artificial_brightness(candidate_lat, candidate_lon, population_centers)
        dark_score = darkness_score(brightness)
        candidates.append({
            "name": name,
            "lat": round(candidate_lat, 5),
            "lon": round(candidate_lon, 5),
            "distance_km": round(distance, 1),
            "brightness_index": brightness,
            "darkness_score": dark_score,
            "bortle": bortle_class(brightness),
            "usefulness_score": round(dark_score - 0.04 * distance, 1),
            "kind": "GeoNames populated place",
        })

    if sort_by == "Darkest sky":
        candidates.sort(key=lambda item: (-item["darkness_score"], item["distance_km"], item["name"]))
    elif sort_by == "Shortest trip":
        candidates.sort(key=lambda item: (item["distance_km"], -item["darkness_score"], item["name"]))
    else:
        candidates.sort(key=lambda item: (-item["usefulness_score"], -item["darkness_score"], item["distance_km"], item["name"]))
    return candidates[:top_n]
