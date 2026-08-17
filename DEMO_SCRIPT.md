# Umbra demo script — target 4:40

## 0:00–0:40 — Problem and prompt

Our prompt was to build technology that helps people reconnect with nature or
supports environmental health. Artificial light at night affects nocturnal
wildlife, migratory birds, insects, and human circadian rhythms. It also hides
the night sky. Umbra makes this invisible pollution personal: it shows whether
you can see stars tonight, what is stopping you, and how far you would need to
go to find a darker sky.

## 0:40–1:25 — Core loop

Enter **Portland, Oregon**. Show the explicit daytime gate or current score,
read its plain-language consequence, then show the interpreted factor breakdown
and tonight's true-darkness and best-viewing windows. Point out the highlighted
hourly timeline and its text summary.

## 1:25–2:25 — Technical core

Show `astronomy.py`. Umbra computes solar and lunar positions from orbital
elements, converts ecliptic coordinates to equatorial coordinates, uses local
sidereal time to calculate altitude, and treats the sky as astronomically dark
only when the Sun is below −18 degrees. Moon illumination comes from Sun–Moon
elongation—not a lookup table.

Show `light_pollution.py`. Walker's Law models each city's contribution as
population divided by distance to the 2.5 power. Umbra sums nearby contributions
from the committed GeoNames dataset, then uses a log calibration because sky
brightness spans orders of magnitude. Say clearly that this is a modeled
estimate, not a radiometric measurement; production should use VIIRS-calibrated
World Atlas data.

## 2:25–3:10 — Where to go

Show the dark-sites map and first ranked site. State its straight-line distance
and rough driving-time estimate. Scroll through the equivalent text list and
note that every candidate is a real GeoNames populated place, while public
observing access still must be verified.

## 3:10–3:40 — Physics details

Show **What you can see tonight**. Read the Milky Way status, actual naked-eye
planets, adjusted meteor estimate, and star-loss comparison: an urban observer
may see only tens or hundreds of stars where a Bortle 2 sky reveals several
thousand. Then show the high/middle/low cloud, fog, and smoke interpretations.

## 3:40–4:10 — Accessibility and resilience

Every input is labeled; no state is communicated by color alone; every chart
and map has a text summary; and the dark-site list conveys everything in the
map. Population data is committed locally, and every forecast call fails with
a clear message rather than a traceback.

## 4:10–4:40 — Close

Umbra is for anyone who wants to reconnect with the night sky but does not know
when or where to go. Next steps are verified observing sites, real route
planning, clear-night alerts, community validation, and satellite-calibrated
light data. Umbra tells you whether you can see stars tonight, why you can't,
and where to drive to fix it.
