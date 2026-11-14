# T66: A: Fuller spectra from all exposures: photometry on every exposure covering a position (not only the 36 frames kept for blinking), cached per position

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T66-fuller-spectra`
- **Depends on / feeds:** T31, T33, T49

## Goal
Spectra and light curves use all SPHEREx exposures of a position (~358 for Barnard's Star instead of 36), so they have ~10× more points.

## Plan
- [ ] List all exposures covering the position (T31 index)
- [ ] Read only the rows around the star (T33 S3 range reads)
- [ ] Measure each (`pipeline.photometry.measure_cutout`), cache per position
- [ ] API: same `/photometry` answer, more frames (or a `?all=1`); viewer unchanged

## Findings
From idea I11 in TEAM.md (moved to the Board by Mati, 2026-11-14). ~2 h. Suggested owner: Jonathan (index + S3).

## Questions / needs from others

## Handoff

## Notes from others
