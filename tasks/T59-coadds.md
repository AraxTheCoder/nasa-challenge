# T59: A/C: Per-detector co-adds per epoch: mean/median of the aligned frames per detector and epoch as extra frames, for faint red sources

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T59-stacks`
- **Depends on / feeds:** T03/T04

## Goal
Faint objects (brown dwarfs like WISE 0855, Eps Ind B) become visible: per detector and epoch, combine the aligned frames into one deeper frame (challenge consideration: "add together all the data taken by each of the six detector arrays").

## Plan
- [x] Co-add in the viewer instead (see Findings): per epoch (all detectors) / per detector (all epochs), no-data where no frame has data
- [x] Contract: not needed (client-side)
- [x] Viewer: "Stack" select next to A − B; blink/play show the stack of each frame's group; labelled
- [x] Checked on WISE 0855's field (live)

## Findings
- 2026-11-14 Mati (Claude), change of plan: builds keep only 2 frames per epoch + detector, so a server-side
  co-add per (epoch, detector) gains only √2 and needs a contract change. Instead the viewer stacks the aligned
  frames it already has (no API or contract change): "per epoch, all detectors" (12 frames, ~3.5× S/N; blink
  epochs with less noise) and "per detector, all epochs" (6 frames, ~2.4×; a deep image per band). Display
  only, not photometry. A server-side co-add of *all* exposures stays possible later (with T66's reads).
From idea I3 in TEAM.md (moved to the Board by Mati, 2026-11-14). A ~2 h + C ~0.5 h. Works best together with T66 (more frames per field).

## Questions / needs from others

- Real data (WISE 0855 field, live, 2026-11-14): "per detector" D6 (4.42–4.97 µm, 6 frames over 3 epochs) is
  visibly smoother than one frame; "per epoch" (12 frames, 0.77–4.74 µm) shows many more stars. The first version
  left a bright patch with a diagonal edge (one frame's higher sky); fixed by subtracting each frame's large-scale
  background (16-px block medians, bilinear) before adding. WISE 0855 itself stays at the noise even in the D6
  stack: W2 ≈ 13.9, below what 6 frames reach; a stack of *all* exposures (server side, with T66's reads) could.

## Handoff
- `web/stack.js` (pure, `web/tests/stack_check.mjs`) + `web/stackview.js` (wiring; `pixels` now exported from
  diff.js). Exclusive with A − B and the trail view; works with blink and Play all.
- Jonathan (T55): port the Stack select to `app/` if the frame viewer comes back there.

## Notes from others
