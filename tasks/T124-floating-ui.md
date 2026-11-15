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
- [ ] map fixed behind the page; controls and analysis as floating panels
- [ ] thumbwheel on the right edge (wheel, drag, keys, jump buttons)
- [ ] one coordinate form instead of two, one quick-pick list instead of two
- [ ] remove duplicate / unused elements and long descriptions
- [ ] automated checks (node tests, pytest); visual check by Jonathan

## Findings

## Questions / needs from others

## Handoff

## Notes from others
(anyone may append here, dated and signed)
- 2026-11-15 [Joerg] Heads-up from T122/T123 (merged to main after you branched): please keep, when you merge main into
  `jonathan/T124-floating-ui`: (1) `import "./region.js"` and `import "./activity.js"` in app.js; (2) the block at the
  start of `loadField` that calls `explore.markField(...)` (red square visible while a field builds); (3) the CSS blocks
  `.region-btn` / `.region-hint` and `.activity*` at the end of style.css. `#region-btn` is appended to `#explore`
  (absolute, top 100px right 12px, under 💬); move it wherever fits your floating layout. `#activity` is a fixed bar
  at the top of the page (z-index 60).
