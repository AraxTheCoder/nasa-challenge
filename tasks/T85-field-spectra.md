# T85: Spectra for a whole field

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T85-field-spectra`
- **Depends on / feeds:** T66/T83 (all-exposure spectra, worker pool), T19/T72 (catalogue labels); feeds T86, T87, T75

## Goal
A spectrum for every catalogue source in a field, not just the one clicked point. Read each exposure that
covers the field once and measure all sources in it, so the cost is the ~150–300 exposures, not the number
of stars. Cached per field.

## Plan
- [x] `pipeline/fieldspectra.py`: exposures covering the field centre, one field-sized cutout each (S3, worker
      pool as in T83), aperture photometry at every label position (moved along its own track by MJD)
- [x] Same photometry as T49/T66: `photometry.measure_cutout_many` (file read once, all positions; `measure_cutout`
      is now that with one position, same results) and `build.wavelengths_at` (vectorised `wavelength_at`)
- [x] Cache `data/field_spectra/<target id>.json`: sources, exposures, arrays [source][exposure]; recomputed when
      the labels or `VERSION` change. `seed_spectra` also fills the T66 per-position cache: a click on a source is instant
- [x] Live API with T86: `GET /api/targets/<id>/spectral-outliers[?start=1]` (CONTRACTS v0.15)
- [x] Tests: `pipeline/test_fieldspectra.py` (synthetic cutouts), `server/test_server.py::test_spectral_outliers_job`

## Findings
- RW Aur field: 172 sources × 237 exposures in 21 s the first time (8 s with cached cutouts); the whole field
  costs ~3× one clicked point. Barnard field 246 × 297 in 24 s, RA 180 Dec 0 212 × 316 in 29 s.
- Median ~185–250 clean measurements per source. Saturated stars (RW Aur: 8 clean of 237) can't be used.
- Labels from X-ray / radio catalogues are skipped (`LOOSE_OTYPES`): 1RXS J050754.4+302214 (ROSAT, 10–20″
  position errors) came out as the "strongest outlier" with residuals jumping ±40 % band to band: the
  aperture sat beside the star and the PSF's growth with wavelength faked structure.

## Questions / needs from others

## Handoff
`python -m pipeline.fieldspectra data/targets/<id>` (or the endpoint) → `data/field_spectra/<id>.json`;
`fieldspectra.source_spectrum(fs, i)` gives one source in the T66 shape. For the survey (T75) the same
`measure_field` works per tile with detections as sources.

## Notes from others
