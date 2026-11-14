# T61: B: Appear / disappear / brightness change between epochs, not only motion: sources present in one epoch and not another, or much brighter / fainter

- **Owner:** –  ·  **Status:** open
- **Branch:** –
- **Depends on / feeds:** T06, T49

## Goal
Detection also reports objects that appear, vanish or change brightness between epochs (variables, transients), not only movers.

## Plan
- [ ] On wavelength-matched pairs (CONTRACTS Pair): sources in A without counterpart in B and vice versa
- [ ] Flux ratio at matched wavelength for matched sources (use T49 photometry), flag large changes
- [ ] Write them as detections with a clear `reason` (contract: maybe a new status or `kind`, Decisions line)
- [ ] Viewer: list + mark them

## Findings
From idea I6a in TEAM.md (moved to the Board by Mati, 2026-11-14). Needs T06 source extraction.

## Questions / needs from others

## Handoff

## Notes from others
