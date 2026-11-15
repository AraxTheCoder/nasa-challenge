# T124: UI redesign: floating panels over the map, thumbwheel to the analysis

- **Owner:** Jonathan  ·  **Status:** doing
- **Branch:** `jonathan/T124-floating-ui` (**not merged to main until Jonathan says so**)
- **Depends on / feeds:** T55 / T90 (the map as first screen); feeds T16 (demo video, slides)

## Goal
The page looks like one modern tool: the sky map stays behind everything, the controls and the analysis
(frame tools, spectra, objects, frames) float over it as panels, and a thumbwheel on the right edge
scrolls between the map and the analysis. Elements that exist twice, are no longer used, or only
describe what is already visible are gone.

## Plan
- [x] map fixed behind the page; controls and analysis as floating panels
- [x] thumbwheel on the right edge (wheel, drag, keys, jump buttons)
- [x] one coordinate form instead of two, one quick-pick list instead of two
- [x] remove duplicate / unused elements and long descriptions
- [x] automated checks (node tests, pytest)
- [ ] visual check by Jonathan; then merge (his call)

## Findings
- Design skill installed for this: `frontend-design@claude-plugins-official` (user scope).
- Look (Jonathan, 2026-11-15): clean like Apple's UI, solid panels, no frosted glass; system font, one blue accent.
- Removed as duplicate / unused: the second RA/Dec form and second quick-pick list (one form now: Go + Build field),
  the map-tools bar ("Blink this spot", cursor position, the T82 pass buttons = `web/passes.js`: the passes blink by
  themselves and a date label picks one), the long hint texts on and under the map, "more below", the page title bar.
- Moved: base map, tiles and tile outlines under "More"; position + N-up into one readout bottom left.
- Changed default: tile outlines (the debug overlay) are off; `?debug=1` or More > Tile outlines turns them on.
- Checks: all `web/*.js` parse, 6 node tests pass, pytest 262 passed + 1 failed
  (`test_workers_end_when_their_server_is_gone`: needs `fork`, not available on Windows; not touched here).
  The browser test was not run (Jonathan's rule); ids it uses (`#field-form`, `#preset`, `#surprise`, `#form-tip`,
  `#picker`, `#empty`, ...) are kept and `?explore=0` / offline still show the form in the page.

## Questions / needs from others

## Handoff
- `python web/dev.py`, open the viewer. Wheel over the map zooms; the thumbwheel on the right edge (roll over it, drag,
  arrows) or the wheel over any panel scrolls to the analysis. >= 1280 px wide: map panels stay left, analysis is a
  column on the right; the button under the wheel widens it.
- Not merged. Joerg's T122 / T123 (region tool, progress bar) add elements to the map: merge main into this branch
  first and place them.

## Notes from others
(anyone may append here, dated and signed)
