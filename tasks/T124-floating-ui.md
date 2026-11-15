# T124: UI redesign: floating panels over the map, thumbwheel to the analysis

- **Owner:** Jonathan  ·  **Status:** review
- **Branch:** `jonathan/T124-floating-ui` (merged to main 2026-11-15)
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
- Merged to main 2026-11-15 with T122 / T123 / T126 placed in the new layout (region button top right under 💬).

## Notes from others
(anyone may append here, dated and signed)
- 2026-11-15 [Joerg] Heads-up from T122/T123 (merged to main after you branched): please keep, when you merge main into
  `jonathan/T124-floating-ui`: (1) `import "./region.js"` and `import "./activity.js"` in app.js; (2) the block at the
  start of `loadField` that calls `explore.markField(...)` (red square visible while a field builds); (3) the CSS blocks
  `.region-btn` / `.region-hint` and `.activity*` at the end of style.css. `#region-btn` is appended to `#explore`
  (absolute, top 100px right 12px, under 💬); move it wherever fits your floating layout. `#activity` is a fixed bar
  at the top of the page (z-index 60).
- 2026-11-15 [Joerg] Checked `jonathan/T124-floating-ui` (ad3f0ad) against main (9d6b0d8): merging main in conflicts only in
  `web/style.css` at the end of the file (your wide-screen / phone / no-map blocks vs main's `.region-*` and `.activity*`
  blocks from T122/T123): **keep both sides**, nothing overlaps. `web/app.js` merges by itself and keeps the region /
  activity imports, the red-square block in `loadField` and the T126 blink-line text. `#explore`, `#sky`,
  `#blink-status` are still in your index.html, so region.js / activity.js work unchanged. Only look: "▭ Select region"
  is `position: absolute; top: 100px; right: 12px` in `#explore` (under 💬; on phones `bottom: 100px`): move it if
  your floating layout puts something there.

- 2026-11-15 [Mati] T137 (on Mati's word, Decision in TEAM.md) added folding to `web/hud.js`: `makeGrip()` (your grip
  + dblclick, now also used by the folded tab) and `makeFoldable()` (a `.hud-fold` – after the grip; folded =
  `.hud-folded` on the group, which hides everything but a `.hud-tab` panel, `.messages` and `.job`); `place()` doesn't
  freeze the width of a folded group. style.css: the T137 block after `.hud-dragging`, and `.hud-fold` added to the
  "nothing to show yet" row rule. Drag, dock and saved positions are unchanged. Details: tasks/T137.
- 2026-11-15 [Mati] T137 addition: `place()` now keeps all of a moved group inside the window (`MARGIN` 8 px, below
  `.app-header`'s height, `max-width` = window − 16 px; `KEEP` is only the narrowest width now), and `initHud()`
  re-places moved groups on resize and via a ResizeObserver when a group grows (not during a drag). `reset()` also
  clears `max-width`.
- 2026-11-15 [Mati] T137 fix: `place()` now measures where the panel landed after setting left/top and shifts them by
  the difference. Reason: `body:has(.app-header) .hud-moved { margin-top: 54px }` (T133) and, on narrow screens, the dock
  being the moved panel's containing block made relPos() and left/top disagree (54 px jump on every drag; drift on every
  re-place). No margins now (edges and the header's bottom are the limits). Hidden panels aren't placed.

