# T64: A/C: Data release in the UI: release per frame (DR1 / QR3) in target.json, shown in frame info, "newer data available: rebuild" when a cached field is older

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T64-data-release`
- **Depends on / feeds:** T01, T58 (refresh token)

## Goal
Users see which SPHEREx release each frame comes from, and the tool says when a newer release exists (challenge: "easy to update with the latest data releases").

## Plan
- [ ] Pipeline: release per frame from obs_collection into target.json (contract field, Decisions line)
- [ ] Viewer: release in frame info + footer
- [ ] API: flag a cached field that predates the newest release; viewer offers Rebuild (`refresh=1`)

## Findings
From idea I9 in TEAM.md (moved to the Board by Mati, 2026-11-14). 

## Questions / needs from others

## Handoff

## Notes from others
