"""Accessible Streamlit interface for the complete Midnight experience."""

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
from dark_sites import distance_km, find_dark_sites, find_hybrid_dark_sites, google_maps_url, is_darker_than_start
from data_sources import confirm_land_by_elevation, enrich_dark_sites_with_osm, fetch_air_quality, fetch_forecast, fetch_population_centers, geocode_location, geocode_search
from interpretations import (
    interpret_aerosol,
    interpret_bortle,
    interpret_bortle_improvement,
    interpret_cloud_layers,
    interpret_clouds,
    interpret_component,
    interpret_darkness_window,
    interpret_distance,
    interpret_fog,
    interpret_moon,
    interpret_no_darker_sites,
    interpret_score,
    interpret_smoke,
    visibility_snapshot,
    estimated_dark_sky_distance_km,
)
from light_pollution import artificial_brightness, bortle_class, darkness_score, visibility_expectations
from meteor_showers import meteor_activity
from scoring import (
    build_score_timeline,
    compute_stargazing_score,
    find_best_window,
    hourly_data_covers_window,
    is_flat_night,
    limiting_factor,
    normalize_hourly_data,
    precompute_night_views,
    score_label,
    summarize_nights,
)
from units import default_unit_system, distance_to_km, format_distance

st.set_page_config(page_title="Midnight", page_icon="🌌", layout="centered")

st.markdown("""
<style>
div[data-testid="stMetric"] { border: 1px solid #62698c; border-radius: .7rem; padding: .75rem; }
.stCaption { color: #d5d7e6 !important; }
</style>
""", unsafe_allow_html=True)

st.title("MIDNIGHT")
st.caption(
    "See whether the sky is worth watching tonight—and what is limiting it. "
    "Built for the world to help people reconnect with nature and support environmental health."
)

with st.form("location_form"):
    search_columns = st.columns([5, 1])
    with search_columns[0]:
        query = st.text_input("Location", placeholder="Portland, Oregon", key="location_query")
    with search_columns[1]:
        submitted = st.form_submit_button("Check tonight")

if submitted:
    if not query.strip():
        st.session_state["midnight_matches"] = []
        st.session_state["midnight_search_error"] = None
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
            st.session_state["midnight_matches"] = matches
            st.session_state["midnight_search_error"] = location_error if not matches else None
            if matches:
                st.session_state["location_choice"] = matches[0]["display_label"]

matches = st.session_state.get("midnight_matches", [])
search_error = st.session_state.get("midnight_search_error")
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
    if (
        st.session_state.get("unit_country_code") != country_code
        or "unit_system" not in st.session_state
    ):
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
        st.caption(
            "Estimated from population density using Walker's Law. This cannot account for local "
            "lighting ordinances — communities with dark-sky policies, like Flagstaff, are darker "
            "than this model predicts."
        )
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
    st.caption(
        "Estimated from population density using Walker's Law. This cannot account for local "
        "lighting ordinances — communities with dark-sky policies, like Flagstaff, are darker "
        "than this model predicts."
    )

    current_hour = now.replace(minute=0, second=0, microsecond=0)
    night_location_key = selected_match["display_label"]
    night_views = precompute_night_views(
        night_location_key, location["lat"], location["lon"], location["timezone"],
        current_hour, forecast,
    )
    nights = [view["summary"] for view in night_views]
    night_labels = [view["label"] for view in night_views]
    if (
        st.session_state.get("night_location_key") != night_location_key
        or st.session_state.get("selected_night") not in night_labels
    ):
        st.session_state["night_location_key"] = night_location_key
        st.session_state["selected_night"] = night_labels[0] if night_labels else None

    selected_night_label = (
        st.selectbox("Choose a night to inspect", night_labels, key="selected_night")
        if night_labels else None
    )
    selected_view = next(
        (view for view in night_views if view["label"] == selected_night_label),
        None,
    )
    selected_date = selected_view["date"] if selected_view is not None else None
    selected_dark_window = selected_view["dark_window"] if selected_view is not None else None
    selected_forecast = selected_view["forecast"] if selected_view is not None else []
    complete_dark_window = selected_view["complete"] if selected_view is not None else False
    best = selected_view["best"] if selected_view is not None else {}
    chart_a_title = (
        f"Tonight — {selected_night_label}"
        if night_labels and selected_night_label == night_labels[0]
        else f"Selected night — {selected_night_label}"
    )
    st.subheader(chart_a_title)
    flat_night = False
    if not complete_dark_window:
        st.warning(
            "The forecast does not cover this night’s full astronomical-darkness window, "
            "so Midnight will not report a best window from partial data."
        )
    elif best:
        local_start = best["start"].astimezone(local_zone)
        local_end = best["end"].astimezone(local_zone)
        night_scores = [item["score"] for item in best["all_hours"]]
        score_min = min(night_scores)
        score_max = max(night_scores)
        flat_night = is_flat_night(night_scores)
        selected_period = "tonight" if selected_night_label == night_labels[0] else "that night"
        if selected_dark_window is not None:
            darkness_start = selected_dark_window[0].astimezone(local_zone)
            darkness_end = selected_dark_window[1].astimezone(local_zone)
            st.caption(interpret_darkness_window(darkness_start, darkness_end))
            chart_edge_padding = timedelta(minutes=10)
            chart_time_domain = [
                (darkness_start - chart_edge_padding).isoformat(),
                (darkness_end + chart_edge_padding).isoformat(),
            ]
        if flat_night:
            st.write(
                f"Conditions barely change {selected_period} ({score_min:.0f}–{score_max:.0f}). "
                "Any time in the darkness window works equally well."
            )
        else:
            st.write(
                f"Best viewing window: {local_start.strftime('%b %d, %I:%M %p')}–{local_end.strftime('%I:%M %p %Z')} "
                f"with a peak modeled score of **{best['best_score']:.0f}/100** — {interpret_score(best['best_score'])}"
            )
        timeline_rows = []
        for item in selected_view["timeline"]:
            local_time = item["time"].astimezone(local_zone)
            interval_end = min(item["time"] + timedelta(hours=1), selected_dark_window[1])
            timeline_rows.append({
                "Local time": local_time,
                "Exact time": local_time.strftime("%b %d, %I:%M %p %Z").replace(" 0", " "),
                "Interval end": interval_end.astimezone(local_zone),
                "Stargazing score": item["score"],
                "Limited by": f"limited by {item['limiting_factor']}",
                "Night segment": item["segment"],
                "Best window": (
                    not flat_night
                    and item["time"] < best["end"]
                    and interval_end > best["start"]
                ),
                "Point type": "Forecast",
            })
        for boundary in selected_dark_window:
            boundary_local = boundary.astimezone(local_zone)
            timeline_rows.append({
                "Local time": boundary_local, "Interval end": boundary_local,
                "Exact time": boundary_local.strftime("%b %d, %I:%M %p %Z").replace(" 0", " "),
                "Stargazing score": None, "Limited by": None, "Night segment": None,
                "Best window": False, "Point type": "Darkness boundary",
            })
        if selected_night_label == night_labels[0] and selected_dark_window[0] <= now <= selected_dark_window[1]:
            now_local = now.astimezone(local_zone)
            timeline_rows.append({
                "Local time": now_local, "Interval end": now_local,
                "Exact time": now_local.strftime("%b %d, %I:%M %p %Z").replace(" 0", " "),
                "Stargazing score": None, "Limited by": None, "Night segment": None,
                "Best window": False, "Point type": "Current time",
            })
        timeline = pd.DataFrame(timeline_rows).sort_values("Local time").drop_duplicates("Local time")
        st.vega_lite_chart(timeline, {
            "height": 370,
            "padding": {"left": 25, "right": 10, "top": 10, "bottom": 55},
            "layer": [
                {
                    "transform": [{"filter": "datum['Best window'] === true"}],
                    "mark": {"type": "rect", "color": "#F2B880", "opacity": 0.18, "clip": True},
                    "encoding": {
                        "x": {"field": "Local time", "type": "temporal"},
                        "x2": {"field": "Interval end"},
                        "y": {"datum": 0},
                        "y2": {"datum": 100},
                    },
                },
                {
                    "transform": [{"filter": "isValid(datum['Stargazing score'])"}],
                    "mark": {
                        "type": "line", "color": "#D8A7FF", "strokeWidth": 2.5,
                        "interpolate": "monotone", "clip": True,
                        "point": {"filled": True, "size": 48, "color": "#83D5FF"},
                    },
                    "encoding": {
                        "x": {
                            "field": "Local time", "type": "temporal", "title": "Local date and time",
                            "scale": {"domain": chart_time_domain},
                            "axis": {
                                "format": "%b %d, %I:%M %p", "labelAngle": -35,
                                "labelOverlap": "greedy", "tickCount": 7,
                                "titlePadding": 18,
                            },
                        },
                        "y": {
                            "field": "Stargazing score", "type": "quantitative", "title": "Stargazing score (0–100)",
                            "scale": {"domain": [0, 100], "clamp": True, "nice": False},
                            "axis": {"titlePadding": 14, "values": [0, 20, 40, 60, 80, 100]},
                        },
                        "detail": {"field": "Night segment", "type": "nominal"},
                        "tooltip": [
                            {"field": "Exact time", "type": "nominal", "title": "Time"},
                            {"field": "Stargazing score", "type": "quantitative", "title": "Score", "format": ".1f"},
                            {"field": "Limited by", "type": "nominal", "title": "Limitation"},
                        ],
                    },
                },
                {
                    "transform": [{"filter": "datum['Point type'] === 'Darkness boundary'"}],
                    "mark": {"type": "rule", "color": "#777FA3", "strokeDash": [2, 4], "opacity": 0.55},
                    "encoding": {"x": {"field": "Local time", "type": "temporal"}},
                },
                {
                    "transform": [{"filter": "datum['Point type'] === 'Current time'"}],
                    "mark": {
                        "type": "rule", "color": "#F2B880", "strokeDash": [5, 4],
                        "size": 2, "clip": True,
                    },
                    "encoding": {
                        "x": {"field": "Local time", "type": "temporal"},
                        "y": {"datum": 0},
                        "y2": {"datum": 100},
                        "tooltip": [{"field": "Local time", "type": "temporal", "title": "Current time", "format": "%I:%M %p"}],
                    },
                },
            ],
        }, width="stretch", height=370, key=f"detailed-night-{night_location_key}-{selected_date.isoformat()}")
        summary_prefix = "Best window tonight" if selected_night_label == night_labels[0] else f"Best window {selected_night_label}"
        peak_hour = max(best["hours"], key=lambda item: item["score"])
        limitation_period = "tonight" if selected_night_label == night_labels[0] else "that night"
        limitation = limiting_factor(peak_hour["subscores"], limitation_period)
        if flat_night:
            st.caption(
                f"The modeled score stays between {score_min:.0f} and {score_max:.0f} {selected_period}; "
                f"{limitation[0].lower() + limitation[1:]}"
            )
        else:
            st.caption(
                f"{summary_prefix}: conditions peak from {local_start.strftime('%I:%M %p')}–{local_end.strftime('%I:%M %p')} "
                f"at {best['best_score']:.0f}/100; {limitation[0].lower() + limitation[1:]}"
            )
        if flat_night:
            st.caption("Legend: the line is the hourly stargazing score; no best-window band is shown because conditions are nearly constant.")
        else:
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

    st.subheader("Cloud layers, fog, and smoke")
    low_cloud = nearest.get("cloud_cover_low", nearest["cloud_cover"])
    mid_cloud = nearest.get("cloud_cover_mid", nearest["cloud_cover"])
    high_cloud = nearest.get("cloud_cover_high", nearest["cloud_cover"])
    st.write(
        f"Cloud layers: **{low_cloud:.0f}% low · {mid_cloud:.0f}% middle · {high_cloud:.0f}% high**"
    )
    st.caption(interpret_cloud_layers(low_cloud, mid_cloud, high_cloud))

    temperature = nearest.get("temperature_2m", 10.0)
    dew_point = nearest.get("dew_point_2m", temperature - 5.0)
    wind_speed = nearest.get("wind_speed_10m", 15.0)
    dew_point_spread = temperature - dew_point
    fog_likely, fog_meaning = interpret_fog(temperature, dew_point, wind_speed)
    st.write(
        f"Fog inputs: **{dew_point_spread:.1f}°C temperature–dew point spread · "
        f"{wind_speed:.1f} km/h wind**"
    )
    if fog_likely:
        st.warning(f"Fog risk: {fog_meaning}")
    else:
        st.caption(f"Fog risk: {fog_meaning}")

    air_quality, air_error = fetch_air_quality(location["lat"], location["lon"])
    if air_quality:
        nearest_air = min(air_quality, key=lambda row: abs((row["time"] - now).total_seconds()))
        pm_value = nearest_air["pm2_5"]
        aerosol = nearest_air["aerosol_optical_depth"]
        aerosol_text = f" and aerosol optical depth {aerosol:.2f}" if aerosol is not None else ""
        st.write(f"Forecast PM2.5 is **{pm_value:.1f} µg/m³**{aerosol_text}. Lower values generally mean clearer skies.")
        st.caption(interpret_aerosol(aerosol, pm_value))
        smoke_meaning = interpret_smoke(pm_value)
        if pm_value >= 25:
            st.warning(f"Smoke signal: {smoke_meaning}")
        else:
            st.caption(f"Smoke signal: {smoke_meaning}")
    else:
        st.info(air_error or "Air-quality detail is unavailable; forecast visibility remains the haze proxy.")

    st.subheader("Dark-sky candidates nearby")
    dark_site_sort = "Best balance"
    if bortle <= 4:
        sites = []
        osm_lookup_succeeded = False
    else:
        dark_site_sort = st.selectbox(
            "Sort dark-site candidates by",
            ["Best balance", "Darkest sky", "Shortest trip"],
            key="dark_site_sort",
        )
        grid_sites = find_hybrid_dark_sites(
            location["lat"], location["lon"], centers, brightness, max_distance_km, 40,
            sort_by=dark_site_sort, country_code=country_code,
        )
        sites, land_check_succeeded = confirm_land_by_elevation(grid_sites)
        if not land_check_succeeded:
            sites = find_dark_sites(
                location["lat"], location["lon"], centers, max_distance_km, 8,
                sort_by=dark_site_sort, country_code=country_code,
                starting_brightness_index=brightness,
            )
        sites = sites[:8]
        sites, osm_lookup_succeeded = enrich_dark_sites_with_osm(sites)
    for site in sites:
        site["distance_km"] = round(distance_km(location["lat"], location["lon"], site["lat"], site["lon"]), 1)
        site["brightness_index"] = artificial_brightness(site["lat"], site["lon"], centers)
        site["darkness_score"] = darkness_score(site["brightness_index"])
        site["darkness_gain"] = round(site["darkness_score"] - darkness_score(brightness), 1)
        site["darkness_gain_per_km"] = round(
            site["darkness_gain"] / max(5.0, site["distance_km"]), 3
        )
        site["bortle"] = bortle_class(site["brightness_index"])
        site["maps_url"] = google_maps_url(site["lat"], site["lon"])
        site["country"] = location["country"] if site.get("country_code") == country_code else site.get("country_code", "Unknown")
        if site.get("kind") == "Modeled land point":
            region = f", {site['region']}" if site.get("region") else ""
            site["name"] = (
                f"{format_distance(site['nearest_distance_km'], unit_system)} {site['direction']} "
                f"of {site['nearest_place']}{region}"
            )
    sites = [site for site in sites if is_darker_than_start(brightness, site["brightness_index"])]
    if sites:
        map_rows = [{
            **site,
            "distance_display": format_distance(site["distance_km"], unit_system),
            "bortle_meaning": interpret_bortle(site["bortle"]),
            "access_label": site["access_label"],
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
            tooltip={"html": "<b>{name}</b><br/>{marker}<br/>{bortle_meaning}<br/>{access_label}<br/>{distance_display} straight-line"},
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
        st.markdown(f"[Open starting location in Google Maps]({google_maps_url(location['lat'], location['lon'])})")
        if osm_lookup_succeeded:
            st.caption("A named public-access recreation feature was found near at least one dark-sky candidate.")
        else:
            st.caption("Each dark point is described relative to a nearby named place when no public park, trailhead, or viewpoint is available.")
        for index, site in enumerate(sites, 1):
            access_line = f"{site['access_label']}  \n" if site.get("access_label") else ""
            st.markdown(
                f"**{index}. {site['name']}**  \n"
                f"{site['country']}  \n"
                f"{interpret_distance(site['distance_km'], unit_system)}  \n"
                f"{interpret_bortle_improvement(bortle, site['bortle'])}  \n"
                f"{access_line}"
                f"Darkness {site['darkness_score']:.0f}/100 — "
                f"gain {site.get('darkness_gain', 0):.0f} points over your location · "
                f"{interpret_component('light_pollution', site['darkness_score'])} · "
                f"`{site['lat']:.4f}, {site['lon']:.4f}`  \n"
                f"[Open in Google Maps]({site['maps_url']})"
            )
    else:
        estimate = estimated_dark_sky_distance_km(bortle)
        guidance = interpret_no_darker_sites(
            bortle,
            format_distance(max_distance_km, unit_system),
            format_distance(estimate, unit_system) if estimate else None,
        )
        (st.success if bortle <= 4 else st.info)(guidance)

    st.subheader("Take this plan with you")
    if best and flat_night:
        best_window_text = "Any time during astronomical darkness; conditions are nearly constant"
    elif best:
        best_window_text = (
            f"{best['start'].astimezone(local_zone).strftime('%b %d, %I:%M %p')}–"
            f"{best['end'].astimezone(local_zone).strftime('%I:%M %p %Z')}"
        )
    else:
        best_window_text = "No astronomical-darkness window in the forecast"
    top_site_text = (
        f"{sites[0]['name']} ({format_distance(sites[0]['distance_km'], unit_system)} straight-line, Bortle {sites[0]['bortle']})"
        if sites else "No modeled candidate"
    )
    score_text = f"{current_score:.0f}/100 ({score_label(current_score)})" if current_score is not None else "Not dark yet"
    summary_card = f"""# Midnight night-sky plan

**Location:** {location['name']}, {location['admin1'] or location['country']}
**Current state:** {score_text}
**Modeled local sky:** Bortle {bortle}/9
**Best viewing window:** {best_window_text}
**Moon:** {phase}, {illumination * 100:.0f}% illuminated
**Top nearby candidate:** {top_site_text}
**Biggest factor:** {limiting_factor(subscores) if current_score is not None else 'Astronomical darkness has not begun'}

Modeled planning estimate from Midnight. Verify weather, access, closures, and land rules before traveling.
"""
    st.download_button(
        "Download night-sky plan",
        summary_card,
        file_name=f"midnight-{location['name'].lower().replace(' ', '-')}.md",
        mime="text/markdown",
    )
