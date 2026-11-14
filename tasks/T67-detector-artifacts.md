# T67: B: "Follows the detector, not the sky" artifact rule: a detection fixed in detector pixels while its sky position jumps (ghost, persistence, hot pixel) is an artifact

- **Owner:** –  ·  **Status:** open
- **Branch:** –
- **Depends on / feeds:** T06, T08

## Goal
Detector artifacts are not reported as movers.

## Plan
- [ ] Map each track point back to native detector pixels (frame WCS)
- [ ] Fixed detector position + jumping sky position → artifact with reason
- [ ] Seen on one detector only while overlapping frames of another show nothing → artifact
- [ ] Tune on real T06 detections; tests in detect/test_classify.py

## Findings
From idea I12 in TEAM.md (moved to the Board by Mati, 2026-11-14). B, `detect/classify.py`. ~1 h.

## Questions / needs from others

## Handoff

## Notes from others
