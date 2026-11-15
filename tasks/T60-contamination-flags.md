# T60: A/C: Contamination flags in the viewer: per-frame FLAGS bits exported with the frame, overlay toggle, flag names at the inspected pixel

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T60-flags`
- **Depends on / feeds:** T04

## Goal
The viewer can show SPHEREx quality flags (challenge consideration: "display metadata, like contamination flags"), so users see why a spot may be unreliable.

## Plan
- [ ] Pipeline: small per-frame flags image (or bit counts) next to each frame PNG; contract field (Decisions line)
- [ ] Viewer: flags overlay toggle; flag names at the hovered pixel (OUTLIER may be a mover, SOURCE a catalogued star, PERSIST a ghost)
- [ ] Browser test on the fixture

## Findings
- 2026-11-15 step 1 (merged): `pipeline/flags.py` has the 22 mask planes of the FLAGS header (MSKNnnnn, read from a
  DR1 image) with kind (bad / warn / info) and plain words. Photometry returns `frames[].flags` + `flag_meanings`
  (CONTRACTS); the spectrum panel shows "SPHEREx quality flags at this spot". Barnard's Star: TRANSIENT, BLOOM in
  298 of 298 exposures, OVERFLOW (saturated) in 297, PERSIST in 21.
- Step 2: `flags.field_mask` (FLAGS of every frame resampled to the field grid; only flags in >= 15 % of frames
  drawn, so one-off cosmic rays don't paint the field), `server/flagsmap.py` (`/flags`, `/flags.png`, cached next
  to target.json), `web/flagsmap.js` ("Quality flags" toggle in the map bar, overlay through explore.addDrawHook).
  RW Aur field: 36 frames, 2.2 % of pixel-frames unreliable; red discs on the saturated stars, amber specks.
From idea I5 in TEAM.md (moved to the Board by Mati, 2026-11-14). A ~1.5 h + C ~1 h.

## Questions / needs from others

## Handoff

## Notes from others
