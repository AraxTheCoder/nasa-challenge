# T79: click to measure, on the image and on the map

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T79-click-spectrum`
- **Depends on / feeds:** T49 (photometry), T63 (spectrum context), T66 (all exposures), T36 (map)

## Goal
Clicking a pixel should give its spectrum. Before: only after pressing "Measure a star", and the map had
no click action at all.

## Plan
- [ ] Frame image: a plain click measures there (label clicks still open the inspector)
- [ ] Map: a click (not a drag, not a double-click) measures that sky point from all exposures, snapped to a
      labelled dot within a few px; marker on the map; works without a built field
- [ ] `GET /api/photometry?ra=&dec=`: all exposures at any position (same job as `?all=1`)

## Findings

## Questions / needs from others
- [to Jonathan] `/app/` has no photometry panel; port the map click + panel when you want it there.

## Handoff

## Notes from others
