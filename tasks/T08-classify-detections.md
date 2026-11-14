# T08: Classify detections as known / unknown / artifact

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T08-classify` (merged)
- **Depends on / feeds:** T06 (detections, Jonathan; not started yet), T07 (`known_objects`), T19
  (`labels`), `pipeline.motion` (T23); feeds the viewer (T13 objects panel, T22 paths) and T09

## Goal
Every detection gets an honest `status`: **known** (it is a catalogued asteroid/comet: matches a
`known_objects` track frame by frame), **artifact** (not a real mover: too few frames, not a straight
track, rate impossible, sitting on a catalogued star, …) or **unknown** (moves like a real object and
matches nothing). Plus `matched_object`, `score` (0–1) and `motion`. Built against CONTRACTS
"Detection" so T06's output can go straight through it.

## Plan
- [x] `detect/classify.py`: `classify_detections(target) -> target` (touches only `detections` + provenance)
- [x] Known: per shared frame, distance to each known object's predicted position; match if the
      median is within a tolerance (pixels; JPL positions + SPHEREx PSF) on ≥ 2 frames, or on the one
      frame for single-frame tracks
- [x] Artifact rules, each with a plain-words reason; score from track length, straightness, rate sanity
- [x] `motion` (rate ″/h, pa) from the track when T06 leaves it out
- [x] CLI `python -m detect.classify <target_dir>`; offline tests with synthetic targets
- [x] Viewer: show the reason for artifacts / score in the objects panel if useful

## Findings
- Rules (first match wins): known asteroid/comet (median ≤ 2 px to a `known_objects` track over shared
  frames, ≥ 2 frames unless the detection has one) → known moving catalogued star (labels with a motion
  class other than `still`, e.g. Barnard's Star) → artifact: on a still catalogued star / one frame only /
  doesn't move (< 0.5 px) / off a straight line inside a visit (> 1 px RMS) / faster than 2°/h → unknown.
- Each detection gets a plain-words `reason` (CONTRACTS v0.9), shown in the objects panel.
- `pipeline.motion.summarize` skips frame pairs < 0.05 h apart, but SPHEREx exposures in a visit are
  ~2 min apart, so its within-epoch rate is 0 for burst movers. T08 computes the within-visit rate
  itself (note left for Joerg in tasks/T23).
- Unknown movers on fields where the JPL lookup (T07) never ran say so in the reason and score ≤ 0.6:
  "unknown" is only meaningful after checking the catalogue.
- No real detections exist yet (T06 not started), so it is tested on synthetic tracks: one per rule,
  15 tests, plus the fixture (`Fake asteroid` → known, score 1.00).

## Questions / needs from others
- [to Jonathan, T06] Suggested order in `detect.run.detect()`: find tracks → `add_known_objects(target)`
  (T07) → `classify_detections(target)` (T08). Tracks need `frame_id`, `ra_deg`, `dec_deg`, `x`, `y` per
  frame (CONTRACTS); `status` can be left out, T08 sets it.

## Handoff
- `python -m detect.classify data/targets/<id>` (writes `detections` + one provenance entry).
- Python: `classify_detections(target)`; `classify_one(det, target)` for a single detection.
- Thresholds are constants at the top of `detect/classify.py`; tune them on real detections (T09).
- Tests: `python -m pytest detect/test_classify.py`.

## Notes from others
(anyone may append here, dated and signed)
- 2026-11-14 [Joerg] For T08: `pipeline.motion.summarize(track, frames, pixel_scale_arcsec)` (CONTRACTS
  v0.5) works on any `detections[].track` and returns shift, rate, direction and a class (`still`,
  `proper motion`, `fast mover`, `distant body?`) with a plain-words note. "Moves less than 0.3 px over
  the whole series" (`still`) is a cheap artifact/static-source hint. Tests: `pipeline/test_motion.py`.
