# T69: C: Shift-and-stack in the viewer: stack the frames along an object's motion (or a guessed one), faint movers sharpen, stars smear

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T69-shift-stack`
- **Depends on / feeds:** T23, T10

## Goal
The viewer shows the shift-and-stack image (exists as `python -m pipeline.stack`, T23) for a chosen object or a guessed motion.

## Plan
- [x] API route or client-side stack on the loaded frames (like trail.js)
- [x] Pick object (or rate + direction for a guessed motion, T10 Planet X mode)
- [x] Toggle like the trail / difference views; browser test

## Findings
- Client-side on the loaded frames (no API): `stackPixels(frames, w, h, shifts)` in `web/stack.js` samples each
  frame at (x + dx, y + dy), bilinear; `shiftsAlong` (an object's per-frame positions, relative to its first
  one) and `shiftsForMotion` (rate ″/h + direction, relative to the epoch's first frame). Stack select options
  "along the selected object" (click an object on the image) and "along a guessed motion" (rate + direction).
- Frames of a built field are days to weeks apart within an epoch (Barnard: 46 days in epoch 1), so a guessed
  motion only stays on the image for slow movers (< ~0.5″/h, distant bodies); default 0.25″/h (~1 px/day). Fast
  asteroids would need the exposures of one visit (minutes apart), which builds don't keep (T09).
- Real data (Barnard field, live): "along Barnard's star", 36 frames, deep and sharp; a dark ring around the
  bright star comes from the per-frame background removal next to a very bright source (display only).
From idea I14 in TEAM.md (moved to the Board by Mati, 2026-11-14). Partly done: `pipeline.stack` (T23).

## Questions / needs from others

## Handoff
- Jonathan (T10 Planet X mode): "along a guessed motion" is the viewer side of shift-and-stack; the rate box
  takes ″/h and the direction east of north. T55: port with the Stack select.

## Notes from others
