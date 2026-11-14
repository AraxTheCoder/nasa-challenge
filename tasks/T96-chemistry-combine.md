# T96: C/A: Chemistry maps combined (several features at once, as one colour picture)

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T96-chemistry-combine`
- **Depends on / feeds:** T93 (chemistry maps), T81 (field layers on the map), T89 (false colour), T90 (automatic blink)

## Goal
Asked by Mati (2026-11-14): select several chemistry filters and see them on at the same time. Tick up to
three features in the map's Chemistry control:
- one feature: the T93 grey map as before (dark = absorption, bright = emission);
- two or three: one colour picture, like a narrow-band image: each feature gets a colour by wavelength
  (shortest blue, longest red; with two: cyan and red), showing it in the direction that matters (emission
  for the hydrogen lines and PAH, absorption depth for the ices and water bands). Overlaps mix (red + green =
  yellow, all three = white); black = none of them stands out.
Visualization only (Decision 2026-11-14): a legend says which colour is what; nothing is classified. Works
with false colour on or off, any band, and the automatic blink.

## Plan
- [ ] pipeline/chemistry.py: `SHOWS` (emission / absorption per feature), `composite(target_dir, features)`
      from the per-feature maps (intersection of their coverage, 1-noise-level floor)
- [ ] Live API: map layer `x-<a>-<b>[-<c>]` (features in wavelength order), PNG
      `/api/targets/<id>/chemistry/<a>-<b>.png`, `shows` in `/api/chemistry/features` (CONTRACTS + Decisions)
- [ ] Viewer: checkboxes instead of the select (max 3), maps made one after another (memory), legend with
      the colours; stays right when the band / false colour changes
- [ ] Tests (pipeline, server, node / browser); check on Orion (Br-α + PAH + H₂O ice)

## Findings

## Questions / needs from others

## Handoff

## Notes from others
