# Midnight — Devpost submission copy

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

Midnight accepts a location and produces a physically gated stargazing score,
factor-by-factor explanation, best viewing window, seven-night comparison,
Moon and naked-eye planet visibility, meteor-shower context, and ranked nearby
dark-sky candidates. It shows candidates on a map and in an accessible text
list, then generates a downloadable observing plan.
Ambiguous names such as Portland present accessible location choices, and
distance displays support both kilometers and miles for international use.
Every numeric result states its practical consequence, and a dedicated panel
contrasts the stars visible locally with what light pollution has erased.
Layered clouds, fog risk, particle haze, and possible smoke are explained in
plain language rather than collapsed into one weather number.

## How we built it

We implemented low-precision Sun, Moon, and planet positions from orbital
elements using Python's standard math library. The model converts ecliptic to
equatorial coordinates, uses local sidereal time for observer-relative altitude,
derives lunar illumination from elongation, and gates scores at the −18°
astronomical-twilight threshold.

Artificial brightness follows Walker's Law: population × distance^−2.5. We sum
nearby cities from a committed GeoNames dataset, calibrate the result on a
logarithmic scale to an estimated Bortle class, and rank real GeoNames populated
places by modeled darkness and distance. Open-Meteo supplies keyless hourly
weather, layered cloud, dew-point, wind, PM2.5, and aerosol data; the app handles
unavailable services without tracebacks.

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
Midnight deliberately distinguishes modeled Bortle estimates from measurements and
explains what each score factor means rather than hiding everything behind one
number.

## What's next

- **Verified observing sites:** Partner with astronomy clubs on public access,
  parking, hours, and safety notes so every recommendation is dependable.
- **Route planning:** Add reliable driving time and directions so travel choices
  reflect real roads rather than straight-line distance.
- **Alerts:** Notify users before unusually clear, dark windows so they can act
  on conditions that may only occur a few nights each month.
- **Community validation:** Collect observer reports to reveal where modeled
  conditions drift from the real sky and guide future calibration.
- **Satellite-calibrated light pollution:** Replace population-based brightness
  with VIIRS-derived measurements for more locally accurate skyglow estimates.

## AI usage disclosure

We used OpenAI Codex to help translate our written specification into Python,
create tests and documentation, and review failure paths. The team directed the
product, evaluated the outputs, and remains responsible for the submitted work.

## Links to fill before submission

- Public GitHub repository: https://github.com/SachitCharan/midnight
- Live Streamlit app: TODO
- Demo video (five minutes maximum): TODO
