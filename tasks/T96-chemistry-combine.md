# T96: C/A: Chemistry maps combined (several features at once, as one colour picture)

- **Owner:** Mati  ·  **Status:** done
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
- [x] pipeline/chemistry.py: `SHOWS` (emission / absorption per feature), `composite(target_dir, features)`
      from the per-feature maps (intersection of their coverage, 1-noise-level floor)
- [x] Live API: map layer `x-<a>-<b>[-<c>]` (features in wavelength order), PNG
      `/api/targets/<id>/chemistry/<a>-<b>.png`, `shows` in `/api/chemistry/features` (CONTRACTS + Decisions)
- [x] Viewer: checkboxes instead of the select (max 3), maps made one after another (memory), legend with
      the colours; stays right when the band / false colour changes
- [x] Tests (pipeline 3 new, server 3 new); scripted browser check on Orion (Br-α + PAH + H₂O ice)
- [ ] Later: keep the picture when the band moves to another detector (that is another field since T89)

## Findings
- 2026-11-15, Orion (c0838300-m053900-s20), H₂O ice + PAH + Br-α: Br-α (red) on M42's ionised gas and M43, PAH
  (green) along the cloud edges, the bright core white (all three strong there: the ice "absorption" inside the
  nebula is the PAH plateau the T93 note warns about). Made from the existing maps: instant.
- Single-feature "off" in T93 left the layer on the map; now unticking all hides it and gives the map back to the
  automatic blink.
- Band change to another detector = another field (T89 per-detector fields): the picture ends there, as before.

## Questions / needs from others

## Handoff
Use: open a field (e.g. RA 83.83 Dec −5.39, 20′), map view panel → **Chemistry ▾** → tick 1-3 features. API:
CONTRACTS v0.27 "Combined". Code: `pipeline/chemistry.py` (`SHOWS`, `combo`, `strength`, `combined_map`),
`server/chemistry.py`, `server/hips.py` (`x-<a>-<b>[-<c>]`, `_chem_mtime`), `web/chemistry.js`; app.js: `map:give`,
`explore:epoch-picked` detail `auto`.

## Notes from others
