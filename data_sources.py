"""Keyless external data sources with graceful failure and regional fallback."""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import streamlit as st

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
REQUEST_TIMEOUT = 12

PNW_POPULATION_CENTERS = [
    {"name": "Portland", "lat": 45.5152, "lon": -122.6784, "population": 652503},
    {"name": "Salem", "lat": 44.9429, "lon": -123.0351, "population": 175535},
    {"name": "Eugene", "lat": 44.0521, "lon": -123.0868, "population": 176654},
    {"name": "Gresham", "lat": 45.5001, "lon": -122.4302, "population": 114247},
    {"name": "Hillsboro", "lat": 45.5229, "lon": -122.9898, "population": 106447},
    {"name": "Bend", "lat": 44.0582, "lon": -121.3153, "population": 102059},
    {"name": "Beaverton", "lat": 45.4871, "lon": -122.8037, "population": 97590},
    {"name": "Medford", "lat": 42.3265, "lon": -122.8756, "population": 85824},
    {"name": "Corvallis", "lat": 44.5646, "lon": -123.2620, "population": 59922},
    {"name": "Albany", "lat": 44.6365, "lon": -123.1059, "population": 56472},
    {"name": "Springfield", "lat": 44.0462, "lon": -123.0220, "population": 61918},
    {"name": "Klamath Falls", "lat": 42.2249, "lon": -121.7817, "population": 21813},
    {"name": "Pendleton", "lat": 45.6721, "lon": -118.7886, "population": 17000},
    {"name": "The Dalles", "lat": 45.5946, "lon": -121.1787, "population": 16259},
    {"name": "Seattle", "lat": 47.6062, "lon": -122.3321, "population": 755078},
    {"name": "Tacoma", "lat": 47.2529, "lon": -122.4443, "population": 219346},
    {"name": "Vancouver", "lat": 45.6387, "lon": -122.6615, "population": 196442},
    {"name": "Spokane", "lat": 47.6588, "lon": -117.4260, "population": 229447},
    {"name": "Boise", "lat": 43.6150, "lon": -116.2023, "population": 235684},
]
PNW_ADMIN1_CODES = {
    "Seattle": "WA", "Tacoma": "WA", "Vancouver": "WA", "Spokane": "WA",
    "Boise": "ID",
}

OREGON_DARK_SKY_LANDMARKS = [
    {"name": "Prineville Reservoir State Park", "lat": 44.1310, "lon": -120.7259, "kind": "International Dark Sky Park"},
    {"name": "Painted Hills", "lat": 44.6501, "lon": -120.2707, "kind": "John Day Fossil Beds"},
    {"name": "Steens Mountain", "lat": 42.6365, "lon": -118.5763, "kind": "Remote high-desert site"},
    {"name": "Oregon Outback Dark Sky Sanctuary", "lat": 42.7200, "lon": -120.5000, "kind": "Dark Sky Sanctuary region"},
]

GEONAMES_COLUMNS = [
    "geonameid", "name", "asciiname", "alternatenames", "latitude", "longitude",
    "feature_class", "feature_code", "country_code", "cc2", "admin1_code",
    "admin2_code", "admin3_code", "admin4_code", "population", "elevation",
    "dem", "timezone", "modification_date",
]
GEONAMES_PATH = Path(__file__).parent / "data" / "cities15000.txt"


def location_display_label(result: dict) -> str:
    parts = [result.get("name"), result.get("admin1"), result.get("country")]
    return ", ".join(str(part).strip() for part in parts if part is not None and str(part).strip())


@st.cache_data(ttl=3600, show_spinner=False)
def geocode_search(name: str, count: int = 8) -> list[dict]:
    """Return ordered, label-deduplicated Open-Meteo location matches."""
    try:
        response = requests.get(
            GEOCODING_URL,
            params={
                "name": name.strip(),
                "count": max(1, min(100, int(count))),
                "language": "en",
                "format": "json",
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        matches = []
        seen_labels = set()
        for raw in response.json().get("results") or []:
            match = {
                "name": raw.get("name", name),
                "admin1": raw.get("admin1", "") or "",
                "country": raw.get("country", "") or "",
                "country_code": raw.get("country_code", "") or "",
                "latitude": float(raw["latitude"]),
                "longitude": float(raw["longitude"]),
                "timezone": raw.get("timezone", "UTC") or "UTC",
            }
            if raw.get("population") is not None:
                match["population"] = int(raw["population"])
            match["display_label"] = location_display_label(match)
            if match["display_label"] in seen_labels:
                continue
            seen_labels.add(match["display_label"])
            matches.append(match)
        return matches
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return []


@st.cache_data(ttl=3600, show_spinner=False)
def geocode_location(query: str) -> tuple[dict | None, str | None]:
    try:
        response = requests.get(
            GEOCODING_URL,
            params={"name": query.strip(), "count": 1, "language": "en", "format": "json"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        results = response.json().get("results")
        if not results:
            return None, "No matching location was found. Try a city and state."
        result = results[0]
        return {
            "name": result.get("name", query),
            "lat": float(result["latitude"]),
            "lon": float(result["longitude"]),
            "admin1": result.get("admin1", ""),
            "country": result.get("country", ""),
            "country_code": result.get("country_code", "") or "",
            "timezone": result.get("timezone", "UTC"),
        }, None
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None, "Location search is temporarily unavailable. Check your connection and try again."


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_forecast(lat: float, lon: float) -> tuple[list[dict], str | None]:
    try:
        response = requests.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "cloud_cover,cloud_cover_low,cloud_cover_mid,cloud_cover_high,visibility,relative_humidity_2m,temperature_2m,dew_point_2m,wind_speed_10m",
                "forecast_days": 8,
                "past_days": 1,
                "timezone": "auto",
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        hourly = payload.get("hourly", {})
        required = ("time", "cloud_cover", "visibility", "relative_humidity_2m")
        if not all(hourly.get(key) for key in required):
            raise ValueError("Incomplete hourly forecast")
        offset = timedelta(seconds=int(payload.get("utc_offset_seconds", 0)))
        rows = []
        for index, local_time in enumerate(hourly["time"]):
            local_dt = datetime.fromisoformat(local_time)
            utc_dt = (local_dt - offset).replace(tzinfo=timezone.utc)
            rows.append({key: hourly[key][index] for key in hourly if key != "time"} | {"time": utc_dt})
        return rows, None
    except (requests.RequestException, ValueError, KeyError, TypeError, IndexError):
        return [], "Weather data is temporarily unavailable. The app is still usable, but tonight's score cannot be calculated."


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_air_quality(lat: float, lon: float) -> tuple[list[dict], str | None]:
    try:
        response = requests.get(
            AIR_QUALITY_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "pm2_5,aerosol_optical_depth",
                "forecast_days": 5,
                "timezone": "auto",
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        hourly = payload.get("hourly", {})
        if not hourly.get("time") or not hourly.get("pm2_5"):
            raise ValueError("Incomplete air-quality response")
        offset = timedelta(seconds=int(payload.get("utc_offset_seconds", 0)))
        rows = []
        for index, local_time in enumerate(hourly["time"]):
            local_dt = datetime.fromisoformat(local_time)
            rows.append({
                "time": (local_dt - offset).replace(tzinfo=timezone.utc),
                "pm2_5": hourly["pm2_5"][index],
                "aerosol_optical_depth": (hourly.get("aerosol_optical_depth") or [None] * len(hourly["time"]))[index],
            })
        return rows, None
    except (requests.RequestException, ValueError, KeyError, TypeError, IndexError):
        return [], "Air-quality detail is unavailable; visibility still provides a haze proxy."


def _parse_population(raw: object) -> int | None:
    cleaned = re.sub(r"[^0-9]", "", str(raw))
    if not cleaned:
        return None
    value = int(cleaned)
    return value if value > 0 else None


@st.cache_data(ttl=3600, show_spinner=False)
def _load_geonames() -> pd.DataFrame:
    return pd.read_csv(
        GEONAMES_PATH,
        sep="\t",
        names=GEONAMES_COLUMNS,
        usecols=["name", "latitude", "longitude", "feature_class", "feature_code", "population", "country_code", "admin1_code"],
        dtype={
            "name": "string", "latitude": float, "longitude": float,
            "feature_class": "string", "feature_code": "string",
            "population": "int64", "country_code": "string", "admin1_code": "string",
        },
        keep_default_na=False,
    )


def _geonames_within_radius(lat: float, lon: float, radius_km: float = 150.0) -> list[dict]:
    frame = _load_geonames()
    latitudes = np.radians(frame["latitude"].to_numpy())
    longitudes = np.radians(frame["longitude"].to_numpy())
    target_latitude = np.radians(lat)
    target_longitude = np.radians(lon)
    dlat = latitudes - target_latitude
    dlon = longitudes - target_longitude
    a = np.sin(dlat / 2) ** 2 + np.cos(target_latitude) * np.cos(latitudes) * np.sin(dlon / 2) ** 2
    distances = 6371.0 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
    nearby = frame.loc[(distances <= radius_km) & (frame["feature_class"] == "P")]
    return [
        {
            "name": row.name, "lat": float(row.latitude), "lon": float(row.longitude),
            "population": int(row.population), "country_code": row.country_code,
            "feature_class": row.feature_class, "feature_code": row.feature_code,
            "admin1_code": row.admin1_code,
        }
        for row in nearby.itertuples(index=False)
        if int(row.population) > 0
    ]


def _pnw_population_fallback() -> list[dict]:
    return [
        center | {
            "country_code": "US",
            "feature_class": "P",
            "admin1_code": PNW_ADMIN1_CODES.get(center["name"], "OR"),
        }
        for center in PNW_POPULATION_CENTERS
    ]


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_population_centers(lat: float, lon: float, use_overpass: bool = False) -> tuple[list[dict], bool, str | None]:
    """Load committed GeoNames data; optionally enrich it with live Overpass."""
    try:
        centers = _geonames_within_radius(lat, lon)
        # Use verified local figures for key Oregon demo cities.
        nearby_enrichment = []
        for center in PNW_POPULATION_CENTERS:
            rough_distance = ((center["lat"] - lat) ** 2 + ((center["lon"] - lon) * np.cos(np.radians(lat))) ** 2) ** 0.5 * 111
            if rough_distance <= 150:
                nearby_enrichment.append(center | {
                    "country_code": "US",
                    "feature_class": "P",
                    "admin1_code": PNW_ADMIN1_CODES.get(center["name"], "OR"),
                })
        merged = {center["name"].casefold(): center for center in centers}
        merged.update({center["name"].casefold(): center for center in nearby_enrichment})
        centers = list(merged.values())
    except (OSError, ValueError, pd.errors.ParserError):
        return _pnw_population_fallback(), False, "GeoNames data could not be loaded; using the bundled PNW emergency dataset."

    if not use_overpass:
        return centers, False, None

    query = f'''[out:json][timeout:25];
(
  node["place"~"^(city|town|village)$"]["population"](around:150000,{lat},{lon});
);
out body;'''
    for attempt in range(2):
        try:
            response = requests.post(OVERPASS_URL, data={"data": query}, timeout=30)
            response.raise_for_status()
            enriched = {center["name"].casefold(): center for center in centers}
            for element in response.json().get("elements", []):
                population = _parse_population(element.get("tags", {}).get("population"))
                if population is not None:
                    center = {
                        "name": element.get("tags", {}).get("name", "Unnamed place"),
                        "lat": float(element["lat"]),
                        "lon": float(element["lon"]),
                        "population": population,
                    }
                    enriched[center["name"].casefold()] = center
            return list(enriched.values()), True, None
        except (requests.RequestException, ValueError, KeyError, TypeError):
            if attempt == 0:
                time.sleep(1)
    return centers, False, None


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1_rad, lat2_rad = np.radians(lat1), np.radians(lat2)
    dlat = lat2_rad - lat1_rad
    dlon = np.radians(lon2 - lon1)
    value = np.sin(dlat / 2) ** 2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2) ** 2
    return float(6371.0 * 2 * np.arcsin(np.sqrt(np.clip(value, 0, 1))))


@st.cache_data(ttl=86400, show_spinner=False)
def confirm_land_by_elevation(sites: list[dict]) -> tuple[list[dict], bool]:
    """Drop zero-elevation DEM cells, which represent open water in GLO-90."""
    if not sites:
        return [], True
    try:
        response = requests.get(
            ELEVATION_URL,
            params={
                "latitude": ",".join(str(site["lat"]) for site in sites),
                "longitude": ",".join(str(site["lon"]) for site in sites),
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        elevations = response.json().get("elevation") or []
        if len(elevations) != len(sites):
            raise ValueError("Incomplete elevation response")
        confirmed = []
        for site, elevation in zip(sites, elevations):
            elevation_m = float(elevation)
            if abs(elevation_m) > 0.5:
                confirmed.append(site | {"elevation_m": elevation_m})
        return confirmed, True
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return [], False


@st.cache_data(ttl=3600, show_spinner=False)
def enrich_dark_sites_with_osm(sites: list[dict]) -> tuple[list[dict], bool]:
    """Prefer nearby named OSM recreation features; otherwise return honest town fallbacks."""
    fallback = [site | {
        "access_label": (
            "Nearest town — look for a public pullout or park on the outskirts"
            if site.get("kind") != "Modeled land point" else ""
        ),
        "osm_public_feature": False,
    } for site in sites]
    if not sites:
        return fallback, False

    clauses = []
    for site in sites:
        point = f"(around:5000,{site['lat']},{site['lon']})"
        clauses.extend([
            f'nwr{point}["leisure"~"^(park|nature_reserve|recreation_ground)$"];',
            f'nwr{point}["tourism"="viewpoint"];',
            f'nwr{point}["highway"="trailhead"];',
            f'nwr{point}["boundary"~"^(protected_area|national_park)$"];',
        ])
    query = "[out:json][timeout:25];(" + "".join(clauses) + ");out center tags;"
    try:
        response = requests.post(OVERPASS_URL, data={"data": query}, timeout=30)
        response.raise_for_status()
        features = []
        for element in response.json().get("elements", []):
            tags = element.get("tags", {})
            name = str(tags.get("name", "")).strip()
            center = element.get("center", {})
            feature_lat = element.get("lat", center.get("lat"))
            feature_lon = element.get("lon", center.get("lon"))
            access = str(tags.get("access", "")).lower()
            if not name or feature_lat is None or feature_lon is None or access in {"no", "private", "customers"}:
                continue
            feature_type_raw = (
                tags.get("leisure") or tags.get("tourism") or tags.get("highway")
                or tags.get("boundary") or "recreation feature"
            )
            feature_type = feature_type_raw.replace("_", " ")
            confirmed = access in {"yes", "permissive", "designated"} or tags.get("ownership") == "public"
            if not confirmed:
                continue
            if feature_type_raw in {"park", "nature_reserve", "recreation_ground"}:
                access_label = "Public park"
            elif feature_type_raw == "trailhead":
                access_label = "Trailhead — public access"
            elif feature_type_raw == "viewpoint":
                access_label = "Viewpoint — public access"
            else:
                access_label = "Public protected area"
            features.append({
                "name": name, "lat": float(feature_lat), "lon": float(feature_lon),
                "kind": f"OpenStreetMap {feature_type}", "access_label": access_label,
                "osm_public_feature": confirmed,
            })
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return fallback, False

    enriched = []
    used_osm = False
    for site in sites:
        nearby = sorted(
            (
                (_distance_km(site["lat"], site["lon"], feature["lat"], feature["lon"]), feature)
                for feature in features
            ),
            key=lambda pair: pair[0],
        )
        if nearby and nearby[0][0] <= 5.0:
            used_osm = True
            enriched.append(site | nearby[0][1] | {"nearest_town": site["name"]})
        else:
            enriched.append(site | {
                "access_label": (
                    "Nearest town — look for a public pullout or park on the outskirts"
                    if site.get("kind") != "Modeled land point" else ""
                ),
                "osm_public_feature": False,
            })
    return enriched, used_osm
