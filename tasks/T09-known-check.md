# T09: Sanity check: do we recover known asteroids in real SPHEREx data at the predicted position?

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T09-known-check`
- **Depends on / feeds:** T04 (frames), T07/T51 (predicted positions), T49 (photometry); feeds T15 (a validated claim)

## Goal
For every known asteroid in our real fields: is there a source at the predicted position in the frame where
it should be, and not there in the other epochs? How far off is it, and down to which brightness does it work?
A reusable check (`python -m detect.known_check <target_dir>`) plus the numbers for the submission.

## Plan
- [x] Per known-object position: flux in that frame at the predicted position (aperture on the SPHEREx cutout,
      `pipeline.photometry`) minus the same sky position in frames of other epochs (asteroid gone) → S/N
- [x] Position: peak of (frame − median of other epochs) on the aligned grid near the prediction → offset
- [x] Run on all cached fields with known objects; table: name, V, S/N, offset
- [x] Tests on synthetic data; findings + handoff

## Findings
Run 2026-11-14 with `python -m detect.known_check` (code in this branch; JPL Horizons observer SPHEREx `-163182`,
local SPHEREx index T31, IRSA cutouts; all requests in the JSON's provenance).

**Bright asteroid: recovered.** (29) Amphitrite, V = 10.7 (JPL, seen from SPHEREx), 2026-07-29 (`--object 29
--date 2026-07-29`): 20 exposures cover it within ±0.5 d (10 visits × 2 detectors imaging the same sky at once).
- 19 of 19 measurable exposures recovered (S/N 56–215; 1 flagged at that spot; 1 reference image 404 at IRSA,
  skipped). Controls (same exposures, 15 px away): 0 of 40 "recovered".
- Position: median offset 0.11 px (0.7″); long-wavelength detectors D5/D6 ≤ 0.11 px, short D2/D3 0.4–1.5 px
  (all within the 1.5 px limit; the larger short-λ offsets are worth a look: PSF or per-detector WCS).
- Flux: 26–126 mJy at 1.1–1.9 µm (some visit-to-visit scatter: rotation, or partial flags), and **rising from
  83 mJy at 3.8 µm to 127 mJy at 4.6 µm**: reflected sunlight should fall there in F_ν, so this looks like the
  asteroid's own thermal emission. A hint, not checked further.

**Faint asteroids in our cached fields: correctly not recovered.** 11 asteroids (RW Aur field, two Barnard-area
fields), V 18.1–20.1: 0 of 17 measurable positions above S/N 5, 0 of 69 controls. Single-exposure 5σ limit
here ~2.5–8 mJy (≈ AB 14–15.5, depends on stars and nebulosity under the position), V 18–20 asteroids are
0.03–0.2 mJy. So: **single SPHEREx exposures see asteroids down to roughly V ≈ 14–15**; everything that bright
has been known for decades, so new-asteroid claims from single exposures would be suspicious by default.

Index gotcha: the local index (T31) still holds a few outdated image paths (IRSA 404); the check skips them.

## Questions / needs from others

## Handoff
- Fields: `python -m detect.known_check data/targets/<id> [...] [--json out.json]` (needs `known_objects`, i.e.
  `/objects` has run; cutouts from the build cache).
- Bright asteroid: `python -m detect.known_check --object 29 --date 2026-07-29` (needs `data/mirror/index.npz`;
  ~6 min first time, IRSA cutouts are slow; cached afterwards under `data/raw/cutouts`). Other bright
  candidates with coverage: (12) Victoria V≈12 on 2026-02-02, (29) on 2026-03-01.
- Numbers for T15 (submission): "known asteroids recovered at the predicted position in 19/19 exposures,
  median error 0.7″; no false recoveries in 109 control positions; single-exposure limit ≈ V 14–15".
- Tests: `detect/test_known_check.py` (offline, demo-epochs fixture).

## Notes from others
