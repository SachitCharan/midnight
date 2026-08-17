"""Low-precision solar and lunar astronomy implemented from first principles."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _normalize(angle: float) -> float:
    return angle % 360.0


def _signed_angle(angle: float) -> float:
    return (angle + 180.0) % 360.0 - 180.0


def julian_date(dt_utc: datetime) -> float:
    return _utc(dt_utc).timestamp() / 86400.0 + 2440587.5


def days_since_j2000(dt_utc: datetime) -> float:
    return julian_date(dt_utc) - 2451545.0


def _sun_equatorial(dt_utc: datetime) -> tuple[float, float, float]:
    d = days_since_j2000(dt_utc)
    mean_longitude = _normalize(280.460 + 0.9856474 * d)
    anomaly = math.radians(_normalize(357.528 + 0.9856003 * d))
    ecliptic_longitude = _normalize(
        mean_longitude + 1.915 * math.sin(anomaly) + 0.020 * math.sin(2 * anomaly)
    )
    obliquity = math.radians(23.439 - 0.0000004 * d)
    longitude = math.radians(ecliptic_longitude)
    right_ascension = _normalize(math.degrees(math.atan2(
        math.cos(obliquity) * math.sin(longitude), math.cos(longitude)
    )))
    declination = math.degrees(math.asin(math.sin(obliquity) * math.sin(longitude)))
    return right_ascension, declination, ecliptic_longitude


def _moon_equatorial(dt_utc: datetime) -> tuple[float, float, float]:
    d = days_since_j2000(dt_utc)
    mean_longitude = _normalize(218.316 + 13.176396 * d)
    anomaly = math.radians(_normalize(134.963 + 13.064993 * d))
    argument_latitude = math.radians(_normalize(93.272 + 13.229350 * d))
    ecliptic_longitude = _normalize(mean_longitude + 6.289 * math.sin(anomaly))
    ecliptic_latitude = 5.128 * math.sin(argument_latitude)
    obliquity = math.radians(23.439 - 0.0000004 * d)
    longitude = math.radians(ecliptic_longitude)
    latitude = math.radians(ecliptic_latitude)
    right_ascension = _normalize(math.degrees(math.atan2(
        math.sin(longitude) * math.cos(obliquity) - math.tan(latitude) * math.sin(obliquity),
        math.cos(longitude),
    )))
    declination = math.degrees(math.asin(
        math.sin(latitude) * math.cos(obliquity)
        + math.cos(latitude) * math.sin(obliquity) * math.sin(longitude)
    ))
    return right_ascension, declination, ecliptic_longitude


def _altitude(dt_utc: datetime, lat: float, lon: float, ra: float, dec: float) -> float:
    d = days_since_j2000(dt_utc)
    local_sidereal_time = _normalize(280.46061837 + 360.98564736629 * d + lon)
    hour_angle = math.radians(_signed_angle(local_sidereal_time - ra))
    latitude = math.radians(lat)
    declination = math.radians(dec)
    sine_altitude = (
        math.sin(latitude) * math.sin(declination)
        + math.cos(latitude) * math.cos(declination) * math.cos(hour_angle)
    )
    return math.degrees(math.asin(max(-1.0, min(1.0, sine_altitude))))


def sun_altitude(dt_utc: datetime, lat: float, lon: float) -> float:
    ra, dec, _ = _sun_equatorial(dt_utc)
    return _altitude(dt_utc, lat, lon, ra, dec)


def moon_altitude(dt_utc: datetime, lat: float, lon: float) -> float:
    ra, dec, _ = _moon_equatorial(dt_utc)
    return _altitude(dt_utc, lat, lon, ra, dec)


def moon_illumination(dt_utc: datetime) -> float:
    _, _, sun_longitude = _sun_equatorial(dt_utc)
    _, _, moon_longitude = _moon_equatorial(dt_utc)
    elongation = math.radians(_normalize(moon_longitude - sun_longitude))
    return max(0.0, min(1.0, (1.0 - math.cos(elongation)) / 2.0))


def moon_is_waxing(dt_utc: datetime) -> bool:
    step = timedelta(hours=3)
    return moon_illumination(dt_utc + step) >= moon_illumination(dt_utc - step)


def moon_phase_name(illumination: float, waxing: bool) -> str:
    illumination = max(0.0, min(1.0, illumination))
    if illumination < 0.03:
        return "New Moon"
    if illumination > 0.97:
        return "Full Moon"
    if 0.47 <= illumination <= 0.53:
        return "First Quarter" if waxing else "Last Quarter"
    if illumination < 0.5:
        return "Waxing Crescent" if waxing else "Waning Crescent"
    return "Waxing Gibbous" if waxing else "Waning Gibbous"


def is_astronomical_darkness(dt_utc: datetime, lat: float, lon: float) -> bool:
    return sun_altitude(dt_utc, lat, lon) < -18.0


def find_dark_window(
    dt_utc_start: datetime, lat: float, lon: float, hours: int = 24
) -> tuple[datetime, datetime] | None:
    """Return the first contiguous dark interval sampled at five-minute resolution."""
    start = _utc(dt_utc_start)
    step = timedelta(minutes=5)
    samples = hours * 12
    dark_start: datetime | None = None
    for index in range(samples + 1):
        current = start + index * step
        dark = is_astronomical_darkness(current, lat, lon)
        if dark and dark_start is None:
            dark_start = current
        elif not dark and dark_start is not None:
            return dark_start, current
    if dark_start is not None:
        return dark_start, start + timedelta(hours=hours)
    return None


_PLANET_ELEMENTS = {
    "Mercury": lambda d: (48.3313 + 3.24587e-5*d, 7.0047 + 5.00e-8*d, 29.1241 + 1.01444e-5*d, 0.387098, 0.205635 + 5.59e-10*d, 168.6562 + 4.0923344368*d),
    "Venus": lambda d: (76.6799 + 2.46590e-5*d, 3.3946 + 2.75e-8*d, 54.8910 + 1.38374e-5*d, 0.723330, 0.006773 - 1.302e-9*d, 48.0052 + 1.6021302244*d),
    "Mars": lambda d: (49.5574 + 2.11081e-5*d, 1.8497 - 1.78e-8*d, 286.5016 + 2.92961e-5*d, 1.523688, 0.093405 + 2.516e-9*d, 18.6021 + 0.5240207766*d),
    "Jupiter": lambda d: (100.4542 + 2.76854e-5*d, 1.3030 - 1.557e-7*d, 273.8777 + 1.64505e-5*d, 5.20256, 0.048498 + 4.469e-9*d, 19.8950 + 0.0830853001*d),
    "Saturn": lambda d: (113.6634 + 2.38980e-5*d, 2.4886 - 1.081e-7*d, 339.3939 + 2.97661e-5*d, 9.55475, 0.055546 - 9.499e-9*d, 316.9670 + 0.0334442282*d),
}

_TYPICAL_MAGNITUDES = {"Mercury": -0.4, "Venus": -4.0, "Mars": 0.0, "Jupiter": -2.2, "Saturn": 0.7}


def _eccentric_anomaly(mean_anomaly_deg: float, eccentricity: float) -> float:
    mean_anomaly = math.radians(_normalize(mean_anomaly_deg))
    eccentric = mean_anomaly
    for _ in range(12):
        delta = (eccentric - eccentricity * math.sin(eccentric) - mean_anomaly) / (1 - eccentricity * math.cos(eccentric))
        eccentric -= delta
        if abs(delta) < 1e-10:
            break
    return eccentric


def _sun_cartesian(day_number: float) -> tuple[float, float, float]:
    perihelion = math.radians(_normalize(282.9404 + 4.70935e-5 * day_number))
    eccentricity = 0.016709 - 1.151e-9 * day_number
    anomaly = 356.0470 + 0.9856002585 * day_number
    eccentric = _eccentric_anomaly(anomaly, eccentricity)
    xv = math.cos(eccentric) - eccentricity
    yv = math.sqrt(1 - eccentricity**2) * math.sin(eccentric)
    true_anomaly = math.atan2(yv, xv)
    radius = math.hypot(xv, yv)
    longitude = true_anomaly + perihelion
    return radius * math.cos(longitude), radius * math.sin(longitude), 0.0


def _planet_equatorial(dt_utc: datetime, planet: str) -> tuple[float, float]:
    if planet not in _PLANET_ELEMENTS:
        raise ValueError(f"Unsupported planet: {planet}")
    day_number = days_since_j2000(dt_utc) + 1.5
    node, inclination, perihelion, semimajor, eccentricity, anomaly = _PLANET_ELEMENTS[planet](day_number)
    node, inclination, perihelion = map(math.radians, (_normalize(node), inclination, _normalize(perihelion)))
    eccentric = _eccentric_anomaly(anomaly, eccentricity)
    xv = semimajor * (math.cos(eccentric) - eccentricity)
    yv = semimajor * math.sqrt(1 - eccentricity**2) * math.sin(eccentric)
    true_anomaly = math.atan2(yv, xv)
    radius = math.hypot(xv, yv)
    argument = true_anomaly + perihelion
    xh = radius * (math.cos(node) * math.cos(argument) - math.sin(node) * math.sin(argument) * math.cos(inclination))
    yh = radius * (math.sin(node) * math.cos(argument) + math.cos(node) * math.sin(argument) * math.cos(inclination))
    zh = radius * math.sin(argument) * math.sin(inclination)
    xs, ys, _ = _sun_cartesian(day_number)
    xg, yg, zg = xh + xs, yh + ys, zh
    obliquity = math.radians(23.4393 - 3.563e-7 * day_number)
    xe = xg
    ye = yg * math.cos(obliquity) - zg * math.sin(obliquity)
    ze = yg * math.sin(obliquity) + zg * math.cos(obliquity)
    right_ascension = _normalize(math.degrees(math.atan2(ye, xe)))
    declination = math.degrees(math.atan2(ze, math.hypot(xe, ye)))
    return right_ascension, declination


def _azimuth(dt_utc: datetime, lat: float, lon: float, ra: float, dec: float) -> float:
    d = days_since_j2000(dt_utc)
    local_sidereal_time = _normalize(280.46061837 + 360.98564736629 * d + lon)
    hour_angle = math.radians(_signed_angle(local_sidereal_time - ra))
    latitude = math.radians(lat)
    declination = math.radians(dec)
    return _normalize(math.degrees(math.atan2(
        math.sin(hour_angle),
        math.cos(hour_angle) * math.sin(latitude) - math.tan(declination) * math.cos(latitude),
    )) + 180.0)


def planet_altitude(dt_utc: datetime, lat: float, lon: float, planet: str) -> float:
    ra, dec = _planet_equatorial(dt_utc, planet)
    return _altitude(dt_utc, lat, lon, ra, dec)


def visible_planets(dt_utc: datetime, lat: float, lon: float, min_altitude: float = 10.0) -> list[dict]:
    directions = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    visible = []
    for planet in _PLANET_ELEMENTS:
        ra, dec = _planet_equatorial(dt_utc, planet)
        altitude = _altitude(dt_utc, lat, lon, ra, dec)
        if altitude < min_altitude:
            continue
        azimuth = _azimuth(dt_utc, lat, lon, ra, dec)
        direction = directions[int((azimuth + 22.5) // 45) % 8]
        visible.append({
            "name": planet,
            "altitude": round(altitude, 1),
            "azimuth": round(azimuth, 1),
            "direction": direction,
            "typical_magnitude": _TYPICAL_MAGNITUDES[planet],
        })
    return sorted(visible, key=lambda item: item["altitude"], reverse=True)
