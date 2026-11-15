# T128: Candidates from a chemistry picture (a list of spots, rings on the map)

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T128-chemistry-candidates`
- **Depends on / feeds:** T93, T96, T107, T122 (select region), T127 (object presets)

## Goal
Select a region, pick a chemistry preset (or tick features): below the picture's note a numbered list of the spots
where the features show, ranked, with the catalogue name if one is there; the same numbers as rings on the map; a
click centres the map on the spot and opens its spectrum. Visualization only (Decision 2026-11-14): spots to look
at, worded as such, nothing classified; the spectrum is how the user judges.

## Plan
- [ ] `pipeline.chemistry.candidates(target_dir, keys)`: per map the strength in noise levels in its direction
      (from the shown, smoothed map), compact local peaks, sharpness pairs at bright stars and the rims of empty
      (saturated) holes left out; rank by features showing (>= 2 sigma), then strength; nearest catalogue label
- [ ] `GET /api/targets/<id>/chemistry/candidates?maps=<k1>-<k2>...` (CONTRACTS)
- [ ] viewer: list under the chemistry note, numbered rings on the map, click = centre + spectrum
- [ ] try on the T127 fields (Eps Ind B, 3C 273, NGC 6240, rho Oph)

## Findings

## Questions / needs from others

## Handoff

## Notes from others
