# T53: Comets in the local orbit catalogue

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T52-more-labels`
- **Depends on / feeds:** T51 (detect/mpcorb.py)

## Goal
Known comets in `known_objects` from the MPC comet file, computed locally like the asteroids.

## Plan
- [x] Parse CometEls.txt (q, e, T, angles, total magnitude)
- [x] Elliptic, parabolic and hyperbolic two-body + the same n-body refinement
- [x] Check against JPL Horizons (geocentric, 2025-06-01 and 2026-02-27)

## Findings
973 comets (MPC CometEls.txt, 2026-11-14). Local vs JPL Horizons, geocentric astrometric, 2025-06-01 / 2026-02-27:
29P 0.3"/0.4", 2P/Encke 0.1"/0.1", C/2025 A1 0.0"/0.0", C/2025 A3 0.2"/0.2", C/2023 A3 (e = 1.0002) 0.2"/1.9",
C/2024 G3 (q = 0.09 AU) 1.9"/1.5", 12P 1.4"/4.1". All under a pixel (6.15"); the rest is non-gravitational
forces, which Horizons models and we do not. Same pass also fixed T51: objects whose orbit epoch differs from
the catalogue's main epoch (~1,700 asteroids) were integrated from the wrong time.

## Questions / needs from others

## Handoff
`python -m detect.mpcorb fetch && python -m detect.mpcorb build` now also fetches/builds `data/mpcorb/comets.npz`.
Comets come out as `known_objects` with `source: "mpcorb"` like the asteroids; the magnitude limit is 1 mag
looser for comets (total coma magnitude).

## Notes from others
