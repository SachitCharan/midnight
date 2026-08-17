"""Plain-language consequences for Umbra's numeric model outputs."""

from __future__ import annotations

from datetime import datetime


def interpret_score(score: float) -> str:
    if score >= 85:
        return "Excellent. The sky should support faint stars, meteor watching, and detailed constellations."
    if score >= 70:
        return "Good. Most constellations should be clear, though the faintest objects may be washed out."
    if score >= 50:
        return "Fair. Bright constellations are worthwhile, but faint stars will be difficult."
    if score >= 30:
        return "Poor. Expect only brighter stars and planets to stand out consistently."
    return "Very poor. Only the Moon, bright planets, and the brightest stars are likely to show well."


def interpret_bortle(bortle: int) -> str:
    value = max(1, min(9, int(bortle)))
    if value <= 2:
        return f"Bortle {value} means a truly dark sky. The Milky Way should be obvious and richly detailed."
    if value <= 4:
        return f"Bortle {value} means a rural sky. The Milky Way should remain visible, with some horizon glow."
    if value == 5:
        return "Bortle 5 means a suburban sky. The Milky Way will look faint and lose detail near the horizon."
    if value == 6:
        return "Bortle 6 means a bright suburban sky. The Milky Way is not realistically visible here."
    if value == 7:
        return "Bortle 7 means a suburban-to-urban sky. Only brighter deep-sky objects will stand out."
    if value == 8:
        return "Bortle 8 means a city sky. Many constellation stars disappear into skyglow."
    return "Bortle 9 means an inner-city sky. Expect mainly the Moon, planets, and the brightest stars."


def interpret_moon(illumination: float, altitude: float) -> str:
    fraction = illumination / 100.0 if illumination > 1 else illumination
    fraction = max(0.0, min(1.0, fraction))
    if altitude < 0:
        return "The Moon is below the horizon, so it is not washing out faint stars at this time."
    if fraction >= 0.65:
        return "The bright Moon is above the horizon and will hide many faint stars until it sets."
    if fraction >= 0.30:
        return "The Moon is up and causing noticeable glare, but brighter constellations should remain visible."
    if altitude >= 45:
        return "The Moon is high but still dim enough that its effect on most bright stars should be limited."
    return "The Moon is low and relatively dim, so moonlight should have little effect on the view."


def interpret_clouds(cloud_pct: float) -> str:
    value = max(0.0, min(100.0, float(cloud_pct)))
    if value < 15:
        return "Mostly clear. Long, uninterrupted views should be possible."
    if value < 40:
        return "Some clouds. Most of the sky should stay usable with occasional interruptions."
    if value < 70:
        return "Patchy clouds. Expect gaps between clear stretches."
    if value < 90:
        return "Mostly cloudy. Only short openings are likely to be useful."
    return "Overcast. Stargazing is unlikely even if other conditions are favorable."


def interpret_aerosol(aod: float | None, pm25: float) -> str:
    aerosol = 0.0 if aod is None else max(0.0, float(aod))
    particles = max(0.0, float(pm25))
    if particles < 10 and aerosol < 0.10:
        return "Clear air. Stars near the horizon should retain good contrast."
    if particles < 25 and aerosol < 0.25:
        return "Some haze is likely. Faint stars near the horizon may look washed out."
    return "Hazy air. Particles will dim stars and scatter more city light back into the sky."


def interpret_smoke(pm25: float) -> str:
    particles = max(0.0, float(pm25))
    if particles < 10:
        return "No strong smoke signal appears in the fine-particle forecast."
    if particles < 25:
        return "Some particle haze is present, but the forecast does not show a strong smoke signal."
    return (
        "Elevated fine particles may indicate wildfire smoke; smoke dims stars and scatters city light "
        "back toward the ground."
    )


def interpret_fog(temperature: float, dew_point: float, wind_speed: float) -> tuple[bool, str]:
    spread = float(temperature) - float(dew_point)
    wind = max(0.0, float(wind_speed))
    likely = spread <= 2.0 and wind <= 10.0
    if likely:
        return True, "Fog is likely because the air is near saturation and winds are light; visibility may fall quickly."
    if spread <= 4.0 and wind <= 15.0:
        return False, "Fog is possible if the air cools further, so recheck visibility before leaving."
    return False, "Fog risk is low because the air is well above its dew point or winds are mixing it."


def interpret_cloud_layers(low_pct: float, mid_pct: float, high_pct: float) -> str:
    low = max(0.0, min(100.0, float(low_pct)))
    middle = max(0.0, min(100.0, float(mid_pct)))
    high = max(0.0, min(100.0, float(high_pct)))
    if low >= 65:
        return "Low, thick cloud is dominant and will block most of the sky; this is usually a no-go night."
    if middle >= 65:
        return "Mid-level cloud is widespread and will repeatedly hide stars across large areas of sky."
    if high >= 60:
        return "High thin cloud is dominant; bright stars may show through, but contrast will look soft and washed out."
    if max(low, middle, high) >= 30:
        return "Broken cloud layers should leave some usable openings, with interruptions moving through the view."
    return "All three cloud layers are limited, so cloud height should not be a major obstacle."


def interpret_distance(km: float, units: str) -> str:
    distance_km = max(0.0, float(km))
    drive_minutes = max(5, round((distance_km * 1.2 / 80.0 * 60.0) / 5.0) * 5)
    if units == "Imperial (mi)":
        distance_text = f"{distance_km / 1.609344:.1f} mi"
    else:
        distance_text = f"{distance_km:.1f} km"
    if drive_minutes < 60:
        time_text = f"roughly {drive_minutes:.0f} minutes of driving"
    else:
        hours = drive_minutes / 60.0
        time_text = f"roughly {hours:.1f} hours of driving"
    return f"{distance_text} straight-line — {time_text}, before traffic and road detours."


def interpret_bortle_improvement(start_bortle: int, site_bortle: int) -> str:
    start = max(1, min(9, int(start_bortle)))
    site = max(1, min(9, int(site_bortle)))
    gain = start - site
    prefix = f"Bortle {start} → {site}."
    if site <= 4 and gain > 0:
        return f"{prefix} Meaningful improvement — the Milky Way should become visible in clear, moonless conditions."
    if gain >= 3:
        return f"{prefix} Meaningful improvement — many more faint stars should appear."
    if gain == 2:
        return f"{prefix} Modest improvement — the Milky Way still won't be visible."
    if gain == 1:
        return f"{prefix} Marginal improvement — expect only a small increase in visible stars."
    return f"{prefix} No modeled improvement over the starting location."


def estimated_dark_sky_distance_km(start_bortle: int) -> float:
    """Return a clearly labeled rule-of-thumb radius for reaching Bortle 4 or better."""
    return {9: 145.0, 8: 120.0, 7: 90.0, 6: 65.0, 5: 40.0}.get(max(1, min(9, int(start_bortle))), 0.0)


def interpret_darkness_window(start: datetime, end: datetime) -> str:
    start_text = start.strftime("%I:%M %p").lstrip("0")
    end_text = end.strftime("%I:%M %p").lstrip("0")
    duration = max(0.0, (end - start).total_seconds() / 3600.0)
    if duration < 2:
        consequence = "That is a short observing window, so plan to be ready before it begins."
    elif duration < 5:
        consequence = "That leaves a useful but limited window for observing."
    else:
        consequence = "That provides a long window for choosing the clearest hours."
    return (
        f"True darkness runs {start_text} to {end_text}. Before and after, twilight hides faint objects. "
        f"{consequence}"
    )


def interpret_component(factor: str, score: float) -> str:
    value = max(0.0, min(100.0, float(score)))
    labels = {
        "cloud_cover": "clouds",
        "light_pollution": "local skyglow",
        "moon": "moonlight",
        "atmosphere": "haze and humidity",
    }
    subject = labels.get(factor, factor.replace("_", " "))
    if value >= 80:
        return f"{subject.capitalize()} should have little effect on the view."
    if value >= 50:
        return f"{subject.capitalize()} will reduce some faint detail but leave brighter targets usable."
    return f"{subject.capitalize()} is strongly limiting what can be seen."


_LIMITING_MAGNITUDE = {1: 7.6, 2: 7.1, 3: 6.6, 4: 6.2, 5: 5.7, 6: 5.3, 7: 4.8, 8: 4.3, 9: 3.8}
_STAR_COUNT = {1: 6000, 2: 4500, 3: 3000, 4: 1500, 5: 800, 6: 400, 7: 200, 8: 80, 9: 30}


def visibility_snapshot(
    bortle: int,
    illumination: float,
    moon_alt: float,
    cloud_pct: float,
    planet_names: list[str],
    active_showers: list[dict],
) -> dict[str, str]:
    value = max(1, min(9, int(bortle)))
    moon_fraction = illumination / 100.0 if illumination > 1 else illumination
    moon_penalty = moon_alt >= 0 and moon_fraction >= 0.45
    clouds = max(0.0, min(100.0, float(cloud_pct)))

    if clouds >= 70 or value >= 6 or (value >= 5 and moon_penalty):
        milky_way = "Not visible tonight; skyglow, moonlight, or clouds erase its low-contrast structure."
    elif value >= 4 or moon_penalty or clouds >= 40:
        milky_way = "Faintly visible at best, away from the brightest horizon glow."
    else:
        milky_way = "Visible, with more structure appearing as the sky gets darker and clearer."

    if value <= 3 and clouds < 40 and not moon_penalty:
        deep_sky = "Many star clusters, nebulae, and brighter galaxies are realistic naked-eye or binocular targets."
    elif value <= 5 and clouds < 60:
        deep_sky = "Only brighter clusters and a few prominent deep-sky objects are realistic."
    else:
        deep_sky = "Beyond the brightest clusters, deep-sky objects are unlikely to stand out."

    planets = ", ".join(planet_names) if planet_names else "No naked-eye planet is above 10° at the selected time"
    planet_text = f"{planets}." if planet_names else f"{planets}."

    sky_factor = {1: 1.0, 2: 0.9, 3: 0.75, 4: 0.6, 5: 0.45, 6: 0.3, 7: 0.2, 8: 0.1, 9: 0.05}[value]
    cloud_factor = max(0.05, 1.0 - clouds / 100.0)
    moon_factor = max(0.25, 1.0 - moon_fraction * 0.65) if moon_alt >= 0 else 1.0
    if active_showers:
        meteor_parts = []
        for shower in active_showers:
            adjusted = max(0, round(shower["zhr"] * sky_factor * cloud_factor * moon_factor))
            meteor_parts.append(f"{shower['name']}: roughly {adjusted} visible meteors per hour")
        meteors = "; ".join(meteor_parts) + " under the modeled conditions."
    else:
        meteors = "No major annual meteor shower is active at the selected time."

    magnitude = _LIMITING_MAGNITUDE[value]
    magnitude -= max(0.0, clouds - 20.0) / 100.0 * 1.5
    if moon_penalty:
        magnitude -= moon_fraction * 0.8
    magnitude = max(1.5, round(magnitude, 1))
    limiting = (
        f"The faintest visible stars are approximately magnitude {magnitude:.1f}. "
        "Polaris is magnitude 2, and higher numbers mean fainter stars."
    )

    star_factor = max(0.05, 1.0 - clouds / 100.0)
    if moon_penalty:
        star_factor *= max(0.35, 1.0 - moon_fraction * 0.55)
    stars = max(10, int(round((_STAR_COUNT[value] * star_factor) / 10.0) * 10))
    loss = (
        f"From here, roughly {stars:,} stars may be visible under tonight’s conditions. "
        "Under a Bortle 2 sky, several thousand would be visible and the Milky Way would be obvious."
    )
    return {
        "milky_way": milky_way,
        "planets": planet_text,
        "meteors": meteors,
        "deep_sky": deep_sky,
        "limiting_magnitude": limiting,
        "loss": loss,
    }
