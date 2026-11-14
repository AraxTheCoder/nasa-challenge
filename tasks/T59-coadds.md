# T59: A/C: Per-detector co-adds per epoch: mean/median of the aligned frames per detector and epoch as extra frames, for faint red sources

- **Owner:** –  ·  **Status:** open
- **Branch:** –
- **Depends on / feeds:** T03/T04

## Goal
Faint objects (brown dwarfs like WISE 0855, Eps Ind B) become visible: per detector and epoch, combine the aligned frames into one deeper frame (challenge consideration: "add together all the data taken by each of the six detector arrays").

## Plan
- [ ] Pipeline: co-add frames per (epoch, detector), noise-weighted mean or median, no-data where all inputs have none
- [ ] Contract: extra frames with `kind: "coadd"`, `n_exposures` (Decisions line)
- [ ] Viewer: co-adds selectable and blinkable across epochs, labelled as co-adds
- [ ] Check on the official brown-dwarf fields

## Findings
From idea I3 in TEAM.md (moved to the Board by Mati, 2026-11-14). A ~2 h + C ~0.5 h. Works best together with T66 (more frames per field).

## Questions / needs from others

## Handoff

## Notes from others
