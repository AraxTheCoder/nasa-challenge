# T68: C: Split the big web files: filter / pairs / playback out of `viewer.js`, sky-map wiring out of `app.js` (pure refactor, browser test guards it)

- **Owner:** –  ·  **Status:** blocked
- **Branch:** –
- **Depends on / feeds:** T55

## Goal
`web/viewer.js` and `web/app.js` (~600 lines each) are split into smaller modules without behaviour change.

## Plan
- [ ] Wait for T55 (UI redesign in `app/`, a copy of `web/`): decide with Jonathan which UI lives on, then split that one
- [ ] Move filter / pairs / matching / playback into `compare.js`; sky-map wiring into the explore module
- [ ] Browser test green

## Findings
From idea I13 in TEAM.md (moved to the Board by Mati, 2026-11-14). Blocked by T55: refactoring `web/` now would make porting to `app/` harder.

## Questions / needs from others

## Handoff

## Notes from others
