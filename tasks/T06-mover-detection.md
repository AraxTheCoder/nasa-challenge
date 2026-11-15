# T06: Mover detection v0

- **Owner:** Mati (taken over from Jonathan, Decision 2026-11-15)  ·  **Status:** doing
- **Branch:** `mati/T06-mover-detection`
- **Depends on / feeds:** T04 (built fields), T08 (classify), T51 (`detect.run`); feeds T61, T62, T67, T70

## Goal
`python -m detect.run <target_dir>` fills `detections` for a built real field: sources that are in the
SPHEREx images at one time and not at the same sky position at other times, with a track per CONTRACTS.
The viewer's objects panel then shows them (known / unknown / artifact from T08).

## Plan
- [ ] `detect/movers.py`: sources per frame from the cached SPHEREx cutouts (IMAGE − ZODI, VARIANCE, FLAGS)
- [ ] Reference = the same sky position in frames of the same detector at other times; keep what is not there
- [ ] Confirmation = the two detectors that image the same sky at the same moment must both show it
- [ ] Link sightings close in time into one track; plug into `detect/run.py`; provenance entry
- [ ] Tests on made-up cutouts; run on the cached real fields; numbers here

## Findings

## Questions / needs from others

## Handoff

## Notes from others
(anyone may append here, dated and signed)
