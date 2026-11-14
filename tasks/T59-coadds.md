# T59: A/C: Per-detector co-adds per epoch: mean/median of the aligned frames per detector and epoch as extra frames, for faint red sources

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T59-stacks`
- **Depends on / feeds:** T03/T04

## Goal
Faint objects (brown dwarfs like WISE 0855, Eps Ind B) become visible: per detector and epoch, combine the aligned frames into one deeper frame (challenge consideration: "add together all the data taken by each of the six detector arrays").

## Plan
- [ ] Pipeline: co-add frames per (epoch, detector), noise-weighted mean or median, no-data where all inputs have none
- [ ] Contract: extra frames with `kind: "coadd"`, `n_exposures` (Decisions line)
- [ ] Viewer: co-adds selectable and blinkable across epochs, labelled as co-adds
- [ ] Check on the official brown-dwarf fields

## Findings
- 2026-11-14 Mati (Claude), change of plan: builds keep only 2 frames per epoch + detector, so a server-side
  co-add per (epoch, detector) gains only √2 and needs a contract change. Instead the viewer stacks the aligned
  frames it already has (no API or contract change): "per epoch, all detectors" (12 frames, ~3.5× S/N; blink
  epochs with less noise) and "per detector, all epochs" (6 frames, ~2.4×; a deep image per band). Display
  only, not photometry. A server-side co-add of *all* exposures stays possible later (with T66's reads).
From idea I3 in TEAM.md (moved to the Board by Mati, 2026-11-14). A ~2 h + C ~0.5 h. Works best together with T66 (more frames per field).

## Questions / needs from others

## Handoff

## Notes from others
