"""Pure-CSS, fixed-seed starfield for Midnight's Streamlit interface."""

from __future__ import annotations

import random

import streamlit as st


STARFIELD_SEED = 20260817
STAR_COLORS = (
    (247, 245, 240),  # soft white
    (216, 229, 255),  # pale blue
    (255, 230, 201),  # occasional warm star
)


def _box_shadows(
    rng: random.Random,
    count: int,
    min_alpha: float,
    max_alpha: float,
) -> str:
    shadows = []
    for _ in range(count):
        red, green, blue = rng.choices(STAR_COLORS, weights=(72, 22, 6), k=1)[0]
        shadows.append(
            f"{rng.uniform(0, 100):.2f}vw {rng.uniform(-12, 112):.2f}vh "
            f"0 {rng.choice((0, 0, 0, 0.35))}px "
            f"rgba({red},{green},{blue},{rng.uniform(min_alpha, max_alpha):.2f})"
        )
    return ",".join(shadows)


def inject_starfield() -> None:
    """Inject a stable, accessible starfield behind the Streamlit page."""
    rng = random.Random(STARFIELD_SEED)
    tiny_stars = _box_shadows(rng, 400, 0.26, 0.62)
    medium_stars = _box_shadows(rng, 150, 0.38, 0.78)
    large_stars = _box_shadows(rng, 50, 0.52, 0.92)
    tiny_twinkle = _box_shadows(rng, 36, 0.28, 0.62)
    medium_twinkle = _box_shadows(rng, 18, 0.38, 0.76)
    large_twinkle = _box_shadows(rng, 8, 0.48, 0.86)

    css = f"""
    <style id="midnight-starfield-css">
    html, body {{
        background: #0b1026 !important;
    }}
    .stApp,
    [data-testid="stAppViewContainer"] {{
        background: transparent !important;
    }}
    .midnight-starfield {{
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        overflow: hidden;
        z-index: -1;
        pointer-events: none;
        background:
            radial-gradient(circle at 14% 8%, rgba(73, 72, 130, 0.24), transparent 38rem),
            radial-gradient(circle at 86% 30%, rgba(52, 71, 127, 0.18), transparent 34rem),
            linear-gradient(180deg, #0b1026 0%, #10162d 58%, #11182f 100%);
    }}
    .midnight-starfield::after {{
        content: "";
        position: absolute;
        inset: 0;
        z-index: 6;
        background: rgba(5, 9, 25, 0.10);
    }}
    .midnight-starfield__layer {{
        position: absolute;
        top: 0;
        left: 0;
        border-radius: 50%;
        will-change: transform, opacity;
    }}
    .midnight-starfield__tiny {{
        width: 1px;
        height: 1px;
        box-shadow: {tiny_stars};
    }}
    .midnight-starfield__medium {{
        width: 2px;
        height: 2px;
        box-shadow: {medium_stars};
    }}
    .midnight-starfield__large {{
        width: 3px;
        height: 3px;
        box-shadow: {large_stars};
    }}
    .midnight-starfield__twinkle-tiny {{
        width: 1px;
        height: 1px;
        box-shadow: {tiny_twinkle};
    }}
    .midnight-starfield__twinkle-medium {{
        width: 2px;
        height: 2px;
        box-shadow: {medium_twinkle};
    }}
    .midnight-starfield__twinkle-large {{
        width: 3px;
        height: 3px;
        box-shadow: {large_twinkle};
    }}
    .midnight-starfield__shooting-star {{
        position: absolute;
        width: 170px;
        height: 1px;
        z-index: 5;
        opacity: 0;
        will-change: transform, opacity;
        background: linear-gradient(90deg, transparent, rgba(222, 232, 247, 0.38), rgba(255, 252, 246, 0.96));
        filter: drop-shadow(0 0 4px rgba(235, 241, 250, 0.60));
        transform: translate3d(0, 0, 0) rotate(-28deg);
    }}
    .midnight-starfield__shooting-star::after {{
        content: "";
        position: absolute;
        right: -2px;
        top: -2px;
        width: 5px;
        height: 5px;
        border-radius: 50%;
        background: #fffdf7;
        box-shadow: 0 0 9px rgba(235, 241, 250, 0.76);
    }}
    .midnight-starfield__shooting-one {{ top: 12vh; left: -14vw; }}
    .midnight-starfield__shooting-two {{ top: 39vh; left: 44vw; }}
    .midnight-starfield__shooting-three {{ top: 7vh; left: 74vw; }}

    @keyframes midnight-drift-tiny {{
        to {{ transform: translate3d(0, -6vh, 0); }}
    }}
    @keyframes midnight-drift-medium {{
        to {{ transform: translate3d(0, -10vh, 0); }}
    }}
    @keyframes midnight-drift-large {{
        to {{ transform: translate3d(0, -14vh, 0); }}
    }}
    @keyframes midnight-twinkle-soft {{
        0%, 100% {{ opacity: 0.22; }}
        48% {{ opacity: 0.88; }}
        62% {{ opacity: 0.46; }}
    }}
    @keyframes midnight-shoot {{
        0%, 82% {{ opacity: 0; transform: translate3d(0, 0, 0) rotate(-28deg); }}
        84% {{ opacity: 0.94; }}
        90% {{ opacity: 0; transform: translate3d(62vw, 36vh, 0) rotate(-28deg); }}
        100% {{ opacity: 0; transform: translate3d(62vw, 36vh, 0) rotate(-28deg); }}
    }}

    @media (prefers-reduced-motion: no-preference) {{
        .midnight-starfield__tiny {{ animation: midnight-drift-tiny 200s linear infinite alternate; }}
        .midnight-starfield__medium {{ animation: midnight-drift-medium 120s linear infinite alternate; }}
        .midnight-starfield__large {{ animation: midnight-drift-large 70s linear infinite alternate; }}
        .midnight-starfield__twinkle-tiny {{
            animation: midnight-drift-tiny 200s linear infinite alternate,
                       midnight-twinkle-soft 8.5s ease-in-out infinite -2s;
        }}
        .midnight-starfield__twinkle-medium {{
            animation: midnight-drift-medium 120s linear infinite alternate,
                       midnight-twinkle-soft 6.8s ease-in-out infinite -4.5s;
        }}
        .midnight-starfield__twinkle-large {{
            animation: midnight-drift-large 70s linear infinite alternate,
                       midnight-twinkle-soft 5.6s ease-in-out infinite -1.2s;
        }}
        .midnight-starfield__shooting-one {{ animation: midnight-shoot 31s linear infinite 15s; }}
        .midnight-starfield__shooting-two {{ animation: midnight-shoot 37s linear infinite 27s; }}
        .midnight-starfield__shooting-three {{ animation: midnight-shoot 43s linear infinite 38s; }}
    }}
    </style>
    <div class="midnight-starfield" aria-hidden="true">
        <div class="midnight-starfield__layer midnight-starfield__tiny"></div>
        <div class="midnight-starfield__layer midnight-starfield__medium"></div>
        <div class="midnight-starfield__layer midnight-starfield__large"></div>
        <div class="midnight-starfield__layer midnight-starfield__twinkle-tiny"></div>
        <div class="midnight-starfield__layer midnight-starfield__twinkle-medium"></div>
        <div class="midnight-starfield__layer midnight-starfield__twinkle-large"></div>
        <div class="midnight-starfield__shooting-star midnight-starfield__shooting-one"></div>
        <div class="midnight-starfield__shooting-star midnight-starfield__shooting-two"></div>
        <div class="midnight-starfield__shooting-star midnight-starfield__shooting-three"></div>
    </div>
    """
    st.markdown(css, unsafe_allow_html=True)
