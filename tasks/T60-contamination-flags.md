# T60: A/C: Contamination flags in the viewer: per-frame FLAGS bits exported with the frame, overlay toggle, flag names at the inspected pixel

- **Owner:** –  ·  **Status:** open
- **Branch:** –
- **Depends on / feeds:** T04

## Goal
The viewer can show SPHEREx quality flags (challenge consideration: "display metadata, like contamination flags"), so users see why a spot may be unreliable.

## Plan
- [ ] Pipeline: small per-frame flags image (or bit counts) next to each frame PNG; contract field (Decisions line)
- [ ] Viewer: flags overlay toggle; flag names at the hovered pixel (OUTLIER may be a mover, SOURCE a catalogued star, PERSIST a ghost)
- [ ] Browser test on the fixture

## Findings
From idea I5 in TEAM.md (moved to the Board by Mati, 2026-11-14). A ~1.5 h + C ~1 h.

## Questions / needs from others

## Handoff

## Notes from others
