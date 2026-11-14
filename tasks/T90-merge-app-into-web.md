# T90: Merge `/app/` (T55 redesign) back into `/web/`

- **Owner:** Jonathan  ·  **Status:** done
- **Branch:** `jonathan/T90-merge-app-web`
- **Depends on / feeds:** T55 (app/ redesign), T68 (unblocked once this lands)

## Goal
One viewer at `/web/`. The first screen looks like `/app/` (full-window map, floating panels, automatic
blink); scrolling down the page (scrollbar on the right) reaches everything of `/web/` the others use:
frame viewer, blink controls, analysis, spectra, candidates, outliers, timeline, side panels. Nothing of
`web/` and nothing of `app/` is dropped.

## Plan
- [x] 3-way merge of every file both sides changed since the copy (base `07974ed`): app.js, explore.js,
      sky.js, index.html, style.css, skylabels.js, traces.js, api.js, util.js
- [x] app-only modules into web/: hud.js, cursorpin.js, coords.js, the automatic blink (`passes.js` of app/,
      renamed so Joerg's T82 `web/passes.js` stays)
- [x] Page layout: first screen = the app/ map stage (100vh), below it the web/ sections, page scrolls
- [x] Checks: unit tests, web/tests/*.mjs, syntax; `/app/` left as is until the humans decide (TEAM.md)

## Findings
- Merge = web/ (everyone's features) + app/'s additions and changes. A plain 3-way merge would also have applied
  app/'s *deletions* (base maps, north up, the explore bar CSS, the frame viewer wiring in app.js): those were
  restored. Clean 3-way merges: api.js, skylabels.js, traces.js, util.js; both-sides-added hunks kept on both
  sides: sky.js (overlayProgress + addOverlays), style.css (T55/T89 + T80/T84/T76/T86/T64/T88 blocks).
- app.js = old web/app.js with every function, import and event kept (checked by inventory) + app/'s Go, 📍,
  panels, automatic blink, quiet builds, band per detector, false colour, month labels, balanced tiles.
- Ids: every id of the old web/index.html and of app/index.html exists in the new page, none twice
  (app's #field-form → #go-form, #preset → #go-preset, #explore-passes → #blink-passes, #objects-note on the map
  → #objects-hud-note; web's cursor position → #map-pos).
- `web/tests/overview_check.mjs` (T48): its band switch 1 → 2 stays inside detector 1, which since T89 is the
  same live tile; it now switches 1 → 18 (detector 2) and checks the same things.

## Questions / needs from others
- [to everyone] `/web/` changes layout; all features stay. Please pull and look before building on web/.

## Handoff
- `/web/`: first screen = the T55 map; scroll down (scrollbar) for the rest; "▾ more below" jumps there.
- Interplay: the frame viewer (T81 mapframes) and the T82 pass buttons take the map over (indicator "Blink: map
  tools / frame viewer below"); moving to another tile or zoom level hands it back to the automatic blink.
  An explicitly built field (Show, candidate, Blink this spot) blinks its epochs at any zoom while the view is on it.
- `/app/` is unchanged and still works; whether to remove it is for the humans (TEAM.md Questions).
- Not run here (Jonathan's rule): `web/tests/browser_test.py`; please run it in CI / by hand.

## Notes from others
