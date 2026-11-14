# T07: Known small bodies from JPL → `known_objects`

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T07-jpl-known` (merged)
- **Depends on / feeds:** T04 (target.json); feeds T08 (classify detections), viewer (T22 paths, T13 objects panel)

## Goal
For every frame of a target, the catalogued asteroids and comets in the field, predicted as seen from
SPHEREx (not the geocentre), written to `known_objects` per CONTRACTS.

## Plan
- [x] SPHEREx geocentric state vectors (ICRF, km, km/s) per frame time from JPL Horizons (ID -163182)
- [x] JPL SB Identification (`sb_ident.api`) per unique frame time with `xobs` = that state vector
- [x] Merge by object name → positions per frame; sky → pixel with the target grid; keep what is in the field
- [x] `python -m detect.known_objects <target_dir>`: updates only `known_objects` + provenance (query + UTC)
- [x] Unit tests with recorded API answers (offline); live run on the real Barnard's Star field

## Findings
- JPL `sb_ident` has no "observer = spacecraft ID"; it takes the observer's geocentric ICRF state
  vector (`xobs`, km + km/s). Horizons gives SPHEREx's vector (`COMMAND='-163182'`, `CENTER='500@399'`,
  `REF_PLANE='FRAME'`); |r| ≈ 7030 km, i.e. ~650 km altitude, as expected.
- `sb_ident` speed: first pass 18–36 s per call; precise two-pass > 180 s (timed out) near the
  ecliptic with thousands of objects. First-pass "estimated error" says ~228″, but the actual offset
  for 6779 Perrine was ~16″; lost asteroids (1927 LA, 1939 RR) come back tens of degrees off.
  So: first pass only for candidates (V ≤ 20 by default), Horizons for positions.
- Horizons can observe from the spacecraft (`CENTER='500@-163182'`): ~0.7 s per object, precise.
- Horizons gives 503 when called in parallel → strictly one request at a time + retry/backoff.
  Two detectors share a frame time; repeated TLIST times make Horizons answer "Bad dates" → dedupe.
  Fragmented periodic comets (332P) match several records → `NOFRAG`.
- Live check (frame times of the real Barnard's Star build, centre moved to an ecliptic spot, first
  two visits): 26 JPL requests, 69 s; 6779 Perrine at pixel (72.52, 72.50) for a field centred on its
  predicted position, i.e. exactly at the centre of the 146×146 grid.
- Official test fields are far from the ecliptic (Barnard 28°, WISE 0855 ~23°, RW Aur ~8°), so expect
  few or no known asteroids there; Barnard's field has none (sb_ident: "no matching records").
- Viewer: the JPL lookup is not mover detection; known objects without a detection step show as
  "catalogued" and the headline counts them (`web/objects.js`).

## Questions / needs from others
- [to Jonathan, T06 / detect.run] Please call `detect.known_objects.add_known_objects(target)` in
  `detect.run.detect()` (or after `add_labels` in `pipeline.build`), so live builds get known objects.
  Cost: ~20 s per visit for sb_ident (two in parallel) + ~1 s per candidate for Horizons, i.e. a few
  minutes for a 15–18-visit field near the ecliptic, much less far from it. Until then use the CLI.

## Handoff
- `python -m detect.known_objects data/targets/<id> [--vmag 20]` adds `known_objects` to a built target
  (writes only `known_objects` + provenance; the API serves it on the next load).
- Python: `add_known_objects(target, jpl=None, vmag_lim=20)`; `find_known_objects(...)` returns the list
  without touching the target. `Jpl` is the HTTP client (swap it in tests, see `FakeJpl`).
- Tests: `python -m pytest detect/test_known_objects.py` (offline, 15 tests).

## Notes from others
(anyone may append here, dated and signed)
