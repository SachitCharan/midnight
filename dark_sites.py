"""Rank modeled dark-sky candidates around an observer without new API calls."""

from __future__ import annotations

import math

import numpy as np

from data_sources import OREGON_DARK_SKY_LANDMARKS
from light_pollution import artificial_brightness, bortle_class, darkness_score

EARTH_RADIUS_KM = 6371.0


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _candidate_name(lat: float, lon: float) -> tuple[str, str]:
    if OREGON_DARK_SKY_LANDMARKS:
        landmark = min(
            OREGON_DARK_SKY_LANDMARKS,
            key=lambda item: distance_km(lat, lon, item["lat"], item["lon"]),
        )
        distance = distance_km(lat, lon, landmark["lat"], landmark["lon"])
        if distance <= 18:
            return landmark["name"], landmark["kind"]
    return f"Modeled site {lat:.3f}, {lon:.3f}", "Grid-search candidate"


def find_dark_sites(
    lat: float,
    lon: float,
    population_centers: list,
    max_distance_km: float = 100,
    top_n: int = 8,
) -> list[dict]:
    """Return distinct high-darkness candidates inside a straight-line radius."""
    if max_distance_km <= 0 or top_n <= 0:
        return []
    lat_span = max_distance_km / 111.0
    lon_span = max_distance_km / max(20.0, 111.0 * math.cos(math.radians(lat)))
    latitudes = np.linspace(lat - lat_span, lat + lat_span, 15)
    longitudes = np.linspace(lon - lon_span, lon + lon_span, 15)
    candidates = []
    for candidate_lat in latitudes:
        for candidate_lon in longitudes:
            distance = distance_km(lat, lon, float(candidate_lat), float(candidate_lon))
            if distance < 5 or distance > max_distance_km:
                continue
            brightness = artificial_brightness(
                float(candidate_lat), float(candidate_lon), population_centers
            )
            candidates.append({
                "lat": round(float(candidate_lat), 5),
                "lon": round(float(candidate_lon), 5),
                "distance_km": round(distance, 1),
                "brightness_index": brightness,
                "darkness_score": darkness_score(brightness),
                "bortle": bortle_class(brightness),
            })

    # Darkness first, then shorter distance. Keep results spatially distinct.
    candidates.sort(key=lambda item: (-item["darkness_score"], item["distance_km"]))
    selected = []
    minimum_separation = max(8.0, max_distance_km / 8.0)
    for candidate in candidates:
        if any(
            distance_km(candidate["lat"], candidate["lon"], other["lat"], other["lon"])
            < minimum_separation
            for other in selected
        ):
            continue
        name, kind = _candidate_name(candidate["lat"], candidate["lon"])
        selected.append(candidate | {"name": name, "kind": kind})
        if len(selected) == top_n:
            break
    return selected
