# T135: Unusual spectra for uncatalogued sources too (SPHEREx-only sources), started only on a click

- **Owner:** Mati  ·  **Status:** review
- **Branch:** `mati/T135-uncatalogued-spectra`
- **Depends on / feeds:** T85/T86 (Joerg), T130 (Codex), T128 (catalogue check)

## Goal
Unusual spectra measured only the field's catalogue labels, so it could never flag anything uncatalogued (Mati,
2026-11-15). Now it also finds sources in SPHEREx's own images and measures them with the rest; the flagged
SPHEREx-only ones are looked up in SIMBAD / Gaia / CatWISE (T128, motion-corrected) and uncatalogued ones are
listed first. Also (Decision, option b): the measurement starts only when "Unusual spectra" is ticked.

## Plan (agreed with Mati 2026-11-15)
- [x] `pipeline/srcfind.py`: one pass over the field's exposures (the cutouts the measurement reads anyway):
      running means per detector group (D1–3, D4, D5, D6) and epoch, median over epochs (asteroids / transients
      out), background removed, peaks >= 5 sigma; drop catalogued (8″), near bright stars, edges; max 150;
      cached per field
- [x] hooks in Joerg's code (minimal): `measure_field` adds them; the cache check reads stored ones only;
      `peer_group` judges them with stars; flagged ones catalogue-checked + tagged after the ranking
- [x] viewer: tag on SPHEREx-only items, uncatalogued first; start only on the tick (outliers.js)
- [x] tests (light, synthetic); the real run skipped: Mati's server was at 3 GB measuring, 1.8 GB free

## Findings
- WISE 0855 is a catalogue label (SIMBAD BD*) and the existing measurement already flags it on the 32′ field
  ("+322 % at 4.24–5.05 µm, 11σ"); its 4.4–5.0 µm flux 546 ± 45 µJy matches WISE (W2 ≈ 13.9 → ~470 µJy).
  An uncatalogued one like it would never have been measured: that is what T135 adds.

## Handoff
- Hooks in Joerg's files: `fieldspectra.VERSION` 3 + one line in `measure_field` (finds them, inside the job);
  `server/fieldspectra.py` `_cached` reads stored ones only (a plain GET never reads an image) and `_tag_spherex`
  after the ranking; `peer_group` judges `source: "spherex"` with the stars; `outliers.js`: `load(st.mapOn)`.
- VERSION 3: every field's unusual spectra are measured again on the next click (stored results are older).
- Stored per field: `data/field_spectra/<id>.sources.json`; SPHEREx-only sources are named `SPHEREx J…`, ids x001…
- First real run = Mati ticking "Unusual spectra" on a field; check `<id>.sources.json` ("peaks", "sources").

## Notes from others
