# T07: Known small bodies from JPL → `known_objects`

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T07-jpl-known`
- **Depends on / feeds:** T04 (target.json); feeds T08 (classify detections), viewer (T22 paths, T13 objects panel)

## Goal
For every frame of a target, the catalogued asteroids and comets in the field, predicted as seen from
SPHEREx (not the geocentre), written to `known_objects` per CONTRACTS.

## Plan
- [ ] SPHEREx geocentric state vectors (ICRF, km, km/s) per frame time from JPL Horizons (ID -163182)
- [ ] JPL SB Identification (`sb_ident.api`) per unique frame time with `xobs` = that state vector
- [ ] Merge by object name → positions per frame; sky → pixel with the target grid; keep what is in the field
- [ ] `python -m detect.known_objects <target_dir>`: updates only `known_objects` + provenance (query + UTC)
- [ ] Unit tests with recorded API answers (offline); live run on the real Barnard's Star field

## Findings

## Questions / needs from others

## Handoff

## Notes from others
(anyone may append here, dated and signed)
