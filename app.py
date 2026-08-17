"""Accessible Streamlit interface for the complete Umbra experience."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
import pydeck as pdk
import streamlit as st

from astronomy import (
    find_dark_window,
    moon_altitude,
    moon_illumination,
    moon_is_waxing,
    moon_phase_name,
    visible_planets,
)
from dark_sites import find_dark_sites
from data_sources import fetch_air_quality, fetch_forecast, fetch_population_centers, geocode_location
from light_pollution import artificial_brightness, bortle_class, bortle_description, visibility_expectations
from meteor_showers import meteor_activity
from scoring import compute_stargazing_score, find_best_window, limiting_factor, score_label, summarize_nights

st.set_page_config(page_title="Umbra", page_icon="🌘", layout="centered")

st.markdown("""
<style>
div[data-testid="stMetric"] { border: 1px solid #62698c; border-radius: .7rem; padding: .75rem; }
.stCaption { color: #d5d7e6 !important; }
</style>
""", unsafe_allow_html=True)

st.title("UMBRA")
st.caption("See whether the sky is worth watching tonight—and what is limiting it.")
st.write(
    "Umbra models astronomical darkness, moonlight, weather, and artificial sky "
    "brightness to make light pollution visible and personal."
)
st.info("Built for OregonHacks: technology that helps people reconnect with nature and supports environmental health.")

with st.form("location_form"):
    query = st.text_input("Location", placeholder="Portland, Oregon")
    max_distance = st.slider("Maximum straight-line search distance", 25, 150, 100, 25, help="Road distance may be longer; verify access and conditions before traveling.")
    submitted = st.form_submit_button("Check tonight")

if submitted:
    if not query.strip():
        st.warning("Enter a city or place name.")
        st.stop()

    with st.spinner("Modeling tonight's sky…"):
        location, location_error = geocode_location(query)
    if location_error or location is None:
        st.error(location_error or "Location search failed.")
        st.stop()

    st.subheader(f"{location['name']}, {location['admin1'] or location['country']}")
    try:
        local_zone = ZoneInfo(location["timezone"])
    except ZoneInfoNotFoundError:
        local_zone = timezone.utc
    forecast, forecast_error = fetch_forecast(location["lat"], location["lon"])
    centers, used_enrichment, population_message = fetch_population_centers(location["lat"], location["lon"])
    if population_message:
        st.info(population_message)

    brightness = artificial_brightness(location["lat"], location["lon"], centers)
    bortle = bortle_class(brightness)
    st.metric("Modeled Bortle class", f"{bortle} / 9")
    st.caption(bortle_description(bortle))
    st.caption("This is a modeled estimate, not a direct radiometric measurement.")

    expectations = visibility_expectations(bortle)
    st.subheader("What this sky reveals")
    st.write(f"**Likely visible:** {expectations['visible']}")
    st.write(f"**Hidden by skyglow:** {expectations['missing']}")

    if forecast_error or not forecast:
        st.warning(forecast_error or "No forecast hours were returned.")
        st.stop()

    for row in forecast:
        row["brightness_index"] = brightness

    now = datetime.now(timezone.utc)
    nearest = min(forecast, key=lambda row: abs((row["time"] - now).total_seconds()))
    current_score, subscores = compute_stargazing_score(
        nearest["cloud_cover"], brightness, moon_illumination(nearest["time"]),
        moon_altitude(nearest["time"], location["lat"], location["lon"]),
        nearest["visibility"], nearest["relative_humidity_2m"],
        dt_utc=now, lat=location["lat"], lon=location["lon"],
    )

    if current_score is None:
        dark_window = find_dark_window(now, location["lat"], location["lon"])
        st.warning("Not dark yet — the Sun is above astronomical twilight (−18°).")
        if dark_window:
            wait = dark_window[0] - now
            hours, remainder = divmod(max(0, int(wait.total_seconds())), 3600)
            minutes = remainder // 60
            st.write(f"Astronomical darkness begins in about {hours} hr {minutes} min.")
    else:
        st.metric("Stargazing score now", f"{current_score:.0f} / 100", score_label(current_score))
        st.write(limiting_factor(subscores))
        st.subheader("Score breakdown")
        for factor, value in subscores.items():
            st.write(f"{factor.replace('_', ' ').title()}: **{value:.0f} / 100**")

    best = find_best_window(forecast, location["lat"], location["lon"])
    st.subheader("Best viewing window")
    if best:
        local_start = best["start"].astimezone(local_zone)
        local_end = (best["end"] + timedelta(hours=1)).astimezone(local_zone)
        end = best["end"] + timedelta(hours=1)
        st.write(
            f"{local_start.strftime('%b %d, %I:%M %p')}–{local_end.strftime('%I:%M %p %Z')} "
            f"with a peak modeled score of **{best['best_score']:.0f}/100**."
        )
        timeline = pd.DataFrame({
            "Local time": [item["time"].astimezone(local_zone) for item in best["all_hours"]],
            "Stargazing score": [item["score"] for item in best["all_hours"]],
        }).set_index("Local time")
        st.line_chart(timeline, y="Stargazing score", color="#D8A7FF")
        st.caption(
            f"Timeline summary: the best modeled score is {best['best_score']:.0f}/100, "
            f"beginning near {local_start.strftime('%I:%M %p')} local time."
        )
    else:
        st.write("No astronomical-darkness window appears in the available forecast.")

    st.subheader("Best night this week")
    nights = summarize_nights(forecast, location["lat"], location["lon"], location["timezone"])
    if nights:
        best_night = max(nights, key=lambda night: night["score"])
        night_chart = pd.DataFrame({
            "Night": [night["date"].strftime("%a %b %d") for night in nights],
            "Best score": [night["score"] for night in nights],
        }).set_index("Night")
        st.bar_chart(night_chart, y="Best score", color="#F2B880")
        best_night_local = best_night["time"].astimezone(local_zone)
        st.caption(
            f"Weekly summary: {best_night_local.strftime('%A, %b %d')} is the strongest forecast night "
            f"with a peak score of {best_night['score']:.0f}/100 near {best_night_local.strftime('%I:%M %p')}."
        )
    else:
        best_night = None
        st.write("No astronomical darkness appears in the seven-day forecast.")

    st.subheader("Moon, planets, and meteors")
    observing_time = best["start"] if best else now
    illumination = moon_illumination(observing_time)
    phase = moon_phase_name(illumination, moon_is_waxing(observing_time))
    st.write(
        f"**Moon:** {phase}, {illumination * 100:.0f}% illuminated, "
        f"{moon_altitude(observing_time, location['lat'], location['lon']):.0f}° altitude at the selected observing time."
    )
    planets = visible_planets(observing_time, location["lat"], location["lon"])
    if planets:
        for planet in planets:
            st.write(
                f"**{planet['name']}:** {planet['altitude']:.0f}° above the horizon toward "
                f"{planet['direction']} (azimuth {planet['azimuth']:.0f}°)."
            )
    else:
        st.write("No naked-eye planet is modeled above 10° at the selected observing time.")
    st.caption("Planet positions are low-precision orbital-element estimates; terrain and buildings are not modeled.")

    meteors = meteor_activity(observing_time.astimezone(local_zone))
    if meteors["active"]:
        for shower in meteors["active"]:
            st.write(
                f"**Active meteor shower:** {shower['name']} — nominal peak "
                f"{shower['peak_date'].strftime('%b %d')}, ideal maximum about {shower['zhr']} meteors/hour under perfect dark skies."
            )
    elif meteors["upcoming"]:
        shower = meteors["upcoming"][0]
        st.write(f"**Next major shower:** {shower['name']} peaks {shower['peak_date'].strftime('%b %d')}.")
    else:
        st.write("No major annual meteor shower is active or near peak in the next 45 days.")

    air_quality, air_error = fetch_air_quality(location["lat"], location["lon"])
    st.subheader("Haze and aerosols")
    if air_quality:
        nearest_air = min(air_quality, key=lambda row: abs((row["time"] - now).total_seconds()))
        pm_value = nearest_air["pm2_5"]
        aerosol = nearest_air["aerosol_optical_depth"]
        aerosol_text = f" and aerosol optical depth {aerosol:.2f}" if aerosol is not None else ""
        st.write(f"Forecast PM2.5 is **{pm_value:.1f} µg/m³**{aerosol_text}. Lower values generally mean clearer skies.")
    else:
        st.info(air_error or "Air-quality detail is unavailable; forecast visibility remains the haze proxy.")

    st.subheader("Darkest modeled sites nearby")
    sites = find_dark_sites(location["lat"], location["lon"], centers, max_distance, 8)
    if sites:
        map_rows = [{
            **site,
            "marker": "Dark-site candidate",
            "color": [216, 167, 255, 220],
        } for site in sites]
        map_rows.append({
            "name": location["name"], "lat": location["lat"], "lon": location["lon"],
            "bortle": bortle, "distance_km": 0, "darkness_score": 0,
            "marker": "Your location", "kind": "Starting point", "color": [255, 190, 92, 255],
        })
        layer = pdk.Layer(
            "ScatterplotLayer", map_rows, get_position="[lon, lat]", get_fill_color="color",
            get_radius=3500, pickable=True, radius_min_pixels=7,
        )
        view = pdk.ViewState(latitude=location["lat"], longitude=location["lon"], zoom=7)
        deck = pdk.Deck(
            layers=[layer], initial_view_state=view,
            tooltip={"html": "<b>{name}</b><br/>{marker}<br/>Bortle {bortle}<br/>{distance_km} km straight-line"},
            map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
        )
        st.pydeck_chart(deck, width="stretch")
        st.caption(
            f"Map summary: {sites[0]['name']} is the darkest top-ranked candidate, "
            f"{sites[0]['distance_km']:.0f} km away with modeled Bortle class {sites[0]['bortle']}. "
            "Purple markers are candidates; the gold marker is your starting location."
        )
        for index, site in enumerate(sites, 1):
            st.markdown(
                f"**{index}. {site['name']} — Bortle {site['bortle']}**  \n"
                f"{site['distance_km']:.1f} km straight-line · Darkness {site['darkness_score']:.0f}/100 · "
                f"{site['kind']} · `{site['lat']:.4f}, {site['lon']:.4f}`"
            )
        st.warning("These are modeled grid candidates, not verified observing sites. Check road access, closures, weather, and land rules before traveling.")
    else:
        st.write("No candidate sites were found within that distance.")

    st.subheader("Take this plan with you")
    best_window_text = (
        f"{best['start'].astimezone(local_zone).strftime('%b %d, %I:%M %p')}–"
        f"{(best['end'] + timedelta(hours=1)).astimezone(local_zone).strftime('%I:%M %p %Z')}"
        if best else "No astronomical-darkness window in the forecast"
    )
    top_site_text = (
        f"{sites[0]['name']} ({sites[0]['distance_km']:.1f} km straight-line, Bortle {sites[0]['bortle']})"
        if sites else "No modeled candidate"
    )
    score_text = f"{current_score:.0f}/100 ({score_label(current_score)})" if current_score is not None else "Not dark yet"
    summary_card = f"""# Umbra night-sky plan

**Location:** {location['name']}, {location['admin1'] or location['country']}
**Current state:** {score_text}
**Modeled local sky:** Bortle {bortle}/9
**Best viewing window:** {best_window_text}
**Moon:** {phase}, {illumination * 100:.0f}% illuminated
**Top nearby candidate:** {top_site_text}
**Biggest factor:** {limiting_factor(subscores) if current_score is not None else 'Astronomical darkness has not begun'}

Modeled planning estimate from Umbra. Verify weather, access, closures, and land rules before traveling.
"""
    st.download_button(
        "Download night-sky plan",
        summary_card,
        file_name=f"umbra-{location['name'].lower().replace(' ', '-')}.md",
        mime="text/markdown",
    )
