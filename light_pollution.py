"""Modeled artificial sky brightness using Walker's Law."""

from __future__ import annotations

import math

EARTH_RADIUS_KM = 6371.0


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def artificial_brightness(lat: float, lon: float, population_centers: list) -> float:
    total = 0.0
    for center in population_centers:
        population = max(0, float(center.get("population", 0)))
        distance = _distance_km(lat, lon, float(center["lat"]), float(center["lon"]))
        if distance <= 150.0:
            total += population * max(1.0, distance) ** -2.5
    return total


def bortle_class(brightness_index: float) -> int:
    """Map the arbitrary Walker index onto Bortle 1–9 using log anchors.

    Anchors are approximately 0.3 for a remote site (Bortle 1) and 650,000
    at the center of a major PNW city (Bortle 9).
    """
    if brightness_index <= 0:
        return 1
    scaled = 1.0 + (math.log10(brightness_index) + 0.5) * (8.0 / 6.3)
    return max(1, min(9, round(scaled)))


_DESCRIPTIONS = {
    1: "Pristine dark sky; the Milky Way is highly detailed.",
    2: "Typical truly dark site with faint skyglow near the horizon.",
    3: "Rural sky; the Milky Way remains prominent.",
    4: "Rural-to-suburban transition with visible light domes.",
    5: "Suburban sky; the Milky Way is washed out near the horizon.",
    6: "Bright suburban sky with limited faint-object visibility.",
    7: "Suburban-to-urban sky; only brighter deep-sky objects stand out.",
    8: "City sky; familiar constellations are incomplete.",
    9: "Inner-city sky; primarily the Moon, planets, and brightest stars show.",
}


def bortle_description(bortle: int) -> str:
    return _DESCRIPTIONS[max(1, min(9, int(bortle)))]


def darkness_score(brightness_index: float) -> float:
    if brightness_index <= 0:
        return 100.0
    # Preserve continuous resolution while using the same calibrated anchors.
    bortle_continuous = 1.0 + (math.log10(brightness_index) + 0.5) * (8.0 / 6.3)
    bortle_continuous = max(1.0, min(9.0, bortle_continuous))
    return round(100.0 * (9.0 - bortle_continuous) / 8.0, 1)


def visibility_expectations(bortle: int) -> dict[str, str]:
    value = max(1, min(9, int(bortle)))
    if value <= 2:
        return {
            "visible": "The Milky Way is richly structured; faint deep-sky objects and meteor showers can be excellent.",
            "missing": "Very little natural sky detail is lost to modeled artificial brightness.",
        }
    if value <= 4:
        return {
            "visible": "The Milky Way, meteor showers, star clusters, and many brighter deep-sky objects should be visible.",
            "missing": "The faintest galaxies and low-contrast Milky Way detail begin to wash out.",
        }
    if value <= 6:
        return {
            "visible": "The Moon, planets, constellations, bright clusters, and strong meteor showers remain visible.",
            "missing": "Most Milky Way structure and faint galaxies are hidden by skyglow.",
        }
    return {
        "visible": "The Moon, bright planets, and the brightest stars and constellations remain visible.",
        "missing": "The Milky Way, faint meteors, nebulae, and most galaxies are lost in modeled skyglow.",
    }
