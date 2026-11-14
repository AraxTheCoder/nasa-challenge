# T85: Spectra for a whole field

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T85-field-spectra`
- **Depends on / feeds:** T66/T83 (all-exposure spectra, worker pool), T19/T72 (catalogue labels); feeds T86, T87, T75

## Goal
A spectrum for every catalogue source in a field, not just the one clicked point. Read each exposure that
covers the field once and measure all sources in it, so the cost is the ~150–300 exposures, not the number
of stars. Cached per field.

## Plan
- [ ] `pipeline/fieldspectra.py`: exposures covering the field centre, one field-sized cutout each (S3, worker
      pool as in T83), aperture photometry at every label position (moved along its own track by MJD)
- [ ] Same photometry as T49/T66 (`photometry.measure_cutout`), loaded once per cutout for all positions
- [ ] Cache `data/field_spectra/<target id>.json`: sources, exposures, compact arrays per source
- [ ] Live API: job + progress, result endpoint (with T86)
- [ ] Tests on a synthetic cutout

## Findings

## Questions / needs from others

## Handoff

## Notes from others
