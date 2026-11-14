# T08: Classify detections as known / unknown / artifact

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T08-classify`
- **Depends on / feeds:** T06 (detections, Jonathan; not started yet), T07 (`known_objects`), T19
  (`labels`), `pipeline.motion` (T23); feeds the viewer (T13 objects panel, T22 paths) and T09

## Goal
Every detection gets an honest `status`: **known** (it is a catalogued asteroid/comet: matches a
`known_objects` track frame by frame), **artifact** (not a real mover: too few frames, not a straight
track, rate impossible, sitting on a catalogued star, …) or **unknown** (moves like a real object and
matches nothing). Plus `matched_object`, `score` (0–1) and `motion`. Built against CONTRACTS
"Detection" so T06's output can go straight through it.

## Plan
- [ ] `detect/classify.py`: `classify_detections(target) -> target` (touches only `detections` + provenance)
- [ ] Known: per shared frame, distance to each known object's predicted position; match if the
      median is within a tolerance (pixels; JPL positions + SPHEREx PSF) on ≥ 2 frames, or on the one
      frame for single-frame tracks
- [ ] Artifact rules, each with a plain-words reason; score from track length, straightness, rate sanity
- [ ] `motion` (rate ″/h, pa) from the track when T06 leaves it out
- [ ] CLI `python -m detect.classify <target_dir>`; offline tests with synthetic targets
- [ ] Viewer: show the reason for artifacts / score in the objects panel if useful

## Findings

## Questions / needs from others

## Handoff

## Notes from others
(anyone may append here, dated and signed)
- 2026-11-14 [Joerg] For T08: `pipeline.motion.summarize(track, frames, pixel_scale_arcsec)` (CONTRACTS
  v0.5) works on any `detections[].track` and returns shift, rate, direction and a class (`still`,
  `proper motion`, `fast mover`, `distant body?`) with a plain-words note. "Moves less than 0.3 px over
  the whole series" (`still`) is a cheap artifact/static-source hint. Tests: `pipeline/test_motion.py`.
