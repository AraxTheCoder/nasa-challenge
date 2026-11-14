# T54: Known objects + labels start while the images download

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T52-more-labels`
- **Depends on / feeds:** T51, T37, pipeline/build.py

## Goal
Known objects and labels need only frame times and the field geometry, not pixels: start them when the frames are chosen, so a new field is complete when its frames are.

## Plan
- [ ] Hook in pipeline.build once frames are chosen
- [ ] Server starts objects + labels from it, merges when the build lands
- [ ] Frames dropped by a failed download are dropped from tracks too

## Findings

## Questions / needs from others

## Handoff

## Notes from others
