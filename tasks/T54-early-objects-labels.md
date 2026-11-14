# T54: Known objects + labels start while the images download

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T52-more-labels`
- **Depends on / feeds:** T51, T37, pipeline/build.py

## Goal
Known objects and labels need only frame times and the field geometry, not pixels: start them when the frames are chosen, so a new field is complete when its frames are.

## Plan
- [x] Hook in pipeline.build once frames are chosen (`build_target(early=...)`, `remap_to_frames`)
- [x] Server starts objects + labels from it, merges when the build lands
- [x] Frames dropped by a failed download are dropped from tracks too

## Findings
New field RA 182 Dec -0.5 (2026-11-14): query 0.8 s, download 9.6 s, align 1.4 s, ready at 11.8 s with
`labels_requested` and `objects_requested` already set (148 labels, 2 known asteroids). Before: objects
+2.5 s and labels +2-3 s after the frames, as extra requests from the viewer. If the early work is not done
within 20 s after the frames, the on-request jobs (`/labels`, `/objects`) take over as before.

## Questions / needs from others

## Handoff

## Notes from others
