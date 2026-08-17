"""Dependency-free test runner for Umbra's pure logic."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import requests

from astronomy import (
    find_dark_window,
    is_astronomical_darkness,
    moon_altitude,
    moon_illumination,
    sun_altitude,
    planet_altitude,
    visible_planets,
)
from light_pollution import artificial_brightness, bortle_class, darkness_score
from scoring import compute_stargazing_score, find_best_window, limiting_factor, score_label, summarize_nights
from data_sources import fetch_air_quality, fetch_forecast, fetch_population_centers, geocode_location, geocode_search
from dark_sites import distance_km, find_dark_sites
from meteor_showers import meteor_activity
from units import default_unit_system, distance_to_km, format_distance

UTC = timezone.utc


def test_moon_illumination_bounded() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    values = [moon_illumination(start + timedelta(hours=6 * i)) for i in range(60 * 4)]
    assert all(0.0 <= value <= 1.0 for value in values)


def test_lunar_cycle_length() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    values = [moon_illumination(start + timedelta(hours=3 * i)) for i in range(70 * 8)]
    peaks = [i for i in range(1, len(values) - 1) if values[i] > values[i - 1] and values[i] >= values[i + 1]]
    interval_days = (peaks[1] - peaks[0]) * 3 / 24
    assert 29.0 <= interval_days <= 30.0, interval_days


def test_sun_altitude_sane() -> None:
    # Longitude 0 makes 12:00 UTC close to local solar noon.
    assert sun_altitude(datetime(2026, 6, 21, 12, tzinfo=UTC), 45.0, 0.0) > 60.0
    assert sun_altitude(datetime(2026, 6, 21, 0, tzinfo=UTC), 45.0, 0.0) < 0.0


def test_darkness_gate() -> None:
    assert not is_astronomical_darkness(datetime(2026, 12, 21, 12, tzinfo=UTC), 45.0, 0.0)
    assert is_astronomical_darkness(datetime(2026, 12, 21, 2, tzinfo=UTC), 45.0, 0.0)


def test_polar_edge_case() -> None:
    assert find_dark_window(datetime(2026, 6, 21, 0, tzinfo=UTC), 70.0, 0.0) is None


def test_light_pollution_calibration() -> None:
    centers = [{"name": "Portland", "lat": 45.5152, "lon": -122.6784, "population": 652503}]
    city = artificial_brightness(45.5152, -122.6784, centers)
    remote = artificial_brightness(44.0, -120.5, centers)
    assert 7 <= bortle_class(city) <= 9
    assert 1 <= bortle_class(remote) <= 3
    assert darkness_score(remote) > darkness_score(city)


def test_score_darkness_gate_and_plausibility() -> None:
    noon_score, state = compute_stargazing_score(
        10, 10, 0.2, 20, 20000, 40,
        dt_utc=datetime(2026, 12, 21, 12, tzinfo=UTC), lat=45, lon=0,
    )
    assert noon_score is None and state["state"] == "not dark yet"
    night_score, subscores = compute_stargazing_score(
        10, 10, 0.2, -5, 20000, 40,
        dt_utc=datetime(2026, 12, 21, 1, tzinfo=UTC), lat=45, lon=0,
    )
    assert night_score is not None and 0 <= night_score <= 100
    assert subscores["moon"] == 100
    assert score_label(night_score) in {"Excellent", "Good", "Fair", "Poor", "Don't bother"}
    assert limiting_factor({"cloud_cover": 70, "light_pollution": 65, "moon": 80, "atmosphere": 90}).startswith("Cloud")


def test_static_population_data_requires_no_network() -> None:
    fetch_population_centers.clear()
    with patch("data_sources.requests.post") as post:
        centers, enriched, message = fetch_population_centers(45.5, -122.7)
    assert centers and not enriched and message is None
    assert any(center["name"] == "Portland" for center in centers)
    post.assert_not_called()


def test_network_failures_are_graceful() -> None:
    geocode_location.clear()
    geocode_search.clear()
    fetch_forecast.clear()
    fetch_air_quality.clear()
    with patch("data_sources.requests.get", side_effect=requests.ConnectionError("offline")):
        matches = geocode_search("Portland")
        location, geocode_error = geocode_location("Portland")
        forecast, forecast_error = fetch_forecast(45.5, -122.7)
        air_quality, air_error = fetch_air_quality(45.5, -122.7)
    assert matches == []
    assert location is None and "unavailable" in geocode_error.lower()
    assert forecast == [] and "unavailable" in forecast_error.lower()
    assert air_quality == [] and "unavailable" in air_error.lower()


def test_empty_geocode_result_is_clean() -> None:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {}
    geocode_location.clear()
    with patch("data_sources.requests.get", return_value=response):
        location, error = geocode_location("not-a-real-place")
    assert location is None and "no matching" in error.lower()


def test_geocode_search_normalizes_and_deduplicates() -> None:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"results": [
        {"name": "Portland", "admin1": "Oregon", "country": "United States", "country_code": "US", "latitude": 45.52, "longitude": -122.68, "population": 652503, "timezone": "America/Los_Angeles"},
        {"name": "Portland", "admin1": "Oregon", "country": "United States", "country_code": "US", "latitude": 45.53, "longitude": -122.67},
        {"name": "Solo", "admin1": None, "country": "Indonesia", "country_code": "ID", "latitude": -7.57, "longitude": 110.82},
    ]}
    geocode_search.clear()
    with patch("data_sources.requests.get", return_value=response):
        matches = geocode_search("Portland", count=8)
    assert len(matches) == 2
    assert matches[0]["display_label"] == "Portland, Oregon, United States"
    assert matches[0]["population"] == 652503
    assert matches[1]["display_label"] == "Solo, Indonesia"
    assert "None" not in matches[1]["display_label"]


def test_optional_overpass_failure_never_replaces_static_data() -> None:
    fetch_population_centers.clear()
    with patch("data_sources.requests.post", side_effect=requests.ConnectionError("offline")), patch("data_sources.time.sleep"):
        centers, enriched, message = fetch_population_centers(45.5, -122.7, use_overpass=True)
    assert centers and not enriched and message is None


def test_dark_sites_are_ranked_and_bounded() -> None:
    centers = [
        {"name": "Portland", "lat": 45.5152, "lon": -122.6784, "population": 652503},
        {"name": "Salem", "lat": 44.9429, "lon": -123.0351, "population": 175535},
    ]
    sites = find_dark_sites(45.5152, -122.6784, centers, max_distance_km=80, top_n=6)
    assert len(sites) == 6
    assert all(5 <= site["distance_km"] <= 80 for site in sites)
    assert all(1 <= site["bortle"] <= 9 for site in sites)
    assert all(sites[index]["darkness_score"] >= sites[index + 1]["darkness_score"] for index in range(len(sites) - 1))
    assert all(abs(distance_km(45.5152, -122.6784, site["lat"], site["lon"]) - site["distance_km"]) < 0.2 for site in sites)


def test_planet_positions_are_sane() -> None:
    when = datetime(2026, 8, 17, 6, tzinfo=UTC)
    for planet in ("Mercury", "Venus", "Mars", "Jupiter", "Saturn"):
        assert -90 <= planet_altitude(when, 45.5, -122.7, planet) <= 90
    for planet in visible_planets(when, 45.5, -122.7, min_altitude=-90):
        assert 0 <= planet["azimuth"] < 360
    # NASA/JPL Horizons gives Saturn elevation 8.44° for Portland at this time.
    assert abs(planet_altitude(when, 45.5152, -122.6784, "Saturn") - 8.44) < 1.0


def test_reykjavik_polar_summer_and_sydney_negative_latitude() -> None:
    reykjavik_start = datetime(2026, 6, 21, tzinfo=UTC)
    assert find_dark_window(reykjavik_start, 64.15, -21.94, 24) is None
    reykjavik_hours = [{
        "time": reykjavik_start + timedelta(hours=index), "cloud_cover": 20,
        "brightness_index": 1, "visibility": 20000, "relative_humidity_2m": 50,
    } for index in range(168)]
    assert find_best_window(reykjavik_hours, 64.15, -21.94) == {}

    sydney_day = datetime(2026, 12, 21, 2, tzinfo=UTC)
    sydney_night = datetime(2026, 12, 21, 14, tzinfo=UTC)
    assert sun_altitude(sydney_day, -33.87, 151.21) > 70
    assert sun_altitude(sydney_night, -33.87, 151.21) < -20
    assert sun_altitude(datetime(2026, 6, 21, 2, tzinfo=UTC), -33.87, 151.21) > 25
    assert -90 <= moon_altitude(sydney_day, -33.87, 151.21) <= 90


def test_metric_and_imperial_distance_paths() -> None:
    assert default_unit_system("US") == "Imperial (mi)"
    assert default_unit_system("JP") == "Metric (km)"
    assert default_unit_system(None) == "Metric (km)"
    assert abs(distance_to_km(10, "Imperial (mi)") - 16.09344) < 1e-6
    assert format_distance(16.09344, "Imperial (mi)") == "10.0 mi"
    assert format_distance(16.09344, "Metric (km)") == "16.1 km"


def test_meteor_calendar_and_multi_night_summary() -> None:
    activity = meteor_activity(date := datetime(2026, 8, 16, tzinfo=UTC))
    assert "Perseids" in {item["name"] for item in activity["active"]}
    start = datetime(2026, 12, 20, tzinfo=UTC)
    hourly = [{
        "time": start + timedelta(hours=index), "cloud_cover": 20,
        "brightness_index": 10, "visibility": 18000, "relative_humidity_2m": 50,
    } for index in range(72)]
    nights = summarize_nights(hourly, 45, 0)
    assert len(nights) >= 2
    assert all(0 <= night["score"] <= 100 for night in nights)


def run_tests() -> None:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"{len(tests)} logic tests passed")


if __name__ == "__main__":
    run_tests()
