# T22: Movement paths in the viewer

- **Owner:** Joerg  ·  **Status:** review (waiting for a visual check in a browser)
- **Branch:** `joerg/T22-movement-paths`
- **Depends on / feeds:** T19 (`labels`), T07 (`known_objects`), T06/T08 (`detections`); part of
  what T13 (overlay) wants. From the idea "Draw paths, not just positions" in TEAM.md.

## Goal
For every object with a position per frame (labels, known objects, detections), the viewer draws
its path through all frames: a line, a tick per frame, colour from early to late, the current
position highlighted with its name. Slow movers (Barnard's Star moves < 2 px in a year) get a
clearly labelled exaggerated motion arrow so the motion is still visible.

## Plan
- [x] `web/paths.js` + `web/paths.css`: path layer in the existing `#overlay` SVG, own controls
- [x] Hooks in `viewer.js`: one import + three `dispatchEvent` lines; no other change to Mati's code
- [ ] Visual check on the fixture (fake asteroid, synthetic) and a real target with labels
      (Barnard's Star): Joerg, in a browser
- [ ] Browser test checks in `web/tests/browser_test.py`: Joerg's agent can't run Chromium (sandbox
      blocks its Mach-port check-in), so whoever can run that test should add/run them

## Findings
- What it draws: named labels (SIMBAD), known objects and detections by default; catalogue stars
  (Gaia) on a toggle. Moving objects get a line through all their positions, one tick per frame,
  colour blue → orange from the first to the last frame date, and a ring + name at the current
  frame. Anything that moves less than 0.3 px over the whole series counts as still: ring only.
- Slow movers: a path under 3 px gets a dashed arrow along its motion, 12 px long, labelled
  "motion ×k, not to scale". Barnard's Star moves 1.7 px in our year of data, so it gets ×7.
- A detection matched to a known object replaces that object, so a body isn't named twice.
- Only checked so far: JS syntax (`node --check`) and a code read. Not yet seen rendered.

## Questions / needs from others
- [to Mati] T22 adds two dispatch lines to `viewer.js` (events `viewer:target`, `viewer:frame`) and
  one `<script>` import. The path layer lives in `web/paths.js`; T13 can reuse the same events.

## Handoff

## Notes from others
- 2026-11-14 [Mati] Fine with the two hooks in `viewer.js`. FYI T21 changed `web/api.js` (`DEFAULT_API`
  now from the page's host), added `web/dev.py` and edited `web/README.md`; no overlap with T22.
  `python web/dev.py` is the quickest way to see your layer.
