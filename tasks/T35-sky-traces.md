# T35: Tracing over the stitched sky

- **Owner:** Joerg  ·  **Status:** review (needs a look in a browser)
- **Branch:** `joerg/T35-sky-traces`
- **Depends on / feeds:** T30/T32 (Jonathan: explore map + per-epoch HiPS), T19/T23/T34 (labels,
  motion, importance), T07 (known objects), T06/T08 (detections)

## Goal
On the explore map, the shown field's important objects carry their traces: a line through their
per-frame positions, one marker per epoch, the current epoch highlighted while the map blinks, and the
name with a popup. Slow movers get a labelled, exaggerated direction arrow so motion is visible at map
scale.

## Plan
- [x] Two hooks in `web/explore.js` (Jonathan's): `getAladin()` export and an `explore:epoch` event in
      `showEpoch` (note in TEAM.md Log)
- [x] `web/traces.js`: overlay + catalogue per shown target; which objects: movers, detections,
      importance ≤ 2 labels; per-epoch mean positions; arrow for paths < 3 map-visible units
- [x] Toggle "Traces" in the explore bar
- [x] Check on the five official fields

## Findings
- Selection on the five real fields: Barnard's star (3 epochs, 11.5″ reach), * eps Ind B and its host
  * eps Ind (4 epochs, ~6.7″), WISEA J085510.74-071442.5 (3 epochs, 8.3″): traces + dashed arrow
  labelled "motion ×k, not to scale" (k ≈ 8-13 at 1.5′ arrow length). RW Aur and R Dra don't move:
  marker + name only. Checked by running the selection code in Node on the cached target.json files;
  the Aladin drawing itself is not seen yet (no browser in Joerg's agent).
- Which objects: detections (not artifacts), known objects not matched by a detection, labels with
  importance 0-1, and importance 2 if they move.

## Questions / needs from others

## Handoff
- `web/traces.js`, loaded from `paths.js`. Uses `getAladin()` and the `explore:epoch` event, both
  added to `web/explore.js` (Jonathan's file, 2 small additions). Toggle "Traces" sits next to the
  epoch buttons in the explore bar.

## Notes from others
