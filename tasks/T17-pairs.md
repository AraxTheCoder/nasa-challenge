# T17: Wavelength-matched pairs in target.json

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T17-pairs`
- **Depends on / feeds:** T04 `pipeline.build` (writes `bandwidth_um` already); T12 viewer reads `pairs`

## Goal
Every built `target.json` carries `pairs` per CONTRACTS v0.2 "Pair", so the viewer's matched-pairs
blink works on real fields.

## Plan
- [x] `pipeline/pairs.py`: `add_pairs(target)` with the contract rule (different epochs, same
      detector, |Δλ| ≤ 0.5 × smaller bandwidth, closest match first, each frame at most once per
      other epoch, `a` = earlier)
- [x] One call in `pipeline/build.py` next to `add_labels` (Jonathan's file: note in TEAM.md Log)
- [x] Tests (4, `pipeline/test_pairs.py`); checked on the real Barnard's Star frames

## Findings

## Questions / needs from others

## Handoff

## Notes from others
