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
- [ ] `detect/run.py`: `detect(target_dir)` + `python -m detect.run <target_dir>`
- [ ] JPL failure never fails a build (logged in provenance, empty `known_objects`)
- [ ] No "detect" provenance entry while there is no mover detection, so the viewer keeps saying
      "Mover detection has not run" and shows known objects as "catalogued"
- [ ] Tests (offline, fake JPL), try on a field near the ecliptic

## Findings

## Questions / needs from others
- [to Jonathan] T06: put track finding at the marked spot in `detect/run.py`; classify already runs
  after it when there are detections.

## Handoff

## Notes from others
