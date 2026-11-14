# T09: Sanity check: do we recover known asteroids in real SPHEREx data at the predicted position?

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T09-known-check`
- **Depends on / feeds:** T04 (frames), T07/T51 (predicted positions), T49 (photometry); feeds T15 (a validated claim)

## Goal
For every known asteroid in our real fields: is there a source at the predicted position in the frame where
it should be, and not there in the other epochs? How far off is it, and down to which brightness does it work?
A reusable check (`python -m detect.known_check <target_dir>`) plus the numbers for the submission.

## Plan
- [ ] Per known-object position: flux in that frame at the predicted position (aperture on the SPHEREx cutout,
      `pipeline.photometry`) minus the same sky position in frames of other epochs (asteroid gone) → S/N
- [ ] Position: peak of (frame − median of other epochs) on the aligned grid near the prediction → offset
- [ ] Run on all cached fields with known objects; table: name, V, S/N, offset
- [ ] Tests on synthetic data; findings + handoff

## Findings

## Questions / needs from others

## Handoff

## Notes from others
