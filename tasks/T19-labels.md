# T19: Labels on the images

- **Owner:** Joerg  ·  **Status:** done (pipeline side; viewer side is T13)
- **Branch:** `joerg/T19-labels` (merged)
- **Depends on / feeds:** T04 calls `add_labels` when it writes `target.json`; T13 draws them;
  T07 (known small bodies, Jonathan) stays separate in `known_objects`

## Goal
Find out which labels we can put on SPHEREx frames, where they come from and how fast, put them
into `target.json`, and show that they land on the right pixels.

## Plan
- [x] Check catalogue sources and timing
- [x] Proper motion: move catalogue positions to each frame's time
- [x] Try it on real frames (Barnard's Star, official test target)
- [x] `labels` field in `target.json` (CONTRACTS v0.4 + Decisions line)
- [x] Pipeline code: `pipeline/labels.py`
- [ ] T04 calls `add_labels(target)` before writing `target.json` (Joerg, with T04)

## Findings
Measured 2026-11-14 on a 0.164° (96 px) field around Barnard's Star, 15 detector-1 frames from
Aug 2025 to Aug 2026.

| Source | Gives | Time | Notes |
|---|---|---|---|
| SIMBAD TAP | names, object types, proper motion (J2000) | 0.4 s | `simbad.cds.unistra.fr` returned 404 ("Page unavailable") all day; the official mirror `simbad.cfa.harvard.edu` worked. Code tries CDS, Harvard, IDIA in order |
| Gaia DR3, ESA TAP | positions (J2016.0), proper motion, G mag | 1–2 s | 161 stars to G<16 here. The same table at IRSA (`gaia_dr3_source`) took 28 s, so we use ESA |
| CatWISE2020, IRSA TAP | infrared positions + motions | 33 s | 3,146 rows in the field: too many to label, too slow for live builds. Useful later for brown-dwarf candidates (T10), not for labels |

- **Accuracy:** for 46 bright stationary Gaia stars, label vs measured centroid = 0.4″ median
  (0.07 px), p90 3.2″ (blended or faint stars). Alignment and labels are both good.
- **Proper motion matters:** Barnard's Star's J2000 position is 4.5′ from where it is now. With the
  motion applied, its label sits on the star in every frame and moves 10.4″ (1.7 px) north over the
  year of data.
- **Barnard's Star saturates** in detector 1: about 45 masked pixels at the core in every frame. The
  label sits in the middle of the hole and the halo is centred on it. A halo-centroid measurement
  confirms northward motion but overshoots (18″ vs 10.4″ predicted), so measuring its motion
  needs a better method than a centroid (PSF fit on the wings) or a longer-wavelength detector.
- **Names:** 39 SIMBAD objects in the field, 2 with human-readable names (Barnard's star, V3214
  Oph); the rest are catalogue numbers (ZTF J…, Gaia …). Exoplanets (otype `Pl`) are skipped.
- A whole `add_labels` call takes about 2.3 s, so it fits into a live build.

## Questions / needs from others
- [to Mati, T13/T20] `target.json` can now carry `labels` (CONTRACTS v0.4, optional). Suggested
  drawing: named SIMBAD labels as ring + name by default, Gaia stars as small rings on a toggle,
  hide a Gaia ring within 2 px of a named label, and a track line for objects with
  `pm_mas_yr > 1000`. A working reference is the "Labels" section on Joerg's exploration page.

## Handoff
- `python -m pipeline.labels data/targets/<id>` adds labels to an existing `target.json` in place.
- In code: `from pipeline.labels import add_labels; target = add_labels(target)`. It only needs
  `center`, `image` and `frames[].mjd/id`. Synthetic targets get `labels: []`.
- A SIMBAD or Gaia outage doesn't fail the build: that source just contributes no labels, and its
  provenance entry is missing.
- Not done: labels for known small bodies (that's T07, `known_objects`), and brown-dwarf candidates
  from CatWISE (idea for T10).

## Notes from others
