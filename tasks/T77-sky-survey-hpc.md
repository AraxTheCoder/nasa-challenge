# T77: Sky survey on the HPC (later)

- **Owner:** Joerg  ·  **Status:** done (merged into T74/T75)
- **Branch:** -
- **Depends on / feeds:** T06 (mover detection, Jonathan), T09 (are known asteroids visible?), T31 (image index), T51 (known objects), T36 (map)

## Goal
Run detection over SPHEREx images once (incrementally as new data arrives) and give every sky tile a score:
unknown mover candidates, fastest proper motion, strongest variability, known-object matches. Sorted list of
"where something changes" + a heat-map layer on the explore map. First a 1% pilot (~400 deg2), then the sky.

## Plan
- [ ] Validate per-image detection on a few fields first (official fields + ecliptic RA 180 Dec 0, which has
      7 known asteroids): recover known asteroids and Barnard's Star's motion before spending HPC hours
- [ ] Map step (array job, one task per image): read IMAGE (16.6 MB, uncompressed float32) + FLAGS
      (RICE tiles, `pipeline.s3._flags_rows`) by HTTP range from s3://nasa-irsa-spherex, background,
      sources, WCS -> detections (ra, dec, flux, snr, mjd, detector, wavelength) per HEALPix tile; no pixels kept
- [ ] Reduce step per tile: static sky (same spot in many epochs), proper motions across epochs,
      variability, leftovers linked into straight tracks across bursts within an epoch, known-object match
- [ ] Score + sort per tile; API + map layer
- [ ] Per detector (band), see below: detect per band, link across bands, colour as a classifier

## Findings (2026-11-14, measured on Joerg's host)
- 1,628,230 images (2025-04-24 to 2026-10-05), 65.6 MB per file; we need IMAGE + FLAGS, ~18 MB.
- Cadence per spot: ~150-190 exposure times over 5 epochs, in bursts of ~4 exposures over ~6 min (each
  exposure: 2 detectors at once), bursts hours to days apart. Main-belt asteroids move 0.6 px per burst,
  ~37 px between bursts 6 h apart: link across bursts, not inside them. Planet X at ~50 AU: ~1'/day.
- S3 from a home/EU host: 3.8 MB/s on one connection, 37.5 MB/s with 32 in parallel.
- Scope: 1% pilot ~16k images, ~290 GB read, ~2-3 h; full sky ~54 TB read, ~30 CPU-days (~1 day on
  ~64 cores next to S3, or less on the HPC if its network allows), detections ~8 billion rows (few 100 GB).
- Main risk: false positives (cosmic rays, satellites, ghosts, persistence); LVF wavelength varies across
  each detector, so brightness differs between images of the same star.

## Questions / needs from others
- [to Jonathan] T06 and this share the detection code: who builds what?
- HPC: scheduler, cores, internet bandwidth from compute nodes to AWS, scratch size, Python env.

## Handoff

## Notes from others
