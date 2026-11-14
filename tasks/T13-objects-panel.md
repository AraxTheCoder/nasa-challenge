# T13: Detections and known objects: list, status, synthetic badge

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T13-objects-panel`
- **Depends on / feeds:** T22 (paths overlay, Joerg), T07/T08 (known_objects, detections), CONTRACTS "Detection"

## Goal
Everything the pipeline found is visible and honest: a list of detections and known objects with
their status (known / unknown / artifact), match, motion and score; synthetic ones carry a clear
badge; artifacts are hidden unless asked for; unknown movers stand out. T22 already draws the paths
on the image; T13 adds the list, the counts and the link from list to image.

## Plan
- [ ] "Objects" panel in the side bar: one row per detection / known object; status chip, name or
      match, motion (″/h, direction), score, synthetic badge; "show artifacts" toggle (off by default)
- [ ] Headline count next to the target name ("N movers: k unknown"), unknown emphasised
- [ ] Click a row: ring on the object in the shown frame (own layer, does not touch paths.js); if the
      object has no position in this frame, jump to its first frame
- [ ] Browser test checks for this and for T22's overlay (Joerg's agent can't run a browser)

## Findings

## Questions / needs from others

## Handoff

## Notes from others
(anyone may append here, dated and signed)
