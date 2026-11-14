# T51: `detect/run.py`: known asteroids and comets in every build

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T51-detect-run`
- **Depends on / feeds:** T07 (JPL known objects), T08 (classify), T06 (mover detection, Jonathan)

## Goal
`server/builder.py` calls `detect.run.detect(target_dir)` after every build, but the module never
existed, so every field showed "Objects (0)". Add it with what already exists: the JPL lookup
(T07) fills `known_objects`, and the classifier (T08) runs once there are detections. T06 adds
track finding inside the same function later; nothing else has to change.

## Plan
- [x] `detect/run.py`: `detect(target_dir)` + `python -m detect.run <target_dir>`
- [x] JPL failure never fails a build (logged in provenance, empty `known_objects`)
- [x] No "detect" provenance entry while there is no mover detection, so the viewer keeps saying
      "Mover detection has not run" and shows known objects as "catalogued"
- [x] Builds don't wait: `GET /api/targets/<id>/objects` (202/200), started after every live build;
      viewer polls it and reloads target.json
- [x] Fast: local MPC orbit catalogue (`detect/mpcorb.py`), SkyBoT and JPL sb_ident as fallbacks
- [x] Tests (offline), tried on the ecliptic field RA 180 Dec 0

## Findings
Ecliptic field RA 180, Dec 0, 15', 36 frames in 18 visits (2025-05 to 2026-09), V <= 20:

| Candidate search | Time per field | Found | Notes |
|---|---|---|---|
| JPL sb_ident (T07 as it was) | 6+ min, then 429 | - | 20 requests / 5 min per client, one per visit |
| IMCCE SkyBoT, visits in parallel | 24-28 s | 7 | ~13 s per cone search |
| Local MPCORB (`detect.mpcorb`) | ~2.5 s in the server (3.7 s cold CLI) | same 7 | positions within 0.05" of JPL Horizons (1 px = 6.15") |

Local method: two-body positions of all 1.58 M MPCORB asteroids, one pass per epoch with a search
radius widened by each object's motion, then exact two-body per visit, then Sun + 8 planets RK4
(1-day steps) from the catalogue epoch (2026-06-09) to each frame time, light time, observer =
SPHEREx (Horizons state vectors, 1 request; geocentre if that fails). Two-body vs n-body after 388
days: median 0.010 deg, 99% 0.027 deg, worst 0.73 deg (near-Earth objects), hence margins of 0.15
deg (1.5 deg for q < 1.3 AU). Comets are not in the local path yet (SkyBoT fallback has them).

## Questions / needs from others
- [to Jonathan] T06: put track finding at the marked spot in `detect/run.py`; classify already runs
  after it when there are detections.

## Handoff
One-time setup per machine (data/ is gitignored, ~95 MB download, 160 MB built; MPC updates daily):

    python -m detect.mpcorb fetch && python -m detect.mpcorb build

Without it, the objects job falls back to SkyBoT (~25 s), then JPL sb_ident (minutes).
`python -m detect.mpcorb find data/targets/<id>` shows what would be found, with timings.

## Notes from others
