# T70: B/C: Motion classes for real detections: asteroid-like / nearby star / distant body from rate, direction and shape, checked on T06 output

- **Owner:** –  ·  **Status:** open
- **Branch:** –
- **Depends on / feeds:** T06, T08, T23

## Goal
Every real detection gets a motion class that makes sense ("asteroid-like, 30″/h", "moves between epochs only: nearby star / brown dwarf", "large jump between epochs, slow drift within one: distant solar-system body").

## Plan
- [ ] Run T08 classes on real T06 detections; tune thresholds (main belt ~150 px/day; Barnard 1.7 px/yr; 500 AU body ~1 px/day in an epoch)
- [ ] Show the class in the objects panel and inspector

## Findings
From idea I15 in TEAM.md (moved to the Board by Mati, 2026-11-14). Partly done: classes for labels (T23), status + reason incl. class for detections (T08).

## Questions / needs from others

## Handoff

## Notes from others
