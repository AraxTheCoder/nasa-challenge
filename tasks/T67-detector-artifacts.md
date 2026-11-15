# T67: B: "Follows the detector, not the sky" artifact rule: a detection fixed in detector pixels while its sky position jumps (ghost, persistence, hot pixel) is an artifact

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T67-detector-artifacts`
- **Depends on / feeds:** T06, T08

## Goal
Detector artifacts are not reported as movers.

## Plan
- [x] Map each sighting back to native detector pixels (cutout WCS "A": 0-based active pixel coordinates, `CRPIX1A/2A`)
- [x] Same detector pixel lit in another image pointing elsewhere, other detector empty there → artifact (hot pixel)
- [x] Earlier image (≤ 24 h) with a ≥ 20× brighter source (S/N ≥ 100) on that pixel → artifact (afterglow)
- [x] Seen on one detector only → already dropped by T06 step 3 (twin check), nothing to add
- [x] Run on the 8 cached real fields; tests in detect/test_movers.py

## Findings
- `detect/movers.py` `same_pixel()` → `evidence.same_pixel {looked, lit, persist}` (CONTRACTS v0.32); movers VERSION 2.
  `detect/classify.py` rule 3a (RULES_VERSION 3): `persist >= 1` or `lit >= 1` in ≥ half of `looked` = artifact.
- Why it matters: an afterglow is in *both* simultaneous detectors (both saw the bright star), so T06's twin check
  lets it through. A real star landing on the pixel elsewhere is told apart by the other detector also showing it.
- Real data (2026-11-15, all 8 cached fields): the 3 T06 candidates stay `unknown`; `looked` is 0, 0 and 1. Our
  cutouts are small parts of the detector, and images from other moments mostly cover other detector areas, so
  the check can seldom run. It costs nothing when it can't.
- Fields whose mover search already ran keep their old detections (no `same_pixel`) until rebuilt.
From idea I12 in TEAM.md (moved to the Board by Mati, 2026-11-14). B, `detect/classify.py`. ~1 h.

## Questions / needs from others

## Handoff
Done and merged. To look at it: `python -m detect.movers data/targets/<id>` prints `same_pixel` per detection.

## Notes from others
