# T94: Missing tiles on the map (failed tiles never retried, false-colour epochs 422, holes near the poles)

- **Owner:** Jonathan  ·  **Status:** doing
- **Branch:** `main`
- **Depends on / feeds:** T36 (sky.js), T89 (false colour), T90 (web/)

## Goal
No tile stays missing when its data exists: a tile that failed (server restart, timeout, busy VM) is asked
again later; false-colour field epochs load; no holes at the poles when zooming in.

## Plan
- [x] sky.js: a tile that failed 5 times is not given up for good: asked again after a pause (and on the
      next view change), so a restarted or briefly busy server never leaves holes until a reload
- [x] Live API: `/api/hips/<id>/e<n>c` and `e<n>d<det>` answer (the epoch route took `e1c` as epoch "1c": 422)
- [x] Holes near the poles when zooming in: found (not the poles: the VM's disk was full); caches capped
- [ ] Free the VM's disk and deploy (needs Jonathan's OK: deleting cache on the VM was blocked)

## Findings
- 2026-11-14: Jonathan's screenshot (order 3, false colour): "errors 30", 8 tiles blurry. The Live API served no
  error; the API was restarted several times while the page was open: those tiles failed 5 times and were never
  asked again (`t.state = "failed"`).
- 2026-11-14: `GET /api/hips/<id>/e1c/properties` -> 422 (39 times in the log): false-colour field epochs never showed.

- 2026-11-14 root cause of the holes (also near the poles): the tile VM's 30 GB disk was full (data/raw/s3chunks
  19 GB, vm_cutouts 4.6 GB, no cap): every tile needing new rows -> HTTP 500 (513 in 2 h, "No space left on device").
  The balancer then pushed the VM to 0.0 tiles/s for good and this PC took every tile (12 at once, ~300 s each).
  Fixes: `tilegen/janitor.py` caps the caches (VM: chunks 8 GB, cutouts 4 GB, tiles 4 GB, 3 GB kept free; Live API:
  chunks 10 GB, map tiles 10 GB, 5 GB free; env vars to change); a full disk only costs the cache now (tile still
  served, header cache skipped); the balancer backs off by halving with a floor (0.2 tiles/s) and recovers.
- 2026-11-14 a pole tile (order 6, Npix 4095) renders locally in 10.6 s: no pole-specific bug found.
- 2026-11-14 `hips.py` crashed on frames with `"detector": null` (fixture) in the colour layers: fixed.

- 2026-11-14 "queued 233 visible" at whole-sky zoom: a survey-pass layer (orders 6-7 only) was drawn at
  "screen wants -1", clamped up to order 6 over 240° of sky. sky.js skips (draws / preloads nothing of) an overlay
  while the view is more than one order coarser than its first order; zooming out stops at order 0 (no order -1).
  Both checked in web/tests/overview_check.mjs (each fails without its fix).
- 2026-11-14 the local chunk cache had 17 GB: the Live API's janitor trims it to 10 GB.

## Questions / needs from others

## Handoff

## Notes from others
- 2026-11-14 [Mati]: one more way tiles stay "loading": `load()` in `web/sky.js` has no time limit on its
  `fetch`. When the Live API was OOM-killed tonight (twice, 23:1x and 23:27) the downloads in flight never got an
  answer in Mati's browser (Windows browser -> WSL relay), each kept one of the 6 slots (`st.loads`), and with
  all 6 taken no tile loaded again until a reload (the log showed no tile requests at all from that tab).
  Idea: a timeout (e.g. `AbortSignal.any([job.ctrl.signal, AbortSignal.timeout(60000)])`, ~60 s because live
  renders can be slow) that is retried like any other failure, not treated as "left the screen".
