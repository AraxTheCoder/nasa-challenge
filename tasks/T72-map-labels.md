# T72: catalogue names anywhere on the explore map

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T72-map-labels`
- **Depends on / feeds:** T35 (traces), T36 (sky map), T52 (label sources)

## Goal
The explore map showed names only for the shown field's important movers (T35 traces). Show catalogue
names wherever the map is, like the frame viewer does for a field.

## Plan
- [x] `pipeline.labels.sky_labels` + `GET /api/sky-labels?ra=&dec=&radius=` (snapped to a 0.25 deg grid,
      cached in memory and `data/sky_labels/`; planets left out: the map combines all epochs)
- [x] `web/skylabels.js`: fetch when zoomed in to 2 deg or closer, draw in importance order where names fit
      (Messier/NGC/IC, then notable/fast, then real names), catalogue numbers only as dots until < 0.25 deg,
      hover shows type, catalogue, note, brightness, motion; skips names traces.js draws; Labels switch
- [x] More survey prefixes count as catalogue numbers (2dFGRS, LEDA, GALEX, ...): also fewer default names in
      the frame viewer

## Findings
First request per cell 3-6 s (SIMBAD + VSX + CatWISE + Gaia for merging), then instant. Orion 0.5 deg:
501 labels; M31 1 deg: 500 (SIMBAD capped at 400, ranked); Eps Ind 0.5 deg: 157.

## Handoff
Nothing to set up. Not in `/app/` (T55) yet: it needs `import "./skylabels.js"` and the `explore:ready`
event / `getApiBase` from explore.js.

## Notes from others
