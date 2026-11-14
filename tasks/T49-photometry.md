# T49: Light curves and spectra on the fly (photometry at any position)

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T49-photometry` (merged)
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
- [x] `pipeline/photometry.py`: per frame, find the cached cutout FITS, IMAGE − ZODI, aperture sum
      (r = 3 px) minus annulus background, flagged pixels excluded, µJy + error from VARIANCE, the
      wavelength/bandwidth *at the star* (WCS-WAVE), a `masked` flag
- [x] `server/photometry.py` (APIRouter): `GET /api/targets/<id>/photometry?ra=&dec=` (or `x=&y=` on the
      target grid); one `include_router` line in `server/app.py`; CONTRACTS v0.10 + Decisions line
- [x] Viewer `web/photometry.js`: panel with the two charts, "Measure" mode (click on the image),
      default = field centre; honest notes (aperture photometry, no aperture correction)
- [x] Tests: synthetic FITS (known star flux) for the pipeline + server; browser test with a stubbed API answer

## Findings
- Real fields (cached cutouts on Mati's machine), field centre: **RW Aurigae** 21 of 36 frames measurable
  (short wavelengths; the core saturates at longer ones); ~150 mJy near 1 µm rising to ~1 Jy at 4–5 µm (its
  dusty disk). Epoch 1 → 3 at matched wavelengths: two matches, −45 % and +70 %, i.e. no clear signal from
  this alone (the UI says "mixed signs"). A field star next to it: −19 % median over 4 matches.
- **Barnard's Star and R Draconis are saturated in every frame** (masked); aperture photometry can't measure
  them, and the panel says so plainly. A PSF-wing fit would be the next step for bright stars.
- Calibration sanity check: 49 measurements of Gaia stars (G 11–14.5) at ~0.85 µm come out 2.2× the G-band
  prediction, i.e. ~1.1× after the usual G−RP colour of field stars: consistent within ~20 %.
- One call measures all frames in 1–3 s (cached in memory per position). Since T33 most cutouts come from S3
  without VARIANCE/ZODI (Jonathan's note): local annulus background + annulus scatter cover that (tested).
- Consecutive epochs rarely share a wavelength at the star, so changes compare any earlier→later epoch pair
  (≤ 3 transitions kept, the 3 colours that pass the all-pairs palette check on the dark surface; a 4th fails,
  hence one spectrum panel per epoch instead of 4 colours).

## Questions / needs from others
- [to Jonathan] T49 adds `server/photometry.py` and one `app.include_router(...)` line in `server/app.py`.

## Handoff
- API: `GET /api/targets/<id>/photometry[?ra=&dec= | ?x=&y=]` (CONTRACTS "Photometry"); CLI
  `python -m pipeline.photometry data/targets/<id> [--ra --dec]`.
- Viewer: panel under the timeline; "Measure a star" then click; "Field centre" resets. Hidden in offline mode
  and for synthetic fields (server answers `no_data`).
- Needs the cached cutouts on the machine that serves the API (they are written by the build).
- Next steps if wanted: aperture correction from the EPSF table (better spectral slope); PSF-wing photometry
  for saturated stars (Barnard, R Dra); a time-axis light curve once more epochs exist.

## Notes from others
(anyone may append here, dated and signed)
- 2026-11-14 [Jonathan + Claude → Mati] Fine to add `server/photometry.py` + the `include_router` line.
  Heads-up for reading cached cutouts: since T33 most come from the AWS bucket via `pipeline/s3.py` and
  contain only `IMAGE`, `FLAGS`, `WCS-WAVE` (header `S3SRC` in the primary HDU) - **no `VARIANCE`, no
  `ZODI`**. IRSA-cutout fallbacks still have all extensions. For errors use the local background scatter
  (or read VARIANCE rows the same way as IMAGE in `pipeline/s3.py` if you need it - ask me). For a
  background, subtract a local annulus median (ZODI is smooth at these scales).
