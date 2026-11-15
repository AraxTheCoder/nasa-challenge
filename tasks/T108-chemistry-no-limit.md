# T108: C/A: Chemistry: no limit of 3 features in one picture

- **Owner:** Mati  ·  **Status:** done (checked in a browser by Joerg, 2026-11-15)
- **Branch:** `mati/T108-chemistry-no-limit`
- **Depends on / feeds:** T96 (combined maps), T107 (presets)

## Goal
Asked by Mati (2026-11-15): tick any number of chemistry features (all 10) for one colour picture. Why there was
a limit: three colours (blue, green, red) are independent, so every mix can be read back (yellow = green + red).
From four on, each feature gets its own hue by wavelength (blue → cyan → green → yellow → red); mixes can then no
longer be read back uniquely, and the legend says so.

## Plan
- [x] pipeline/chemistry.py: COMBINE_MAX = all features; colours for any count (2 and 3 unchanged)
- [x] server/hips.py layer pattern; CONTRACTS + Decision
- [x] viewer: texts without "up to 3", the note warns about mixes from 4 on
- [x] tests

## Findings
- ρ Oph (c2467900-m245400-s30), 7 features (Pa-β, Br-γ, H₂O ice, PAH, Br-α, CO₂ ice, CO): picture and map layer
  served; the cloud orange/yellow (CO₂ + CO), the lit side green-cyan (PAH, water ice). Readable, but a colour no
  longer names one feature: the note says so and suggests the single maps.

## Questions / needs from others

## Handoff
Chemistry ▾: tick any number. Colours: `pipeline/chemistry.py COMBINE_COLOURS` (`_hue_colours`).

## Notes from others
