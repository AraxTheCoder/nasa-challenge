# T52: More labels: variable stars, brown dwarfs, planets and moons

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T52-more-labels`
- **Depends on / feeds:** T19/T38 (labels), T37 (labels on request), idea I4

## Goal
Name more of what SPHEREx sees: VSX variables (two official targets, RW Aur and R Dra, are variables), CatWISE2020 brown dwarfs and fast movers (WISE 0855, Eps Ind B), and planets/moons, which are bright and move.

## Plan
- [ ] VSX via VizieR (Harvard mirror first; CDS was down 2026-11-14), type + period + range as `note`
- [ ] CatWISE2020 via IRSA TAP: red (W1-W2) or significant proper motion, moved to frame time
- [ ] Planets + bright moons: astropy for the coarse check, JPL Horizons seen from SPHEREx when near
- [ ] Merge with SIMBAD/Gaia, importance ranking, viewer shows the new sources and `note`
- [ ] CONTRACTS v0.11 + schema + Decisions line

## Findings

## Questions / needs from others

## Handoff

## Notes from others
