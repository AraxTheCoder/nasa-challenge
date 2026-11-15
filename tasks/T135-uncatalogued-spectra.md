# T135: Unusual spectra for uncatalogued sources too (SPHEREx-only sources), started only on a click

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T135-uncatalogued-spectra`
- **Depends on / feeds:** T85/T86 (Joerg), T130 (Codex), T128 (catalogue check)

## Goal
Unusual spectra measured only the field's catalogue labels, so it could never flag anything uncatalogued (Mati,
2026-11-15). Now it also finds sources in SPHEREx's own images and measures them with the rest; the flagged
SPHEREx-only ones are looked up in SIMBAD / Gaia / CatWISE (T128, motion-corrected) and uncatalogued ones are
listed first. Also (Decision, option b): the measurement starts only when "Unusual spectra" is ticked.

## Plan (agreed with Mati 2026-11-15)
- [ ] `pipeline/srcfind.py`: one pass over the field's exposures (the cutouts the measurement reads anyway):
      running means per detector group (D1–3, D4, D5, D6) and epoch, median over epochs (asteroids / transients
      out), background removed, peaks >= 5 sigma; drop catalogued (8″), near bright stars, edges; max 150;
      cached per field
- [ ] hooks in Joerg's code (minimal): `measure_field` adds them; the cache check reads stored ones only;
      `peer_group` judges them with stars; flagged ones catalogue-checked + tagged after the ranking
- [ ] viewer: tag on SPHEREx-only items, uncatalogued first; start only on the tick (outliers.js)
- [ ] tests (light); one real run on the WISE 0855 field (15′) after checking free memory

## Findings

## Handoff

## Notes from others
