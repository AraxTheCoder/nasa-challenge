# T35: Tracing over the stitched sky

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T35-sky-traces`
- **Depends on / feeds:** T30/T32 (Jonathan: explore map + per-epoch HiPS), T19/T23/T34 (labels,
  motion, importance), T07 (known objects), T06/T08 (detections)

## Goal
On the explore map, the shown field's important objects carry their traces: a line through their
per-frame positions, one marker per epoch, the current epoch highlighted while the map blinks, and the
name with a popup. Slow movers get a labelled, exaggerated direction arrow so motion is visible at map
scale.

## Plan
- [ ] Two hooks in `web/explore.js` (Jonathan's): `getAladin()` export and an `explore:epoch` event in
      `showEpoch` (note in TEAM.md Log)
- [ ] `web/traces.js`: overlay + catalogue per shown target; which objects: movers, detections,
      importance ≤ 2 labels; per-epoch mean positions; arrow for paths < 3 map-visible units
- [ ] Toggle "Traces" in the explore bar
- [ ] Check on the five official fields

## Findings

## Questions / needs from others

## Handoff

## Notes from others
