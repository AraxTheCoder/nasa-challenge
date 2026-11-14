# T91: Measured motion of the official targets

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T91-measured-motion`
- **Depends on / feeds:** T85 (field cutouts of every exposure), T19 (catalogue positions + proper motions), demo / pitch

## Goal
Not just draw a star's catalogue path: measure it from SPHEREx alone. Fit the star's position in every epoch
and turn it into a proper motion with an error bar, next to Gaia's value. "SPHEREx says 10.3″/yr; Gaia 10.4."

## Plan
- [x] `pipeline/astrometry.py`: Gaussian fit to the star in every exposure (flagged pixels left out, so a
      saturated core doesn't matter), the catalogue track only to find it; each exposure's pointing corrected
      with up to 40 isolated Gaia stars; robust mean per epoch; motion per axis (errors grown by each axis' own
      χ²); parallax tried with 3+ epochs and reported only if consistent (χ²/dof ≤ 3) and > 3σ
- [x] "Not the star" check: a source ≥ 3″ from the track in every epoch is a neighbour → `not_found`
- [x] Fits spread over the spectra worker processes: ~15 s per star (2 min in one process); cached in data/motion/
- [x] `GET /api/targets/<id>/motion?name=[&start=0]` (CONTRACTS v0.24); box in the spectrum panel
      (`web/motion.js`) when the clicked point is a catalogued star moving ≥ 0.3″/yr; a button measures it
- [x] Tests: `pipeline/test_astrometry.py` (injected motion recovered despite pointing errors; faint star next to
      a neighbour = not_found), `server/test_server.py::test_motion_endpoint`

## Findings
| Target | SPHEREx | Catalogue |
|---|---|---|
| Barnard's Star | 10.46 ± 0.19″/yr, PA 356° (299 exposures, 3 epochs, 0.98 yr) | 10.39″/yr, 356° |
| eps Ind B | 4.60 ± 0.26″/yr, PA 124°; **parallax 0.286 ± 0.022″ = 3.49 pc** (χ²/dof 1.9; 351 exposures, 4 epochs) | 4.68″/yr, 122°; Gaia ϖ(eps Ind A) 0.2748″ = 3.64 pc |
| WISE 0855 | not found: too faint in single exposures; the fit locked onto a field star 7.7″ away | 8.15″/yr |

- Barnard's Star's parallax fit gives 1.02 ± 0.12″ (true 0.547″) with χ²/dof 13: epoch 2 sits 1.9″ east of the
  line, a systematic shift (saturated core, PSF across detectors), so no distance is claimed there.
- WISE 0855 needs deep stacks (the T89 note to Jonathan) to be measurable at all.

## Notes from others
