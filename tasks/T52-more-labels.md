# T52: More labels: variable stars, brown dwarfs, planets and moons

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T52-more-labels`
- **Depends on / feeds:** T19/T38 (labels), T37 (labels on request), idea I4

## Goal
Name more of what SPHEREx sees: VSX variables (two official targets, RW Aur and R Dra, are variables), CatWISE2020 brown dwarfs and fast movers (WISE 0855, Eps Ind B), and planets/moons, which are bright and move.

## Plan
- [x] VSX via VizieR (Harvard mirror first; CDS was down 2026-11-14), type + period + range as `note`;
      proper motions from SIMBAD by name (VSX has none)
- [x] CatWISE2020 via VizieR (IRSA TAP took > 15 s): clean red movers only, moved to frame time
- [x] Planets + bright moons: astropy for the coarse check, JPL Horizons seen from SPHEREx when near
- [x] Merge with SIMBAD/Gaia, importance ranking, viewer shows the new sources, `note`, `mag_band`
- [x] CONTRACTS v0.11 + schema + Decisions line

## Findings
All label sources run in parallel; a field takes 2-4 s in total (the slowest source), measured on the
five official fields + the ecliptic field RA 180 Dec 0 (2026-11-14):

- VSX (0.4 s + 0.5 s SIMBAD lookup). R Dra: "Mira variable (M), period 246.1 d, range 6.7 to 13.2 mag".
  RW Aur: CTTS, period 2.64 d. Barnard's Star = V2500 Oph and Eps Ind B = CI Ind become aliases with the
  VSX note, but only after taking proper motions from SIMBAD: VSX positions are J2000 without motion
  (Barnard's Star 4.5' off, Eps Ind B 2' off). `f_min = Y` marks `min` as an amplitude.
- CatWISE2020 (~2.5 s via VizieR; `-out=` column lists return no rows on the CfA mirror, `-out.all` works).
  Raw cuts (red OR moving) gave fakes: dozens of "movers" in Barnard's Star's glare (1-9"/yr), echoes of
  Eps Ind B, and CatWISE splits WISE 0855 into four sources. Kept now: W1-W2 >= 1 (or not in W1) AND
  proper motion >= 0.1"/yr at 5 sigma, detected in >= half the W2 visits, chi2pm <= 10, no uppercase
  artefact flags, outside the glare of G < 10 / W2 < 9 sources (compared at catalogue epoch), not within
  3' of a known fast star moving at a similar rate, one per 30". Result: no fakes in the five official
  fields; WISE 0855's own entry merges with SIMBAD; RW Aur (Taurus) keeps 3 faint red movers, labelled
  "brown dwarf candidate" (young stars are red too).
- Planets/moons (synthetic fields on 2025-09-01): Neptune + Triton, Jupiter + Io/Europa/Ganymede/Callisto,
  positions from Horizons seen from SPHEREx (0.8-1.5 s, only when a planet is within 1.5 deg). The Moon,
  centred geocentrically, is correctly outside the field seen from SPHEREx (~1 deg parallax).

## Questions / needs from others

## Handoff

## Notes from others
