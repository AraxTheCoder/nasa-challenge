# T94: Missing tiles on the map (failed tiles never retried, false-colour epochs 422, holes near the poles)

- **Owner:** Jonathan  ·  **Status:** doing
- **Branch:** `main`
- **Depends on / feeds:** T36 (sky.js), T89 (false colour), T90 (web/)

## Goal
No tile stays missing when its data exists: a tile that failed (server restart, timeout, busy VM) is asked
again later; false-colour field epochs load; no holes at the poles when zooming in.

## Plan
- [ ] sky.js: a tile that failed 5 times is not given up for good: asked again after a pause (and on the
      next view change), so a restarted or briefly busy server never leaves holes until a reload
- [ ] Live API: `/api/hips/<id>/e<n>c` and `e<n>d<det>` answer (the epoch route took `e1c` as epoch "1c": 422)
- [ ] Holes near the poles when zooming in: find and fix

## Findings
- 2026-11-14: Jonathan's screenshot (order 3, false colour): "errors 30", 8 tiles blurry. The Live API served no
  error; the API was restarted several times while the page was open: those tiles failed 5 times and were never
  asked again (`t.state = "failed"`).
- 2026-11-14: `GET /api/hips/<id>/e1c/properties` -> 422 (39 times in the log): false-colour field epochs never showed.

## Questions / needs from others

## Handoff

## Notes from others
