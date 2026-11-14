# T74: A/B: Discovery survey pass 1 next to the bucket: per manifest exposure read IMAGE + FLAGS, extract sources (T06), keep detection lists per tile, drop pixels; runs on the us-east4 VM

- **Owner:** Joerg (assigned by Mati, 2026-11-14)  ·  **Status:** open
- **Branch:** –
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
