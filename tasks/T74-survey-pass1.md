# T74: A/B: Discovery survey pass 1 next to the bucket: per manifest exposure read IMAGE + FLAGS, extract sources (T06), keep detection lists per tile, drop pixels; runs on the us-east4 VM

- **Owner:** Mati (from Joerg, 2026-11-14 evening; not started there)  ·  **Status:** doing
- **Branch:** `mati/T73-survey-pilot` (T73–T75 together)
- **Depends on / feeds:** T06, T73, T47

## Goal
Detection lists (position, flux, error, wavelength at the source, flags, time) for every manifest exposure, produced next to the AWS bucket; only the lists leave AWS.

## Plan
- [ ] Per-image entry point of the T06 source extraction (no target folder needed)
- [ ] Worker on the us-east4 VM (T47): stream IMAGE + FLAGS from S3, extract, write lists per tile
- [ ] Parallel workers, retries, resumable (skip done images); measured throughput (images/h, MB/s)
- [ ] Run the pilot manifest; copy the lists to the HPC / repo `data/`

Design of the whole survey (passes, data volumes, candidate classes, open questions): [T73](T73-survey-plan.md).

## Findings

## Questions / needs from others

## Handoff

## Notes from others

- 2026-11-14 [Joerg + Claude] Measured scope (was T77, a duplicate of this + T75):
  - 1,628,230 images (2025-04-24 to 2026-10-05), 65.6 MB per file; we need IMAGE + FLAGS, ~18 MB.
  - Cadence per spot: ~150-190 exposure times over 5 epochs, in bursts of ~4 exposures over ~6 min (each
    exposure: 2 detectors at once), bursts hours to days apart. Main-belt asteroids move 0.6 px per burst,
    ~37 px between bursts 6 h apart: link across bursts, not inside them. Planet X at ~50 AU: ~1'/day.
  - S3 from a home/EU host: 3.8 MB/s on one connection, 37.5 MB/s with 32 in parallel.
  - Scope: 1% pilot ~16k images, ~290 GB read, ~2-3 h; full sky ~54 TB read, ~30 CPU-days (~1 day on
    ~64 cores next to S3, or less on the HPC if its network allows), detections ~8 billion rows (few 100 GB).
  - Main risk: false positives (cosmic rays, satellites, ghosts, persistence); LVF wavelength varies across
    each detector, so brightness differs between images of the same star.
  Per band: detect per detector (WISE 0855 is invisible at 0.75-2.4 um, bright at 4-5 um; comet CO2 at 4.26 um), link movers across bands, colour as a classifier.
