# T22: Movement paths in the viewer

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T22-movement-paths`
- **Depends on / feeds:** T19 (`labels`), T07 (`known_objects`), T06/T08 (`detections`); part of
  what T13 (overlay) wants. From the idea "Draw paths, not just positions" in TEAM.md.

## Goal
For every object with a position per frame (labels, known objects, detections), the viewer draws
its path through all frames: a line, a tick per frame, colour from early to late, the current
position highlighted with its name. Slow movers (Barnard's Star moves < 2 px in a year) get a
clearly labelled exaggerated motion arrow so the motion is still visible.

## Plan
- [ ] `web/paths.js` + `web/paths.css`: path layer in the existing `#overlay` SVG, own controls
- [ ] Two hook lines in `viewer.js` (target shown, frame shown); no other change to Mati's code
- [ ] Test on the fixture (fake asteroid, synthetic) and a real target with labels (Barnard's Star)
- [ ] Browser test checks added to `web/tests/browser_test.py`

## Findings

## Questions / needs from others
- [to Mati] T22 adds two dispatch lines to `viewer.js` (events `viewer:target`, `viewer:frame`) and
  one `<script>` import. The path layer lives in `web/paths.js`; T13 can reuse the same events.

## Handoff

## Notes from others
- 2026-11-14 [Mati] Fine with the two hooks in `viewer.js`. FYI T21 changed `web/api.js` (`DEFAULT_API`
  now from the page's host), added `web/dev.py` and edited `web/README.md`; no overlap with T22.
  `python web/dev.py` is the quickest way to see your layer.
