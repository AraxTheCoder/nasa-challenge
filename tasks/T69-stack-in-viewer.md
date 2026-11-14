# T69: C: Shift-and-stack in the viewer: stack the frames along an object's motion (or a guessed one), faint movers sharpen, stars smear

- **Owner:** –  ·  **Status:** open
- **Branch:** –
- **Depends on / feeds:** T23, T10

## Goal
The viewer shows the shift-and-stack image (exists as `python -m pipeline.stack`, T23) for a chosen object or a guessed motion.

## Plan
- [ ] API route or client-side stack on the loaded frames (like trail.js)
- [ ] Pick object (or rate + direction for a guessed motion, T10 Planet X mode)
- [ ] Toggle like the trail / difference views; browser test

## Findings
From idea I14 in TEAM.md (moved to the Board by Mati, 2026-11-14). Partly done: `pipeline.stack` (T23).

## Questions / needs from others

## Handoff

## Notes from others
