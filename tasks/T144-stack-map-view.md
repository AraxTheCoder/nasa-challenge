# T144: Stacks visible in the default map view

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T144-stack-map-view`
- **Depends on / feeds:** T59 / T69 (stacks), T80 / T81 (map-only view); T15 (submission says "in the frame view")

## Goal
Picking a Stack (per epoch, per detector, along the selected object, along a guessed motion) shows something in
the default view (`body.map-only`), not only with `?frames=1`.

## Plan
- [ ] While a stack mode is chosen, the map view shows the field's frame image in the analysis panel (the stack is
      drawn on it; "along the selected object" needs it to click the object)
- [ ] Checks; merge; submission text no longer needs "add `&frames=1`"

## Findings
- Found during T15 (2026-11-15): `stackview.js` draws the stack into a canvas on `#stage`, and style.css hides
  `#stage` in the map-only view (`body.map-only #stage { display: none !important }`). The frames are loaded
  either way (viewer.js), so the stack is computed and never seen.

## Questions / needs from others

## Handoff

## Notes from others
(anyone may append here, dated and signed)
