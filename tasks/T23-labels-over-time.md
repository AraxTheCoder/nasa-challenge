# T23: Labelling over time: moving objects and image series

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T23-labels-over-time`
- **From Joerg's feature list (2026-11-14):** object inspector, cleaner labels, motion vectors.
- **Depends on / feeds:** builds on T19 (catalogue labels, done) and T22 (paths in the viewer,
  review); uses T07 (`known_objects`) and T06/T08 (`detections`, Jonathan) once they exist; feeds
  T10 ("Planet X mode") and the demo. Moved onto the Board from the Ideas "Draw paths", "Motion
  classification", "Trail image" and "Shift-and-stack" (TEAM.md, 2026-11-14).

## Goal
A label should not just name a dot in one frame: across a series of frames it should show **how the
object moves** and what that motion suggests it is. For every labelled object, known object and
detection: its path through the frames, its rate and direction, and a plain-words motion class
(still, nearby star, asteroid-like, distant solar-system body). Plus image views that make motion
visible without blinking: a trail image and, later, shift-and-stack along a motion.

## Plan
- [x] Catalogue labels that follow their object frame by frame, with proper motion (T19)
- [~] Paths in the viewer: line, tick per frame, early→late colour, exaggerated arrow for slow
      movers (T22, waiting for a visual check)
- [x] Motion summary per label: `pipeline/motion.py`, `labels[].motion` (CONTRACTS v0.5)
- [x] Motion class per label (`still`, `proper motion`, `fast mover`, `distant body?`), rule-based (rough numbers in TEAM.md Ideas): still (< 0.3 px over the
      series), nearby star / brown dwarf (moves between epochs only, ≲ 10″/yr), asteroid-like (fast,
      seen in one burst only, ~150 px/day for the main belt), distant solar-system body (big jump
      between epochs, slow drift within one). For detections: agree the rule with Jonathan (T06/T08)
- [x] Show the class next to the name in the viewer + in the hover info
- [x] Object inspector (`web/inspector.js`): click an object → side panel with coordinates, catalogue matches (SIMBAD,
      Gaia), observation history per frame (time, epoch, wavelength, position, and brightness at
      that spot), motion data; Barnard's Star as the demo object. Grows out of T22's pinned tooltip;
      coordinate with Mati's objects list (T13)
- [x] Cleaner labels (in `paths.js`): names try right/left/above/below and skip taken spots,
      movers first; hidden names are counted in the legend, hover still works. Was: avoid overlapping names (shift or hide lower-priority ones), show catalogue
      numbers only on hover, fewer rings at wide fields
- [x] Trail view in the viewer (`web/trail.js`): frames of this epoch or all epochs stacked with
      "brightest pixel wins"; steady stars stay dots, movers leave rows of dots. Browser-only, no pipeline change
- [x] Shift-and-stack: `python -m pipeline.stack <target_dir> [--object <id|name>]` writes plain vs
      shifted median stacks side by side (synthetic input stamped SYNTHETIC). On the fixture the fake
      asteroid vanishes from the plain stack and is a sharp dot in the shifted one. Next: guessed
      motions as a search tool for T10 (Jonathan)
- [-] Try it on the official test targets: dropped 2026-11-14. `build_target` makes real fields now and every label has a position in every frame of every epoch (134/134 on c0767409-p243202-s15, 36 frames, epochs 1–3)

## Findings
- Motion classes on the real Barnard's Star field: Barnard's Star (SIMBAD and its Gaia twin) =
  `proper motion`, 10.39″/yr toward N (catalogue: 10.39); the other 105 objects `still`. The
  fixture's fake asteroid = `fast mover`, 3.1″/h. 5 unit tests in `pipeline/test_motion.py`.
- A unit test caught that a body jumping away and back would have counted as `still` (first and
  last position close together); `still` now uses the farthest excursion (`reach_arcsec`).
- From T19: label accuracy 0.4″ (0.07 px) on stationary stars; Barnard's Star moves 10.4″/yr
  = 1.7 px over our year of data, so its path is short and needs the exaggerated arrow.
- Rough motion scales (my own estimates, not yet measured): main-belt asteroid ~0.25°/day;
  nearby star ≤ 10″/yr; a body at 500 AU swings ±0.11°/yr from Earth's orbit, up to ~14′ between
  two epochs (about one default 15′ field) and ~1 px/day within an epoch.

## Questions / needs from others
- [to Mati] The inspector opens on a `paths:select` event with `{obj}` (same shape as in
  `paths.js`: name, info, source, mag, otype, pm, motion, positions, synthetic). If your objects
  list (T13) dispatches it on row click, list and image open the same panel.
- [to Jonathan] Detections (T06/T08) already carry `motion.rate_arcsec_per_hr` and `pa_deg`. The
  motion class could be computed in `detect` (your side) or in a shared helper; which do you prefer?

## Handoff

## Notes from others
- 2026-11-14 [Mati] Real Barnard's Star field (271 labels) still looks crowded. New open task T34: only
  the most important names always visible, the rest on hover (proposal in tasks/T34). It touches
  `paths.js`, so you may want it; otherwise someone from C picks it up later.
- 2026-11-14 [Mati] `pipeline.motion.summarize` only counts frame pairs > 0.05 h (3 min) apart as
  "within an epoch", but SPHEREx exposures inside a visit are ~2 min apart, so a fast mover seen in one
  burst gets `max_rate_within_epoch_arcsec_per_hr = 0` and may not be classed `fast mover`. T08 computes
  its own within-visit rate; you may want to lower the threshold (or measure first-to-last per visit).
