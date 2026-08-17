# Umbra

Umbra tells you whether you can see stars tonight, why you can't, and where to
drive to fix it — by modeling light pollution, moonlight, and cloud cover from
first principles.

Light pollution is a measurable environmental problem: artificial night light
disrupts nocturnal wildlife, migratory birds and insects, affects human
circadian rhythms, and separates people from the night sky. Umbra makes that
otherwise gradual and invisible pollution understandable at a specific place.

Built for the OregonHacks prompt: **Build technology that helps people reconnect
with nature or supports environmental health.**

## What it does

- Scores current stargazing conditions only after astronomical darkness begins.
- Disambiguates place-name searches and preserves the selected location while
  recomputing results.
- Explains the practical consequence of every score, sky-quality, Moon,
  cloud, aerosol, darkness-window, and travel-distance number.
- Finds the best hour tonight and compares the best hour across seven nights.
- Ranks nearby modeled dark-site candidates and presents both a map and an
  equivalent text list.
- Shows a Bortle-, Moon-, and cloud-adjusted guide to the Milky Way, planets,
  meteors, deep-sky objects, limiting magnitude, and stars lost to skyglow.
- Estimates naked-eye planet positions from orbital elements and identifies
  active major meteor showers.
- Distinguishes low, middle, and high clouds and flags modeled fog and smoke
  conditions using Open-Meteo weather and air-quality data.
- Produces a downloadable night-sky plan.
- Supports global locations with metric/imperial distance controls; US results
  default to miles and all other country codes default to kilometers.

## Run locally

Requires Python 3.10 or newer.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Run the dependency-free logic tests with `python test_logic.py`.

## Methodology

Umbra computes low-precision solar and lunar coordinates directly from orbital
elements. It transforms ecliptic longitude and latitude to right ascension and
declination, uses local sidereal time to find altitude, derives lunar
illumination from Sun–Moon elongation, and defines astronomical darkness as a
solar altitude below −18 degrees.

Artificial brightness uses Walker's Law (Walker, 1977): each nearby population
center contributes population divided by distance in kilometers to the power
2.5. Contributions inside 150 km are summed, then a piecewise log calibration
maps remote, mid-size-town, and major-city reference points to Bortle 2, 6, and
9. Weather comes from Open-Meteo. Population
centers come from the committed global GeoNames `cities15000` dataset and are enriched
with checked Oregon/PNW population figures. No population-data network call is
required. Optional OpenStreetMap Overpass enrichment can fill smaller towns but
is never needed for correctness.

The 0–100 score weights cloud cover at 40%, light pollution at 30%, moonlight
at 20%, and visibility/humidity at 10%. Moonlight has no penalty when the Moon
is below the horizon. The app never gives a score outside astronomical
darkness.

The planet panel independently solves approximate heliocentric positions for
Mercury, Venus, Mars, Jupiter, and Saturn, translates them into geocentric
equatorial coordinates, and then uses the same local-sidereal-time altitude
calculation as the Sun and Moon. The meteor overlay is a transparent static
calendar of major annual showers rather than a live prediction service.

Dark-site candidates use a hybrid search: a coarse coordinate grid finds dark
gaps between towns, then each point must be within 25 km of a committed GeoNames
place before it survives the land-safety filter. Umbra describes each surviving
point relative to the nearest named place and ranks the default view by modeled
darkness gained per kilometer. Open-Meteo's Copernicus GLO-90 elevation lookup
removes open-water cells; if it is unavailable, Umbra safely falls back to
named land places. A top point can be replaced by a nearby named recreation
feature only when OpenStreetMap explicitly confirms public access.

## Model limitations

The Bortle class is a modeled estimate, not a radiometric measurement. Walker's
Law reduces settlements to population and distance: it does not represent
terrain, fixture design, spectral output, atmospheric scattering, or detailed
urban form. GeoNames omits many settlements below 15,000 people. A production
version should use satellite-calibrated sky
brightness such as the Falchi et al. World Atlas derived from VIIRS data.

The Sun and Moon formulas intentionally trade precision for transparency and can
have errors of a few arcminutes; the simplified planetary elements can have
larger errors and are meant for broad naked-eye direction guidance. The five-minute darkness-window sampling,
hourly weather resolution, straight composite weights, and forecast uncertainty
also limit precision. Umbra is a planning aid, not an observatory-grade model.

As a fixed sanity check, the test suite compares the computed Saturn altitude
for Portland at 2026-08-17 06:00 UTC with NASA/JPL Horizons (8.44°); the
low-precision result must remain within one degree.

## Data and privacy

The app uses keyless Open-Meteo geocoding and forecast endpoints. Population
data is read locally from GeoNames; optional Overpass enrichment is disabled by
default. It requires no API keys and stores no user accounts or location history.

## Data attribution

Population data comes from [GeoNames](https://www.geonames.org/), licensed
under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The committed
`data/GEONAMES_README.txt` contains the distributor's format and license notice.

Meteor shower dates and ideal zenithal hourly rates are approximate annual
reference values. Actual observed rates depend strongly on radiant altitude,
Moon, weather, light pollution, and the year-specific peak.

## Accessibility

Every input has a visible label. Scores and states use text rather than color
alone. Every chart and map has a written summary, and the ranked dark-site list
contains the same names, coordinates, distances, and Bortle estimates as the
map. The interface remains usable if visualizations do not load. Theme colors
use high-contrast twilight-inspired ivory, amber, indigo, and midnight tones.

## Roadmap

- **Verified observing sites:** Partner with local astronomy clubs to curate
  public-access status, parking, hours, and safety notes so recommendations are
  dependable destinations rather than model outputs alone.
- **Route planning:** Add reliable driving time and directions so users can
  compare the real effort of reaching each darker site instead of relying on
  straight-line distance and a rough estimate.
- **Alerts:** Notify users when an unusually clear, dark window is approaching
  so rare good conditions are easier to act on.
- **Community validation:** Let observers report actual conditions and use
  those reports to identify where the model consistently drifts from reality.
- **Satellite-calibrated light pollution:** Replace Walker's Law estimates with
  VIIRS-derived measurements so local sky brightness reflects observed light
  emissions rather than population alone.

## AI usage disclosure

This project was developed with assistance from OpenAI Codex. AI helped
translate the written specification into Python, create tests and documentation,
and review failure paths. The team remains responsible for the product choices,
verification, demonstration, and submitted work.

## Project structure

- `astronomy.py` — Sun, Moon, twilight, and naked-eye planet math
- `light_pollution.py` — Walker's Law, Bortle mapping, visibility guidance
- `interpretations.py` — value-sensitive plain-language consequences and sky visibility
- `scoring.py` — composite score, best window, seven-night comparison
- `data_sources.py` — guarded keyless APIs and local GeoNames loading
- `dark_sites.py` — real populated-place candidate ranking by darkness and distance
- `meteor_showers.py` — major annual-shower calendar
- `units.py` — metric/imperial display conversion while models stay metric
- `app.py` — accessible Streamlit interface
- `test_logic.py` — dependency-free test runner
