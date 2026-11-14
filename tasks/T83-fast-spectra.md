# T83: Faster spectra from all exposures

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T83-fast-spectra`
- **Depends on / feeds:** T66, T57 (cutout VM), T33 (S3 range reads)

## Goal
A click's all-exposure spectrum in a few seconds, not 20-65 s.

## Findings (2026-11-14, from Joerg's host in Europe)
- One 3' cutout = 7 dependent range requests (0.13-0.46 s each; a plain round trip to S3 is 0.42 s),
  ~0.6 MB: ~2.2 s per image, all latency. 220 images / 24 threads -> ~20 s.
- The threads were CPU-bound too (FITS headers, WCS, RICE decode hold the GIL): 32 s CPU in 24 s.
- The cutout VM answered 502 / took 9.7 s, and every image tried it first, then S3; moved (reprocessed)
  images then went to IRSA cutouts (seconds each). A spectrum through the server took 65 s.
- Now: S3 directly, 16 worker processes x 8 threads, bucket listing (`s3.find_in_bucket`) for moved
  images, thread fallback if the pool breaks. Fresh point: 9.9 s with a cold pool, 5.5-6.0 s warm
  (233-236 exposures). The rest is latency: next steps are fewer requests per image (header cache,
  parallel IMAGE/FLAGS reads in `s3.fetch_cutout`, Jonathan's code) or precomputing on the HPC (T75).

## Handoff
`pipeline/photometry.py`: SPECTRUM_PROCESSES, SPECTRUM_BATCH; `measure_all(..., processes=0)` = threads only.

## Notes from others
