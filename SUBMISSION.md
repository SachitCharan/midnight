# Devpost submission copy

## Tagline

Know when the sky gets dark—and where to go when your city never does.

## Inspiration

Artificial light at night is both an environmental stressor and a barrier
between people and nature. It affects nocturnal wildlife, migratory birds,
insects, and human circadian rhythms while washing the Milky Way out of urban
skies. For OregonHacks' prompt—technology that helps people reconnect with
nature or supports environmental health—we wanted to make light pollution
visible, local, and actionable.

## What it does

Umbra accepts a location and produces a physically gated stargazing score,
factor-by-factor explanation, best viewing window, seven-night comparison,
Moon and naked-eye planet visibility, meteor-shower context, and ranked nearby
dark-sky candidates. It shows candidates on a map and in an accessible text
list, then generates a downloadable observing plan.

## How we built it

We implemented low-precision Sun, Moon, and planet positions from orbital
elements using Python's standard math library. The model converts ecliptic to
equatorial coordinates, uses local sidereal time for observer-relative altitude,
derives lunar illumination from elongation, and gates scores at the −18°
astronomical-twilight threshold.

Artificial brightness follows Walker's Law: population × distance^−2.5. We sum
nearby cities from a committed GeoNames dataset, calibrate the result on a
logarithmic scale to an estimated Bortle class, and search a bounded geographic
grid for darker candidates. Open-Meteo supplies keyless hourly weather and
optional aerosol data; the app handles unavailable services without tracebacks.

## Challenges

The central challenge was combining transparent astronomical calculations with
an honest light-pollution estimate. Brightness spans orders of magnitude, so a
linear Bortle mapping failed conceptually; the model needs logarithmic scaling.
We also had to treat the Moon geometrically—a bright Moon below the horizon
cannot degrade the score—and ensure the project remains useful when public
services fail.

## Accomplishments

- First-principles Sun, Moon, and five-planet position calculations
- Hard astronomical-darkness gate that prevents nonsensical daytime scores
- Offline primary population dataset with zero runtime dependency
- Accessible map/list parity and written alternatives for every visual
- Tested failure paths for geocoding, weather, air quality, and optional Overpass

## What we learned

Environmental models become more trustworthy when their assumptions are visible.
Umbra deliberately distinguishes modeled Bortle estimates from measurements and
explains what each score factor means rather than hiding everything behind one
number.

## What's next

Use VIIRS-calibrated World Atlas brightness, terrain-aware line-of-sight,
verified roads and public-land access, and year-specific meteor predictions.

## AI usage disclosure

We used OpenAI Codex to help translate our written specification into Python,
create tests and documentation, and review failure paths. The team directed the
product, evaluated the outputs, and remains responsible for the submitted work.

## Links to fill before submission

- Public GitHub repository: TODO
- Live Streamlit app: TODO
- Demo video (five minutes maximum): TODO
