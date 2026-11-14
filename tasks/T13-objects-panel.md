# T13: Detections and known objects: list, status, synthetic badge

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T13-objects-panel` (merged)
- **Depends on / feeds:** T22 (paths overlay, Joerg), T07/T08 (known_objects, detections), CONTRACTS "Detection"

## Goal
Everything the pipeline found is visible and honest: a list of detections and known objects with
their status (known / unknown / artifact), match, motion and score; synthetic ones carry a clear
badge; artifacts are hidden unless asked for; unknown movers stand out. T22 already draws the paths
on the image; T13 adds the list, the counts and the link from list to image.

## Plan
- [x] "Objects" panel in the side bar: one row per detection / known object; status chip, name or
      match, motion (″/h, direction), score, synthetic badge; "show artifacts" toggle (off by default)
- [x] Headline count next to the target name ("N movers: k unknown"), unknown emphasised
- [x] Click a row: ring on the object in the shown frame (own layer, does not touch paths.js); if the
      object has no position in this frame, jump to its first frame
- [x] Browser test checks for this and for T22's overlay (Joerg's agent can't run a browser)

## Findings
- T22 already drew known objects and detections on the image (paths, names, " · synthetic"), so T13
  is the list, the headline and the link from list to image; it does not touch `paths.js`.
- Statuses shown: **unknown** (moves, no match; listed first, headline in amber), **known**
  (detection matched to a catalogued object; the catalogue entry is not listed twice), **known · not
  detected** (in `known_objects` but none of our detections matched it: an honest miss, also useful
  to tune detection), **artifact** (hidden unless "show artifacts").
- Real builds have no `detections` yet (`detect/run.py` does not exist). The headline then says
  "Mover detection has not run on this field yet" instead of "nothing found"; it decides that from
  `provenance` (a detect / JPL entry) or non-empty detections.
- Added browser checks for T22's overlay on the fixture (Joerg's agent can't run a browser).

## Questions / needs from others

## Handoff
- `web/objects.js`, imported by `app.js`; listens to `viewer:target` / `viewer:frame` like `paths.js`.
  Uses the new `showFrame(id)` export of `viewer.js` to jump to an object's first frame.
- Focus ring: own `<g id="focus-layer">` in `#overlay`, drawn after the paths layer.
- For detection (T06–T08): fill `detections` per CONTRACTS and append a provenance entry; the panel
  and headline pick it up without changes.

## Notes from others
(anyone may append here, dated and signed)
