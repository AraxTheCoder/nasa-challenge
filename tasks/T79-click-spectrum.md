# T79: click to measure, on the image and on the map

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T79-click-spectrum`
- **Depends on / feeds:** T49 (photometry), T63 (spectrum context), T66 (all exposures), T36 (map)

## Goal
Clicking a pixel should give its spectrum. Before: only after pressing "Measure a star", and the map had
no click action at all.

## Plan
- [x] Frame image: a plain click measures there (label clicks still open the inspector)
- [x] Map: a click (not a drag, not a double-click) measures that sky point from all exposures, snapped to a
      labelled dot within a few px; marker on the map; works without a built field
- [x] `GET /api/photometry?ra=&dec=`: all exposures at any position (same job as `?all=1`)

## Findings
Browser check on WISE 0855 (2026-11-14): plain click on the frame image -> quick spectrum (31 of 34 frames),
then all exposures; click on the map outside the field -> 245 of 248 exposures at that point, crosshair on
the map, panel right under the map. Double-click still zooms (the click waits 280 ms).

## Questions / needs from others
- [to Jonathan] `/app/` has no photometry panel; port the map click + panel when you want it there.

## Handoff
Click anywhere: image (field) or map (any sky point). "Measure a star" still works as before.

## Notes from others
