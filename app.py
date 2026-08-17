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
from data_sources import fetch_air_quality, fetch_forecast, fetch_population_centers, geocode_location, geocode_search
from interpretations import (
    interpret_aerosol,
    interpret_bortle,
    interpret_clouds,
    interpret_component,
    interpret_darkness_window,
    interpret_distance,
    interpret_moon,
    interpret_score,
    visibility_snapshot,
)
from light_pollution import artificial_brightness, bortle_class, visibility_expectations
from meteor_showers import meteor_activity
from scoring import (
    build_score_timeline,
    compute_stargazing_score,
    find_best_window,
    hourly_data_covers_window,
    limiting_factor,
    normalize_hourly_data,
    score_label,
    summarize_nights,
)
from units import default_unit_system, distance_to_km, format_distance

st.set_page_config(page_title="Umbra", page_icon="🌘", layout="centered")

st.markdown("""
<style>
div[data-testid="stMetric"] { border: 1px solid #62698c; border-radius: .7rem; padding: .75rem; }
.stCaption { color: #d5d7e6 !important; }
</style>
""", unsafe_allow_html=True)

st.title("UMBRA")
st.caption(
    "See whether the sky is worth watching tonight—and what is limiting it. "
    "Built for OregonHacks to help people reconnect with nature and support environmental health."
)

with st.form("location_form"):
    search_columns = st.columns([5, 1])
    with search_columns[0]:
        query = st.text_input("Location", placeholder="Portland, Oregon", key="location_query")
    with search_columns[1]:
        submitted = st.form_submit_button("Check tonight")

if submitted:
    if not query.strip():
        st.session_state["umbra_matches"] = []
        st.session_state["umbra_search_error"] = None
        st.warning("Enter a city or place name.")
    else:
        with st.spinner("Finding matching locations…"):
            matches = geocode_search(query)
            location_error = None
            if not matches:
                # Preserve the original single-result path as a non-breaking fallback.
                legacy, location_error = geocode_location(query)
                if legacy is not None:
                    matches = [{
                        "name": legacy["name"], "admin1": legacy.get("admin1", ""),
                        "country": legacy.get("country", ""), "country_code": legacy.get("country_code", ""),
                        "latitude": legacy["lat"], "longitude": legacy["lon"],
                        "timezone": legacy.get("timezone", "UTC"),
                        "display_label": ", ".join(
                            str(part).strip() for part in (legacy["name"], legacy.get("admin1"), legacy.get("country"))
                            if part is not None and str(part).strip()
                        ),
                    }]
            st.session_state["umbra_matches"] = matches
            st.session_state["umbra_search_error"] = location_error if not matches else None
            if matches:
                st.session_state["location_choice"] = matches[0]["display_label"]

matches = st.session_state.get("umbra_matches", [])
search_error = st.session_state.get("umbra_search_error")
if search_error:
    st.error(search_error)

selected_match = None
if len(matches) == 1:
    selected_match = matches[0]
    st.session_state.pop("location_choice", None)
elif len(matches) >= 2:
    labels = [match["display_label"] for match in matches]
    if st.session_state.get("location_choice") not in labels:
        st.session_state["location_choice"] = labels[0]
    selected_label = st.selectbox(
        "Which location did you mean?",
        labels,
        key="location_choice",
    )
    selected_match = next(match for match in matches if match["display_label"] == selected_label)

if selected_match is not None:
    location = {
        "name": selected_match["name"], "admin1": selected_match.get("admin1", ""),
        "country": selected_match.get("country", ""), "country_code": selected_match.get("country_code", ""),
        "lat": selected_match["latitude"], "lon": selected_match["longitude"],
        "timezone": selected_match.get("timezone", "UTC"),
    }
    country_code = location["country_code"].upper()
    if st.session_state.get("unit_country_code") != country_code:
        st.session_state["unit_system"] = default_unit_system(country_code)
        st.session_state["unit_country_code"] = country_code
    settings_columns = st.columns([2, 1])
    with settings_columns[1]:
        unit_system = st.radio(
            "Distance units",
            ["Metric (km)", "Imperial (mi)"],
            key="unit_system",
            horizontal=True,
        )
    with settings_columns[0]:
        if unit_system == "Imperial (mi)":
            distance_value = st.slider(
                "Maximum straight-line search distance (miles)", 15, 95, 60, 10,
                key="max_distance_imperial",
                help="Road distance may be longer; verify access and conditions before traveling.",
            )
        else:
            distance_value = st.slider(
                "Maximum straight-line search distance (km)", 25, 150, 100, 25,
                key="max_distance_metric",
                help="Road distance may be longer; verify access and conditions before traveling.",
            )
    max_distance_km = distance_to_km(distance_value, unit_system)

if selected_match is not None:
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
    expectations = visibility_expectations(bortle)

    if forecast_error or not forecast:
        st.metric("Modeled Bortle class", f"{bortle} / 9")
        st.caption(interpret_bortle(bortle))
        st.caption("This is a modeled estimate, not a direct radiometric measurement.")
        st.subheader("What this sky reveals")
        st.write(f"**Likely visible:** {expectations['visible']}")
        st.write(f"**Hidden by skyglow:** {expectations['missing']}")
        st.warning(forecast_error or "No forecast hours were returned.")
        st.stop()

    forecast = normalize_hourly_data(forecast)
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
        st.warning("Not dark yet — twilight is still hiding faint stars.")
        if dark_window:
            wait = dark_window[0] - now
            hours, remainder = divmod(max(0, int(wait.total_seconds())), 3600)
            minutes = remainder // 60
            st.write(f"Astronomical darkness begins in about {hours} hr {minutes} min.")
    else:
        st.metric("Stargazing score now", f"{current_score:.0f} / 100", score_label(current_score))
        st.caption(interpret_score(current_score))
        st.write(limiting_factor(subscores))
        st.subheader("Score breakdown")
        st.write(f"Cloud cover: **{nearest['cloud_cover']:.0f}%**")
        st.caption(interpret_clouds(nearest["cloud_cover"]))
        for factor, value in subscores.items():
            st.write(f"{factor.replace('_', ' ').title()} contribution: **{value:.0f} / 100**")
            st.caption(interpret_component(factor, value))

    st.metric("Modeled Bortle class", f"{bortle} / 9")
    st.caption(interpret_bortle(bortle))
    st.caption("This is a modeled estimate, not a direct radiometric measurement.")

    current_hour = now.replace(minute=0, second=0, microsecond=0)
    upcoming_forecast = [row for row in forecast if row["time"] >= current_hour]
    nights = summarize_nights(upcoming_forecast, location["lat"], location["lon"], location["timezone"])[:7]
    night_labels = [night["date"].strftime("%a, %b %d") for night in nights]
    night_location_key = selected_match["display_label"]
    if (
        st.session_state.get("night_location_key") != night_location_key
        or st.session_state.get("selected_night") not in night_labels
    ):
        st.session_state["night_location_key"] = night_location_key
        st.session_state["selected_night"] = night_labels[0] if night_labels else None

    selected_night_label = st.session_state.get("selected_night")
    selected_date = (
        nights[night_labels.index(selected_night_label)]["date"]
        if selected_night_label in night_labels else None
    )
    selected_forecast = [
        row for row in upcoming_forecast
        if selected_date is not None
        and (row["time"].astimezone(local_zone) - timedelta(hours=12)).date() == selected_date
    ]
    selected_dark_window = None
    if selected_date is not None:
        selected_noon = datetime.combine(selected_date, datetime.min.time(), tzinfo=local_zone) + timedelta(hours=12)
        selected_dark_window = find_dark_window(
            selected_noon.astimezone(timezone.utc), location["lat"], location["lon"], 30
        )
    coverage_start = current_hour if selected_night_label == night_labels[0] else None
    complete_dark_window = hourly_data_covers_window(
        selected_forecast, selected_dark_window, not_before=coverage_start
    )
    best = find_best_window(selected_forecast, location["lat"], location["lon"]) if complete_dark_window else {}
    chart_a_title = "Tonight" if not night_labels or selected_night_label == night_labels[0] else f"Selected night — {selected_night_label}"
    st.subheader(chart_a_title)
    if not complete_dark_window:
        st.warning(
            "The forecast does not cover this night’s full remaining astronomical-darkness window, "
            "so Umbra will not report a best window from partial data."
        )
    elif best:
        local_start = best["start"].astimezone(local_zone)
        local_end = (best["end"] + timedelta(hours=1)).astimezone(local_zone)
        if selected_dark_window is not None:
            darkness_start = selected_dark_window[0].astimezone(local_zone)
            darkness_end = selected_dark_window[1].astimezone(local_zone)
            st.caption(interpret_darkness_window(darkness_start, darkness_end))
        st.write(
            f"Best viewing window: {local_start.strftime('%b %d, %I:%M %p')}–{local_end.strftime('%I:%M %p %Z')} "
            f"with a peak modeled score of **{best['best_score']:.0f}/100** — {interpret_score(best['best_score'])}"
        )
        timeline_rows = []
        for item in build_score_timeline(selected_forecast, location["lat"], location["lon"]):
            local_time = item["time"].astimezone(local_zone)
            timeline_rows.append({
                "Local time": local_time,
                "Interval end": local_time + timedelta(hours=1),
                "Stargazing score": item["score"],
                "Night segment": item["segment"],
                "Best window": best["start"] <= item["time"] <= best["end"],
            })
        timeline = pd.DataFrame(timeline_rows).sort_values("Local time").drop_duplicates("Local time")
        st.vega_lite_chart(timeline, {
            "padding": {"left": 25, "right": 10, "top": 10, "bottom": 20},
            "layer": [
                {
                    "transform": [{"filter": "datum['Best window'] === true"}],
                    "mark": {"type": "rect", "color": "#F2B880", "opacity": 0.18},
                    "encoding": {
                        "x": {"field": "Local time", "type": "temporal"},
                        "x2": {"field": "Interval end"},
                    },
                },
                {
                    "transform": [{"filter": "isValid(datum['Stargazing score'])"}],
                    "mark": {"type": "line", "color": "#D8A7FF", "point": True},
                    "encoding": {
                        "x": {
                            "field": "Local time", "type": "temporal", "title": "Local date and time",
                            "axis": {"format": "%b %d, %I %p", "labelAngle": -35, "labelOverlap": "greedy"},
                        },
                        "y": {
                            "field": "Stargazing score", "type": "quantitative", "title": "Stargazing score (0–100)",
                            "scale": {"domain": [0, 100], "clamp": True, "nice": False},
                            "axis": {"titlePadding": 14},
                        },
                        "detail": {"field": "Night segment", "type": "nominal"},
                        "tooltip": [
                            {"field": "Local time", "type": "temporal", "title": "Local time", "format": "%b %d, %I:%M %p"},
                            {"field": "Stargazing score", "type": "quantitative", "title": "Score", "format": ".0f"},
                        ],
                    },
                },
            ],
        }, width="stretch")
        summary_prefix = "Best window tonight" if selected_night_label == night_labels[0] else f"Best window {selected_night_label}"
        peak_hour = max(best["hours"], key=lambda item: item["score"])
        limitation = limiting_factor(peak_hour["subscores"])
        st.caption(
            f"{summary_prefix}: conditions peak from {local_start.strftime('%I:%M %p')}–{local_end.strftime('%I:%M %p')} "
            f"at {best['best_score']:.0f}/100; {limitation[0].lower() + limitation[1:]}"
        )
        st.caption(
            "Legend: the line is the hourly stargazing score; the highlighted band is the best window; "
            "gaps are daylight, when no score is calculated."
        )
        st.caption("Scale: 85–100 Excellent · 70–84 Good · 50–69 Fair · 30–49 Poor · below 30 Don’t bother.")
    else:
        st.info("No astronomical darkness occurs for this location on the selected night.")

    st.subheader("Next 7 nights")
    if nights:
        best_night = max(nights, key=lambda night: night["score"])
        night_chart = pd.DataFrame({
            "Night": night_labels,
            "Best score": [night["score"] for night in nights],
            "Selected": [label == selected_night_label for label in night_labels],
        })
        st.vega_lite_chart(night_chart, {
            "padding": {"left": 20, "right": 10, "top": 5, "bottom": 10},
            "mark": {"type": "bar", "cornerRadiusTopLeft": 4, "cornerRadiusTopRight": 4},
            "encoding": {
                "x": {"field": "Night", "type": "nominal", "sort": night_labels, "title": "Observing night", "axis": {"labelAngle": -30}},
                "y": {"field": "Best score", "type": "quantitative", "title": "Peak score", "scale": {"domain": [0, 100], "nice": False}, "axis": {"titlePadding": 12}},
                "color": {
                    "condition": {"test": "datum.Selected === true", "value": "#F2B880"},
                    "value": "#777FA3",
                    "legend": None,
                },
                "tooltip": [
                    {"field": "Night", "type": "nominal", "title": "Night"},
                    {"field": "Best score", "type": "quantitative", "title": "Peak score", "format": ".0f"},
                ],
            },
        }, width="stretch")
        best_night_local = best_night["time"].astimezone(local_zone)
        st.caption(
            f"Seven-night summary: {best_night_local.strftime('%A, %b %d')} is strongest at "
            f"{best_night['score']:.0f}/100 — {interpret_score(best_night['score'])} "
            f"{selected_night_label} is selected for the detailed chart above."
        )
        st.selectbox("Choose a night to inspect", night_labels, key="selected_night")
    else:
        best_night = None
        st.info("No astronomical darkness appears in the next seven nights, so no nightly chart is shown.")

    st.subheader("What you can see tonight")
    observing_time = best["start"] if best else now
    illumination = moon_illumination(observing_time)
    phase = moon_phase_name(illumination, moon_is_waxing(observing_time))
    selected_moon_altitude = moon_altitude(observing_time, location["lat"], location["lon"])
    st.write(
        f"**Moon:** {phase}, {illumination * 100:.0f}% illuminated, "
        f"{selected_moon_altitude:.0f}° altitude at the selected observing time."
    )
    st.caption(interpret_moon(illumination, selected_moon_altitude))
    planets = visible_planets(observing_time, location["lat"], location["lon"])
    meteors = meteor_activity(observing_time.astimezone(local_zone))
    observing_weather = min(forecast, key=lambda row: abs((row["time"] - observing_time).total_seconds()))
    visibility = visibility_snapshot(
        bortle, illumination, selected_moon_altitude, observing_weather["cloud_cover"],
        [planet["name"] for planet in planets], meteors["active"],
    )
    st.write(f"**Milky Way:** {visibility['milky_way']}")
    st.write(f"**Naked-eye planets:** {visibility['planets']}")
    st.write(f"**Meteor showers:** {visibility['meteors']}")
    st.write(f"**Deep-sky objects:** {visibility['deep_sky']}")
    st.write(f"**Faintest stars:** {visibility['limiting_magnitude']}")
    st.info(visibility["loss"])
    st.caption("Planet positions are low-precision estimates; terrain and buildings are not modeled.")

    air_quality, air_error = fetch_air_quality(location["lat"], location["lon"])
    st.subheader("Haze and aerosols")
    if air_quality:
        nearest_air = min(air_quality, key=lambda row: abs((row["time"] - now).total_seconds()))
        pm_value = nearest_air["pm2_5"]
        aerosol = nearest_air["aerosol_optical_depth"]
        aerosol_text = f" and aerosol optical depth {aerosol:.2f}" if aerosol is not None else ""
        st.write(f"Forecast PM2.5 is **{pm_value:.1f} µg/m³**{aerosol_text}. Lower values generally mean clearer skies.")
        st.caption(interpret_aerosol(aerosol, pm_value))
    else:
        st.info(air_error or "Air-quality detail is unavailable; forecast visibility remains the haze proxy.")

    st.subheader("Real dark-site candidates nearby")
    dark_site_sort = st.selectbox(
        "Sort dark-site candidates by",
        ["Best balance", "Darkest sky", "Shortest trip"],
        key="dark_site_sort",
    )
    sites = find_dark_sites(
        location["lat"], location["lon"], centers, max_distance_km, 8, sort_by=dark_site_sort
    )
    if sites:
        map_rows = [{
            **site,
            "distance_display": format_distance(site["distance_km"], unit_system),
            "bortle_meaning": interpret_bortle(site["bortle"]),
            "marker": "Dark-site candidate",
            "color": [216, 167, 255, 220],
        } for site in sites]
        map_rows.append({
            "name": location["name"], "lat": location["lat"], "lon": location["lon"],
            "bortle": bortle, "distance_km": 0, "darkness_score": 0,
            "distance_display": format_distance(0, unit_system),
            "bortle_meaning": interpret_bortle(bortle),
            "marker": "Your location", "kind": "Starting point", "color": [255, 190, 92, 255],
        })
        layer = pdk.Layer(
            "ScatterplotLayer", map_rows, get_position="[lon, lat]", get_fill_color="color",
            get_radius=3500, pickable=True, radius_min_pixels=7,
        )
        view = pdk.ViewState(latitude=location["lat"], longitude=location["lon"], zoom=7)
        deck = pdk.Deck(
            layers=[layer], initial_view_state=view,
            tooltip={"html": "<b>{name}</b><br/>{marker}<br/>{bortle_meaning}<br/>{distance_display} straight-line"},
            map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
        )
        st.pydeck_chart(deck, width="stretch")
        st.caption(
            f"Map summary: {sites[0]['name']} ranks first by {dark_site_sort.lower()}, "
            f"{interpret_distance(sites[0]['distance_km'], unit_system)} {interpret_bortle(sites[0]['bortle'])} "
            "Purple markers are candidates; the gold marker is your starting location."
        )
        st.write(
            f"**Starting location (gold marker):** {location['name']} — {interpret_bortle(bortle)} · "
            f"{format_distance(0, unit_system)} straight-line · "
            f"`{location['lat']:.4f}, {location['lon']:.4f}`"
        )
        for index, site in enumerate(sites, 1):
            st.markdown(
                f"**{index}. {site['name']}**  \n"
                f"{interpret_distance(site['distance_km'], unit_system)}  \n"
                f"{interpret_bortle(site['bortle'])}  \n"
                f"Darkness {site['darkness_score']:.0f}/100 — "
                f"{interpret_component('light_pollution', site['darkness_score'])} · {site['kind']} · "
                f"`{site['lat']:.4f}, {site['lon']:.4f}`"
            )
        st.warning(
            "These are real named populated places, but not verified observing sites. "
            "Check public access, closures, weather, and local rules before traveling."
        )
    else:
        st.write(
            "No verified populated-place candidates were found within that distance. "
            "Umbra does not show unverified grid coordinates."
        )

    st.subheader("Take this plan with you")
    best_window_text = (
        f"{best['start'].astimezone(local_zone).strftime('%b %d, %I:%M %p')}–"
        f"{(best['end'] + timedelta(hours=1)).astimezone(local_zone).strftime('%I:%M %p %Z')}"
        if best else "No astronomical-darkness window in the forecast"
    )
    top_site_text = (
        f"{sites[0]['name']} ({format_distance(sites[0]['distance_km'], unit_system)} straight-line, Bortle {sites[0]['bortle']})"
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
