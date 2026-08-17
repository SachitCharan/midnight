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
from dark_sites import distance_km, find_dark_sites, find_hybrid_dark_sites, google_maps_url, is_darker_than_start, rank_dark_site_candidates
from data_sources import confirm_land_by_elevation, enrich_dark_sites_with_osm, fetch_air_quality, fetch_forecast, fetch_population_centers, geocode_location, geocode_search
from interpretations import (
    interpret_aerosol,
    interpret_bortle,
    interpret_bortle_improvement,
    interpret_cloud_layers,
    interpret_clouds,
    interpret_component,
    interpret_darkness_change,
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
from starfield import inject_starfield
from units import default_unit_system, distance_to_km, format_distance

st.set_page_config(page_title="Midnight", page_icon="🌌", layout="centered")
inject_starfield()
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&display=swap');

:root {{
    --midnight-navy: #111629;
    --midnight-panel: #29304D;
    --midnight-gold: #F2B880;
    --midnight-ivory: #F7F5F0;
    --midnight-violet: #8E78C7;
    --midnight-border: rgba(151, 161, 205, 0.28);
}}

html, body, [class*="css"] {{ font-family: "Inter", sans-serif; }}
body {{ background: var(--midnight-navy); }}
[data-testid="stAppViewContainer"] {{
    background:
        radial-gradient(circle at 15% 10%, rgba(103, 82, 154, 0.16), transparent 34rem),
        radial-gradient(circle at 88% 28%, rgba(70, 91, 151, 0.12), transparent 32rem),
        linear-gradient(180deg, rgba(17, 22, 41, 0.80), rgba(17, 22, 41, 0.94));
}}
[data-testid="stAppViewContainer"] > .main {{ position: relative; z-index: 2; }}
[data-testid="stHeader"] {{ background: rgba(17, 22, 41, 0.72); backdrop-filter: blur(14px); }}
[data-testid="stToolbar"] {{ z-index: 5; }}
.block-container {{ max-width: 920px; padding-top: 2.2rem; padding-bottom: 6rem; }}

h1, h2, h3, .midnight-hero {{ font-family: "Space Grotesk", "Inter", sans-serif !important; }}
h3 {{
    margin-top: 2.4rem !important;
    letter-spacing: -0.025em;
}}
h3::before {{
    content: "";
    display: inline-block;
    width: 0.48em;
    height: 0.48em;
    margin-right: 0.55rem;
    border-radius: 2px;
    background: var(--midnight-gold);
    transform: rotate(45deg) translateY(-0.05em);
    box-shadow: 0 0 16px rgba(242, 184, 128, 0.5);
}}

.midnight-hero {{
    position: relative;
    overflow: hidden;
    padding: 3.35rem 3rem 3rem;
    margin: 0 0 1.6rem;
    border: 1px solid rgba(242, 184, 128, 0.24);
    border-radius: 28px;
    background:
        radial-gradient(circle at 78% 26%, rgba(242,184,128,0.18) 0 1px, transparent 2px),
        radial-gradient(circle at 68% 20%, rgba(247,245,240,0.45) 0 1px, transparent 2px),
        radial-gradient(circle at 88% 58%, rgba(247,245,240,0.35) 0 1px, transparent 2px),
        linear-gradient(155deg, rgba(23,29,54,0.96) 5%, rgba(65,53,102,0.88) 64%, rgba(161,102,91,0.46) 95%, rgba(242,184,128,0.54) 100%);
    box-shadow: 0 24px 65px rgba(2,5,18,0.38), inset 0 1px 0 rgba(255,255,255,0.05);
}}
.midnight-hero::after {{
    content: "";
    position: absolute;
    inset: auto 0 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, rgba(242,184,128,0.9), transparent);
}}
.midnight-eyebrow {{
    color: var(--midnight-gold);
    font: 600 0.73rem/1 "Inter", sans-serif;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    margin-bottom: 0.9rem;
}}
.midnight-hero h1 {{
    margin: 0;
    color: var(--midnight-ivory);
    font-size: clamp(3rem, 9vw, 5.6rem);
    line-height: 0.95;
    letter-spacing: -0.075em;
    text-shadow: 0 8px 34px rgba(4,7,22,0.5);
}}
.midnight-hero p {{
    max-width: 650px;
    margin: 1.25rem 0 0;
    color: rgba(247,245,240,0.82);
    font-size: 1.03rem;
    line-height: 1.7;
}}

div[data-testid="stForm"],
div[data-testid="stVerticalBlockBorderWrapper"],
div[data-testid="stMetric"],
div[data-testid="stVegaLiteChart"],
div[data-testid="stPydeckChart"] {{
    border: 1px solid var(--midnight-border) !important;
    border-radius: 20px !important;
    background: linear-gradient(145deg, rgba(41,48,77,0.78), rgba(23,29,53,0.72)) !important;
    box-shadow: 0 16px 42px rgba(3,6,20,0.22), inset 0 1px 0 rgba(255,255,255,0.035);
}}
div[data-testid="stForm"] {{ padding: 1.1rem 1.1rem 0.35rem; }}
div[data-testid="stMetric"] {{ padding: 1rem 1.15rem; }}
div[data-testid="stVegaLiteChart"], div[data-testid="stPydeckChart"] {{ padding: 0.45rem; overflow: hidden; }}

div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
div[data-testid="stTextInput"] input {{
    background: rgba(17,22,41,0.58) !important;
    border-color: rgba(151,161,205,0.26) !important;
    border-radius: 12px !important;
}}
div[data-baseweb="input"]:focus-within > div,
div[data-baseweb="select"]:focus-within > div {{
    border-color: rgba(242,184,128,0.75) !important;
    box-shadow: 0 0 0 3px rgba(242,184,128,0.10) !important;
}}
.stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {{
    border: 1px solid rgba(242,184,128,0.42) !important;
    border-radius: 12px !important;
    background: linear-gradient(135deg, rgba(242,184,128,0.96), rgba(202,132,116,0.94)) !important;
    color: #111629 !important;
    font-weight: 700 !important;
    box-shadow: 0 10px 25px rgba(2,5,18,0.22);
    transition: transform 160ms ease, box-shadow 160ms ease, filter 160ms ease;
}}
.stButton > button:hover, .stFormSubmitButton > button:hover, .stDownloadButton > button:hover {{
    transform: translateY(-2px);
    filter: brightness(1.05);
    box-shadow: 0 14px 32px rgba(242,184,128,0.16);
}}

div[data-baseweb="notification"], div[data-testid="stAlertContainer"] {{
    border-radius: 14px !important;
    border: 1px solid rgba(242,184,128,0.34) !important;
    box-shadow: 0 12px 28px rgba(2,5,18,0.18);
    overflow: hidden;
}}
div[data-baseweb="notification"] svg {{ color: var(--midnight-gold) !important; fill: var(--midnight-gold) !important; }}
[data-testid="stAlertContentInfo"] {{ background: rgba(61,72,119,0.68) !important; color: var(--midnight-ivory) !important; }}
[data-testid="stAlertContentWarning"] {{ background: rgba(115,82,70,0.68) !important; color: var(--midnight-ivory) !important; }}
[data-testid="stAlertContentError"] {{ background: rgba(92,55,82,0.78) !important; color: #F6D8D5 !important; }}
[data-testid="stAlertContentSuccess"] {{ background: rgba(63,87,91,0.72) !important; color: var(--midnight-ivory) !important; }}

.stCaption {{ color: #d5d7e6 !important; line-height: 1.55 !important; }}
hr {{ border-color: rgba(151,161,205,0.20) !important; }}
a {{ color: #F2B880 !important; text-underline-offset: 3px; }}

.midnight-score-card {{
    display: grid;
    grid-template-columns: minmax(240px, 0.9fr) minmax(220px, 1.1fr);
    align-items: center;
    gap: 1rem;
    margin: 0.4rem 0 1.35rem;
    padding: 1.2rem 1.5rem 1.1rem;
    border: 1px solid rgba(242,184,128,0.28);
    border-radius: 24px;
    background: linear-gradient(145deg, rgba(41,48,77,0.90), rgba(20,26,48,0.88));
    box-shadow: 0 20px 48px rgba(2,5,18,0.30), inset 0 1px 0 rgba(255,255,255,0.04);
}}
.midnight-score-kicker {{
    color: rgba(247,245,240,0.62);
    font-size: 0.76rem;
    font-weight: 600;
    letter-spacing: 0.13em;
    text-transform: uppercase;
}}
.midnight-score-label {{
    display: inline-flex;
    align-items: center;
    margin-top: 0.75rem;
    padding: 0.36rem 0.7rem;
    border: 1px solid rgba(242,184,128,0.34);
    border-radius: 999px;
    color: var(--midnight-gold);
    background: rgba(242,184,128,0.08);
    font-weight: 700;
    font-size: 0.88rem;
}}
.midnight-gauge {{ width: 100%; max-height: 185px; overflow: visible; }}
.gauge-score {{
    fill: var(--midnight-ivory);
    font: 700 3.1rem "Space Grotesk", sans-serif;
    letter-spacing: -0.05em;
}}
.gauge-total {{ fill: rgba(247,245,240,0.56); font: 600 0.8rem "Inter", sans-serif; letter-spacing: 0.12em; }}

@media (max-width: 700px) {{
    .block-container {{ padding: 1rem 1rem 4rem; }}
    .midnight-hero {{ padding: 2.5rem 1.5rem 2.2rem; border-radius: 22px; }}
    .midnight-score-card {{ grid-template-columns: 1fr; text-align: center; padding-inline: 1rem; }}
    .midnight-gauge {{ max-height: 160px; }}
}}
@media (prefers-reduced-motion: reduce) {{
    *, *::before, *::after {{ scroll-behavior: auto !important; transition: none !important; }}
}}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<section class="midnight-hero">
    <div class="midnight-eyebrow">Night-sky intelligence</div>
    <h1>MIDNIGHT</h1>
    <p>See whether the sky is worth watching tonight—and what is limiting it.
    Built for the world to help people reconnect with nature and support environmental health.</p>
</section>
""", unsafe_allow_html=True)


def render_score_gauge(score: float, label: str) -> None:
    bounded_score = max(0.0, min(100.0, float(score)))
    st.markdown(f"""
    <div class="midnight-score-card">
        <div>
            <div class="midnight-score-kicker">Stargazing score now</div>
            <div class="midnight-score-label">{label}</div>
        </div>
        <svg class="midnight-gauge" viewBox="0 0 260 160" role="img"
             aria-label="Stargazing score {bounded_score:.0f} out of 100, {label}">
            <defs>
                <linearGradient id="midnight-score-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stop-color="#B76572" />
                    <stop offset="52%" stop-color="#D98A6F" />
                    <stop offset="100%" stop-color="#F2B880" />
                </linearGradient>
                <filter id="midnight-gauge-glow" x="-30%" y="-30%" width="160%" height="160%">
                    <feGaussianBlur stdDeviation="3" result="blur" />
                    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
                </filter>
            </defs>
            <path d="M 30 132 A 100 100 0 0 1 230 132" fill="none"
                  stroke="rgba(151,161,205,0.18)" stroke-width="14" stroke-linecap="round"
                  pathLength="100" />
            <path d="M 30 132 A 100 100 0 0 1 230 132" fill="none"
                  stroke="url(#midnight-score-gradient)" stroke-width="14" stroke-linecap="round"
                  pathLength="100" stroke-dasharray="{bounded_score:.1f} 100"
                  filter="url(#midnight-gauge-glow)" />
            <text x="130" y="108" text-anchor="middle" class="gauge-score">{bounded_score:.0f}</text>
            <text x="130" y="130" text-anchor="middle" class="gauge-total">OUT OF 100</text>
        </svg>
    </div>
    """, unsafe_allow_html=True)

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
    starting_darkness_score = darkness_score(brightness)
    expectations = visibility_expectations(bortle)

    if forecast_error or not forecast:
        fallback_sky_section = st.container(border=True)
        fallback_sky_section.metric("Modeled Bortle class", f"{bortle} / 9")
        fallback_sky_section.caption(interpret_bortle(bortle))
        fallback_sky_section.caption(
            "Estimated from population density using Walker's Law. This cannot account for local "
            "lighting ordinances — communities with dark-sky policies, like Flagstaff, are darker "
            "than this model predicts."
        )
        fallback_sky_section.subheader("What this sky reveals")
        fallback_sky_section.write(f"**Likely visible:** {expectations['visible']}")
        fallback_sky_section.write(f"**Hidden by skyglow:** {expectations['missing']}")
        fallback_sky_section.warning(forecast_error or "No forecast hours were returned.")
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
        render_score_gauge(current_score, score_label(current_score))
        st.caption(interpret_score(current_score))
        st.write(limiting_factor(subscores))
        score_breakdown_section = st.container(border=True)
        score_breakdown_section.subheader("Score breakdown")
        score_breakdown_section.write(f"Cloud cover: **{nearest['cloud_cover']:.0f}%**")
        score_breakdown_section.caption(interpret_clouds(nearest["cloud_cover"]))
        for factor, value in subscores.items():
            score_breakdown_section.write(f"{factor.replace('_', ' ').title()} contribution: **{value:.0f} / 100**")
            score_breakdown_section.caption(interpret_component(factor, value))

    sky_model_section = st.container(border=True)
    sky_model_section.metric("Modeled Bortle class", f"{bortle} / 9")
    sky_model_section.caption(interpret_bortle(bortle))
    sky_model_section.caption(
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

    night_detail_section = st.container(border=True)
    selected_night_label = (
        night_detail_section.selectbox("Choose a night to inspect", night_labels, key="selected_night")
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
    night_detail_section.subheader(chart_a_title)
    flat_night = False
    if not complete_dark_window:
        night_detail_section.warning(
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
            night_detail_section.caption(interpret_darkness_window(darkness_start, darkness_end))
            chart_edge_padding = timedelta(minutes=10)
            chart_time_domain = [
                (darkness_start - chart_edge_padding).isoformat(),
                (darkness_end + chart_edge_padding).isoformat(),
            ]
        if flat_night:
            night_detail_section.write(
                f"Conditions barely change {selected_period} ({score_min:.0f}–{score_max:.0f}). "
                "Any time in the darkness window works equally well."
            )
        else:
            night_detail_section.write(
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
        night_detail_section.vega_lite_chart(timeline, {
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
            night_detail_section.caption(
                f"The modeled score stays between {score_min:.0f} and {score_max:.0f} {selected_period}; "
                f"{limitation[0].lower() + limitation[1:]}"
            )
        else:
            night_detail_section.caption(
                f"{summary_prefix}: conditions peak from {local_start.strftime('%I:%M %p')}–{local_end.strftime('%I:%M %p')} "
                f"at {best['best_score']:.0f}/100; {limitation[0].lower() + limitation[1:]}"
            )
        if flat_night:
            night_detail_section.caption("Legend: the line is the hourly stargazing score; no best-window band is shown because conditions are nearly constant.")
        else:
            night_detail_section.caption(
                "Legend: the line is the hourly stargazing score; the highlighted band is the best window; "
                "gaps are daylight, when no score is calculated."
            )
        night_detail_section.caption("Scale: 85–100 Excellent · 70–84 Good · 50–69 Fair · 30–49 Poor · below 30 Don’t bother.")
    else:
        night_detail_section.info("No astronomical darkness occurs for this location on the selected night.")

    night_summary_section = st.container(border=True)
    night_summary_section.subheader("Next 7 nights")
    if nights:
        best_night = max(nights, key=lambda night: night["score"])
        night_chart = pd.DataFrame({
            "Night": night_labels,
            "Best score": [night["score"] for night in nights],
            "Selected": [label == selected_night_label for label in night_labels],
        })
        night_summary_section.vega_lite_chart(night_chart, {
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
        night_summary_section.caption(
            f"Seven-night summary: {best_night_local.strftime('%A, %b %d')} is strongest at "
            f"{best_night['score']:.0f}/100 — {interpret_score(best_night['score'])} "
            f"{selected_night_label} is selected for the detailed chart above."
        )
    else:
        best_night = None
        night_summary_section.info("No astronomical darkness appears in the next seven nights, so no nightly chart is shown.")

    visibility_section = st.container(border=True)
    visibility_section.subheader("What you can see tonight")
    observing_time = best["start"] if best else now
    illumination = moon_illumination(observing_time)
    phase = moon_phase_name(illumination, moon_is_waxing(observing_time))
    selected_moon_altitude = moon_altitude(observing_time, location["lat"], location["lon"])
    visibility_section.write(
        f"**Moon:** {phase}, {illumination * 100:.0f}% illuminated, "
        f"{selected_moon_altitude:.0f}° altitude at the selected observing time."
    )
    visibility_section.caption(interpret_moon(illumination, selected_moon_altitude))
    planets = visible_planets(observing_time, location["lat"], location["lon"])
    meteors = meteor_activity(observing_time.astimezone(local_zone))
    observing_weather = min(forecast, key=lambda row: abs((row["time"] - observing_time).total_seconds()))
    visibility = visibility_snapshot(
        bortle, illumination, selected_moon_altitude, observing_weather["cloud_cover"],
        [planet["name"] for planet in planets], meteors["active"],
    )
    visibility_section.write(f"**Milky Way:** {visibility['milky_way']}")
    visibility_section.write(f"**Naked-eye planets:** {visibility['planets']}")
    visibility_section.write(f"**Meteor showers:** {visibility['meteors']}")
    visibility_section.write(f"**Deep-sky objects:** {visibility['deep_sky']}")
    visibility_section.write(f"**Faintest stars:** {visibility['limiting_magnitude']}")
    visibility_section.info(visibility["loss"])
    visibility_section.caption("Planet positions are low-precision estimates; terrain and buildings are not modeled.")

    atmosphere_section = st.container(border=True)
    atmosphere_section.subheader("Cloud layers, fog, and smoke")
    low_cloud = nearest.get("cloud_cover_low", nearest["cloud_cover"])
    mid_cloud = nearest.get("cloud_cover_mid", nearest["cloud_cover"])
    high_cloud = nearest.get("cloud_cover_high", nearest["cloud_cover"])
    atmosphere_section.write(
        f"Cloud layers: **{low_cloud:.0f}% low · {mid_cloud:.0f}% middle · {high_cloud:.0f}% high**"
    )
    atmosphere_section.caption(interpret_cloud_layers(low_cloud, mid_cloud, high_cloud))

    temperature = nearest.get("temperature_2m", 10.0)
    dew_point = nearest.get("dew_point_2m", temperature - 5.0)
    wind_speed = nearest.get("wind_speed_10m", 15.0)
    dew_point_spread = temperature - dew_point
    fog_likely, fog_meaning = interpret_fog(temperature, dew_point, wind_speed)
    atmosphere_section.write(
        f"Fog inputs: **{dew_point_spread:.1f}°C temperature–dew point spread · "
        f"{wind_speed:.1f} km/h wind**"
    )
    if fog_likely:
        atmosphere_section.warning(f"Fog risk: {fog_meaning}")
    else:
        atmosphere_section.caption(f"Fog risk: {fog_meaning}")

    air_quality, air_error = fetch_air_quality(location["lat"], location["lon"])
    if air_quality:
        nearest_air = min(air_quality, key=lambda row: abs((row["time"] - now).total_seconds()))
        pm_value = nearest_air["pm2_5"]
        aerosol = nearest_air["aerosol_optical_depth"]
        aerosol_text = f" and aerosol optical depth {aerosol:.2f}" if aerosol is not None else ""
        atmosphere_section.write(f"Forecast PM2.5 is **{pm_value:.1f} µg/m³**{aerosol_text}. Lower values generally mean clearer skies.")
        atmosphere_section.caption(interpret_aerosol(aerosol, pm_value))
        smoke_meaning = interpret_smoke(pm_value)
        if pm_value >= 25:
            atmosphere_section.warning(f"Smoke signal: {smoke_meaning}")
        else:
            atmosphere_section.caption(f"Smoke signal: {smoke_meaning}")
    else:
        atmosphere_section.info(air_error or "Air-quality detail is unavailable; forecast visibility remains the haze proxy.")

    dark_site_section = st.container(border=True)
    dark_site_section.subheader("Dark-sky candidates nearby")
    dark_site_sort = "Best balance"
    if bortle <= 4:
        sites = []
        osm_lookup_succeeded = False
    else:
        dark_site_sort = dark_site_section.selectbox(
            "Sort dark-site candidates by",
            ["Best balance", "Darkest sky", "Shortest trip"],
            key="dark_site_sort",
        )
        sort_explanations = {
            "Best balance": "Balances modeled darkness improvement against travel distance, favoring a useful middle ground.",
            "Darkest sky": "Ranks the highest modeled darkness first; distance only breaks ties.",
            "Shortest trip": "Ranks the shortest straight-line trip first; darkness only breaks ties.",
        }
        dark_site_section.caption(sort_explanations[dark_site_sort])
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
        site["darkness_gain"] = round(site["darkness_score"] - starting_darkness_score, 1)
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
    sites = rank_dark_site_candidates(sites, dark_site_sort)[:8]
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
            "bortle": bortle, "distance_km": 0, "darkness_score": starting_darkness_score,
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
        dark_site_section.pydeck_chart(deck, width="stretch")
        dark_site_section.caption(
            f"Map summary: {sites[0]['name']} ranks first by {dark_site_sort.lower()}, "
            f"{interpret_distance(sites[0]['distance_km'], unit_system)} {interpret_bortle(sites[0]['bortle'])} "
            "Purple markers are candidates; the gold marker is your starting location."
        )
        dark_site_section.write(
            f"**Starting location (gold marker):** {location['name']} — {interpret_bortle(bortle)} · "
            f"modeled light-pollution darkness {starting_darkness_score:.0f}/100 · "
            f"{format_distance(0, unit_system)} straight-line · "
            f"`{location['lat']:.4f}, {location['lon']:.4f}`"
        )
        dark_site_section.markdown(f"[Open starting location in Google Maps]({google_maps_url(location['lat'], location['lon'])})")
        if osm_lookup_succeeded:
            dark_site_section.caption("A named public-access recreation feature was found near at least one dark-sky candidate.")
        else:
            dark_site_section.caption("Each dark point is described relative to a nearby named place when no public park, trailhead, or viewpoint is available.")
        dark_site_section.caption(
            "These comparisons isolate artificial light. Clouds, Moon, smoke, and humidity remain part of the separate overall stargazing score."
        )
        for index, site in enumerate(sites, 1):
            access_line = f"{site['access_label']}  \n" if site.get("access_label") else ""
            dark_site_section.markdown(
                f"**{index}. {site['name']}**  \n"
                f"{site['country']}  \n"
                f"{interpret_distance(site['distance_km'], unit_system)}  \n"
                f"{interpret_bortle_improvement(bortle, site['bortle'])}  \n"
                f"{access_line}"
                f"{interpret_darkness_change(starting_darkness_score, site['darkness_score'])}  \n"
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
        (dark_site_section.success if bortle <= 4 else dark_site_section.info)(guidance)

    plan_section = st.container(border=True)
    plan_section.subheader("Take this plan with you")
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
    plan_section.download_button(
        "Download night-sky plan",
        summary_card,
        file_name=f"midnight-{location['name'].lower().replace(' ', '-')}.md",
        mime="text/markdown",
    )
