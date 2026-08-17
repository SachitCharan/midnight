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
the four-factor breakdown, the limiting-factor sentence, and tonight's best
local-time window. Point out the hourly timeline and its text summary.

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
and modeled Bortle class. Scroll through the equivalent text list and note that
the suggestions are grid candidates, so users must verify road and land access.

## 3:10–3:40 — Physics details

Show the Moon/planet/meteor panel. Explain that a full Moon below the horizon
does not reduce the score. Umbra also extends the orbital-element math to the
five naked-eye planets and names active major meteor showers.

## 3:40–4:10 — Accessibility and resilience

Every input is labeled; no state is communicated by color alone; every chart
and map has a text summary; and the dark-site list conveys everything in the
map. Population data is committed locally, and every forecast call fails with
a clear message rather than a traceback.

## 4:10–4:40 — Close

Umbra is for anyone who wants to reconnect with the night sky but does not know
when or where to go. A production version would use satellite-calibrated light
data and verified routing. Umbra tells you whether you can see stars tonight,
why you can't, and where to drive to fix it—by modeling light pollution,
moonlight, and cloud cover from first principles.
