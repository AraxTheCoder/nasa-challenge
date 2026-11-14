# T66: A: Fuller spectra from all exposures: photometry on every exposure covering a position (not only the 36 frames kept for blinking), cached per position

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T66-fuller-spectra`
- **Depends on / feeds:** T31, T33, T49

## Goal
Spectra and light curves use all SPHEREx exposures of a position (~358 for Barnard's Star instead of 36), so they have ~10× more points.

## Plan
- [x] List all exposures covering the position (T31 index)
- [x] Read only the rows around the star (tiny 3' cutouts: VM / S3 rows / IRSA; moved images re-resolved)
- [x] Measure each (`pipeline.photometry.measure_cutout`), cache per position (`data/spectra/`)
- [x] API: `?all=1` on `/photometry`, a background job (202 + done/total, then 200, same answer shape)
- [x] Viewer: quick answer from the field frames first, then "adding all exposures… k/N" and a redraw

## Findings
WISE 0855 (2026-11-14, from Joerg's host): 223 exposures, 220 measured in 16.6 s (24 parallel reads),
~70 points per epoch over 0.75-5 um instead of ~4. The T63 hints flag 4-6x more light at 4.15-4.45 um than a
star-like baseline: the brown-dwarf signature (WISE W2 ~ 14 ~ 430 uJy; we measure ~525 uJy at 4.4-5 um).
At 0.8-1 um a neighbour inside the 18" aperture dominates: blending is now said in the note.
Cutouts from S3 have no ZODI plane; the background ring removes the zodiacal light anyway.
From idea I11 in TEAM.md (moved to the Board by Mati, 2026-11-14). ~2 h. Suggested owner: Jonathan (index + S3).

## Questions / needs from others

## Handoff
`python -m pipeline.photometry --all --ra .. --dec ..` on the command line. In `/app/` (T55): port `loadAll`
from web/photometry.js.

## Notes from others
