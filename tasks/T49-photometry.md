# T49: Light curves and spectra on the fly (photometry at any position)

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T49-photometry`
- **Depends on / feeds:** T02–T04 (cached cutouts in `data/raw/`), T17 (pairs), T12 (viewer); gap-scan ideas #2 + #3
- **From:** official test targets RW Aurigae and R Draconis are *variable stars*; Potential Considerations:
  "Extra kudos if your tool can generate spectra on the fly".

## Goal
Click any star (default: the field's own object) and get, from the calibrated SPHEREx images:
- a **spectrum**: brightness vs. wavelength at that position, one colour per epoch (each epoch sweeps
  0.75–5 µm, so every epoch is its own low-resolution spectrum);
- a **light curve**: brightness vs. time, where lines join frames at the *same* wavelength in different
  epochs (T17 pairs): flat lines = constant star, sloped lines = it changed.

## Plan
- [ ] `pipeline/photometry.py`: per frame, find the cached cutout FITS, IMAGE − ZODI, aperture sum
      (r = 3 px) minus annulus background, flagged pixels excluded, µJy + error from VARIANCE, the
      wavelength/bandwidth *at the star* (WCS-WAVE), a `masked` flag
- [ ] `server/photometry.py` (APIRouter): `GET /api/targets/<id>/photometry?ra=&dec=` (or `x=&y=` on the
      target grid); one `include_router` line in `server/app.py`; CONTRACTS v0.10 + Decisions line
- [ ] Viewer `web/photometry.js`: panel with the two charts, "Measure" mode (click on the image),
      default = field centre; honest notes (aperture photometry, no aperture correction)
- [ ] Tests: synthetic FITS (known star flux) for the pipeline + server; browser test with a stubbed API answer

## Findings

## Questions / needs from others
- [to Jonathan] T49 adds `server/photometry.py` and one `app.include_router(...)` line in `server/app.py`.

## Handoff

## Notes from others
(anyone may append here, dated and signed)
