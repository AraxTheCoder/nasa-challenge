# T144: Stacks visible in the default map view

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T144-stack-map-view`
- **Depends on / feeds:** T59 / T69 (stacks), T80 / T81 (map-only view); T15 (submission says "in the frame view")

## Goal
Picking a Stack (per epoch, per detector, along the selected object, along a guessed motion) shows something in
the default view (`body.map-only`), not only with `?frames=1`.

## Plan
- [x] While a stack mode is chosen, the map view shows the field's frame image in the analysis panel (the stack is
      drawn on it; "along the selected object" needs it to click the object)
- [x] Checks (stackview.js syntax, `web/tests/stack_check.mjs`); merged
- [x] Seen in a browser (Mati, 2026-11-15: matches the description); submission text updated

## Findings
- Found during T15 (2026-11-15): `stackview.js` draws the stack into a canvas on `#stage`, and style.css hides
  `#stage` in the map-only view (`body.map-only #stage { display: none !important }`). The frames are loaded
  either way (viewer.js), so the stack is computed and never seen.

## Questions / needs from others

## Handoff
- `web/stackview.js` `setMode()` sets `body.stack-on` while a stack mode is chosen; style.css shows `#stage` in the
  map view then (`body.map-only.stack-on #stage`). Stack "off" hides it again. Nothing else changes.
- Checked by Mati in the browser on Barnard's Star (per epoch, blink A/B, off).

## Notes from others
(anyone may append here, dated and signed)
