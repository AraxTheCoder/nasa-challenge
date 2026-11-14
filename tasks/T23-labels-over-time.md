# T23: Labelling over time: moving objects and image series

- **Owner:** Joerg  ·  **Status:** doing
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
- [ ] Motion summary per label: total shift over the series in px and ″, rate (″/yr or ″/h),
      direction (PA east of north). Additive field in `target.json` (CONTRACTS change + Decisions line)
- [ ] Motion class per object, rule-based (rough numbers in TEAM.md Ideas): still (< 0.3 px over the
      series), nearby star / brown dwarf (moves between epochs only, ≲ 10″/yr), asteroid-like (fast,
      seen in one burst only, ~150 px/day for the main belt), distant solar-system body (big jump
      between epochs, slow drift within one). For detections: agree the rule with Jonathan (T06/T08)
- [ ] Show the class next to the name in the viewer (with T22's layer)
- [ ] Object inspector: click an object → side panel with coordinates, catalogue matches (SIMBAD,
      Gaia), observation history per frame (time, epoch, wavelength, position, and brightness at
      that spot), motion data; Barnard's Star as the demo object. Grows out of T22's pinned tooltip;
      coordinate with Mati's objects list (T13)
- [ ] Cleaner labels: avoid overlapping names (shift or hide lower-priority ones), show catalogue
      numbers only on hover, fewer rings at wide fields
- [ ] Trail image: one burst or one epoch summed into one picture, movers as dot rows or streaks
- [ ] Shift-and-stack prototype along a known motion (Barnard's Star first), then along guessed
      motions as a search tool for T10
- [ ] Try it on the official test targets once `build_target` produces real frames (T02–T04)

## Findings
- From T19: label accuracy 0.4″ (0.07 px) on stationary stars; Barnard's Star moves 10.4″/yr
  = 1.7 px over our year of data, so its path is short and needs the exaggerated arrow.
- Rough motion scales (my own estimates, not yet measured): main-belt asteroid ~0.25°/day;
  nearby star ≤ 10″/yr; a body at 500 AU swings ±0.11°/yr from Earth's orbit, up to ~14′ between
  two epochs (about one default 15′ field) and ~1 px/day within an epoch.

## Questions / needs from others
- [to Jonathan] Detections (T06/T08) already carry `motion.rate_arcsec_per_hr` and `pa_deg`. The
  motion class could be computed in `detect` (your side) or in a shared helper; which do you prefer?

## Handoff

## Notes from others
