# T121: Chemistry maps smoother (noise speckle, blocky tiles) + errors in the running viewer

- **Owner:** Mati  ·  **Status:** review
- **Branch:** `mati/T121-chemistry-smooth`
- **Depends on / feeds:** T93, T96, T108

## Goal
Chemistry maps on the sky map look smooth instead of speckled and blocky: pixel noise softened, map tiles
sampled bilinearly instead of nearest pixel. Works on the maps already cached (no recompute). Plus: errors seen
by Mati in the running viewer fixed.

## Plan
- [x] smoothing of the grey map when it is read (single maps and combined pictures)
- [x] bilinear sampling of `x-` layers in `server/hips.py` tile rendering, coverage edge too
- [x] tests; restart the viewer (the running API predated the T109/T120 routes: 404s on /redshift, /community)

## Findings
- The saved maps (`<target>/chemistry/<key>.png`) are per pixel (6.15″) with no smoothing: single hot / cold pixels
  (star residuals, cosmic rays) all over, 1-pixel coverage holes, and `server/hips.py` sampled tiles nearest-pixel,
  so at levels 8-10 the map was blocks with stair-step edges (Orion, `c0838300-m053900-s20`, CO₂ / PAH + Br-α + CO₂).
- Tried on Orion's 4 maps: Gaussian alone (σ 1 px) keeps the speckle as blobs; 3 × 3 median alone leaves grain;
  median + Gaussian σ 0.8 px removes both and keeps the filaments (comparison in the T121 commit's session).
- `pipeline/chemistry.smooth()`: 3 × 3 median (outside coverage counts as 128), Gaussian σ 0.8 px normalised over
  covered pixels, holes filled where ≥ 60 % of the Gaussian neighbourhood has data (1-2 px holes yes, saturated cores
  no), values extended just past the coverage so bilinear tiles get no grey rim. ~0.4 s for an 86′ field, cached
  per file mtime (`load_map`), so once per map.
- "Errors" in Mati's running viewer: its Live API was started 09:49 from a session script before T109/T120 were
  pulled; `/api/community/*` and `/api/targets/<id>/redshift` answered 404 there. A fresh API answers 200. No 5xx in
  its log. Fix = restart from main.

## Questions / needs from others

## Handoff
- Display only: the saved PNG and the numbers in the map's JSON (sigma, counts) are unchanged; no recompute, no
  CONTRACTS change (same routes, same image shape). `SMOOTH_PX = 0` in `pipeline/chemistry.py` turns it off.
- The "map image" link (`.../chemistry/<key>.png`) now serves the smoothed map, same as the sky map.
- Exposure-edge stripes (straight lines in H₂O ice on Orion) are still there: they are real level jumps between
  exposure sets, not pixel noise.

## Notes from others
- 2026-11-15 [Joerg] Review: passed. pytest (chemistry + server) 73 passed. `smooth()` on a synthetic map (step edge 128→200,
  60 hot pixels, coverage hole of 1 px and of 10 × 10 px, uncovered border): 0 hot pixels left, max error away from the
  edge 1 grey level, edge spread over ~4 px (σ 0.8), 1-px hole filled, 10-px hole and border stay uncovered. Not checked
  visually on Orion: its chemistry maps were evicted from the cache (disk full, LRU sweep); worth one look after a rebuild.
