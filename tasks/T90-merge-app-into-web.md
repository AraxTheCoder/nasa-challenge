# T90: Merge `/app/` (T55 redesign) back into `/web/`

- **Owner:** Jonathan  ·  **Status:** doing
- **Branch:** `jonathan/T90-merge-app-web`
- **Depends on / feeds:** T55 (app/ redesign), T68 (unblocked once this lands)

## Goal
One viewer at `/web/`. The first screen looks like `/app/` (full-window map, floating panels, automatic
blink); scrolling down the page (scrollbar on the right) reaches everything of `/web/` the others use:
frame viewer, blink controls, analysis, spectra, candidates, outliers, timeline, side panels. Nothing of
`web/` and nothing of `app/` is dropped.

## Plan
- [ ] 3-way merge of every file both sides changed since the copy (base `07974ed`): app.js, explore.js,
      sky.js, index.html, style.css, skylabels.js, traces.js, api.js, util.js
- [ ] app-only modules into web/: hud.js, cursorpin.js, coords.js, the automatic blink (`passes.js` of app/,
      renamed so Joerg's T82 `web/passes.js` stays)
- [ ] Page layout: first screen = the app/ map stage (100vh), below it the web/ sections, page scrolls
- [ ] Checks: unit tests, web/tests/*.mjs, syntax; `/app/` left as is until the humans decide (TEAM.md)

## Findings

## Questions / needs from others
- [to everyone] `/web/` changes layout; all features stay. Please pull and look before building on web/.

## Handoff

## Notes from others
