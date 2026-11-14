# T75: B: Discovery survey pass 2 (HPC): flag tiles from the pass-1 lists (moved / appeared / changed at matched λ / odd spectrum), then all exposures there at full resolution, forced photometry, spectra, candidates with class + score + reason

- **Owner:** Joerg (assigned by Mati, 2026-11-14)  ·  **Status:** open
- **Branch:** –
- **Depends on / feeds:** T74, T08, T09, T63

## Goal
A ranked candidate list per pilot tile, each with class (brown dwarf / variable / spectral outlier / mover), score and a plain-words reason, and a measured completeness.

## Plan
- [ ] Match pass-1 detections to Gaia (moved to frame time) and CatWISE: static + known out
- [ ] Leftovers: link within an epoch (asteroid tracklets vs. MPC) and across epochs (proper motion)
- [ ] Flagged tiles: all exposures, forced photometry, per-epoch spectra (T63 baseline), variability at matched λ (T12 pairs), T09 recovery check
- [ ] Injection test: fake movers + fake brown dwarfs planted in real images, recovery rate vs. brightness
- [ ] Validation: WISE 0855, Eps Ind B and known T/Y dwarfs in the pilot must come out as candidates

Design of the whole survey (passes, data volumes, candidate classes, open questions): [T73](T73-survey-plan.md).

## Findings

## Questions / needs from others

## Handoff

## Notes from others
