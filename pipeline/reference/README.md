# pipeline/reference: working exploration code

> **Superseded 2026-11-14:** `pipeline.build` (T02-T04, Jonathan) now builds real fields, with labels.
> Use it, not `bake_target.py`. These scripts stay as a record of how the data was first explored.

Not part of the pipeline and not imported by anything. These are the scripts Joerg's session used
on 2026-11-14 to look at real SPHEREx data (COSMOS, Barnard's Star). They work, and they show how
each step of T02-T04 can be done. Copy what helps; nothing here is a contract.

| File | Does | Relevant for |
|---|---|---|
| `fetch_cutouts.py` | IBE cutouts for one detector from a `pipeline.query` JSON, 8 threads, skip existing, 3 retries | T02 |
| `bake_target.py` | stopgap: wrote a real target folder into the Live API cache before `pipeline.build` existed. Superseded | — |
| `align_render.py` | reproject onto the common TAN grid, flag mask, zodi subtraction, wavelength + bandwidth at the centre, PNG with alpha, median residuals, matched pairs | T03, T04, T17 |

What we learned (details also in the TEAM.md Log, 2026-11-14):

- **Cutouts:** append `?center=<ra>,<dec>&size=<deg>deg` to the `fits_url` from `pipeline.query`.
  Each is ~4 MB (mostly the EPSF extension) and takes 10-25 s; 8 in parallel is fine.
- **Extensions:** `IMAGE` (MJy/sr), `FLAGS`, `VARIANCE`, `ZODI` (subtract it), `EPSF`, `WCS-WAVE`.
- **Flags:** names are in the FLAGS header (`MSKNnnnn`). Masked here: bits 0,1,2,6,9,10,11,14,17,
  25,26,27,28 (hardware and artifacts). Not masked: 21 `SOURCE` (pixel on a catalogued source,
  ~35%) and 19 `OUTLIER` (may contain real movers).
- **Wavelength at a pixel:** `WCS-WAVE` is an n x n grid (9 or 11) of (wavelength, bandwidth) on
  1-based detector pixels; cutout pixel -> detector pixel via `CRPIX1A`/`CRPIX2A` (see the code;
  an off-by-one there would change the wavelength by ~0.0003 um, harmless).
- **Alignment:** `reproject_interp` onto TAN, north up, 6.15"/px. Checked on Barnard's Star field:
  bright stationary Gaia stars land within 0.4" (0.07 px) of their predicted positions.
- **Saturation:** Barnard's Star saturates in detector 1, ~45 masked pixels at its core.
- **Pairs (T17):** with 0.5 x bandwidth tolerance COSMOS D2 gives 21 pairs; pair differences cancel
  stars much better than subtracting the median.
- **Labels:** `pipeline.labels.add_labels(target)` (T19) can be called once `target.json` exists.

Extra packages used: `reproject`, `scipy`, `pillow` (not yet in `pipeline/requirements.txt`).
