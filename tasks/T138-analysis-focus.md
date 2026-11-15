# T138: Crosshair and analysis selection

- **Owner:** Codex (selection) · **Status:** doing
- **Branch:** `main`

## Goal
A direct map click or pin pick focuses the exact point spectrum and centres the field analysis there, using the current field-size setting. Do not retain old field results or lose the selection to automatic tile/label updates.

## Findings
The crosshair is local to photometry.js. Region tools still use the last viewer target; every viewer:target event resets the point spectrum to the field centre. Pin picks update only coordinates/URL. A 280 ms click delay also projects the clicked pixel after the view may have moved.

## Plan
- [ ] Connect map/pin selection to an explicit analysis field without moving the camera.
- [ ] Clear stale field results while loading; retain point selection across target/label refreshes.
- [ ] Keep automatic tile builds from replacing a selected region.
- [ ] Preserve drag/double-click behavior; verify rapid selection and stale responses.

## Handoff
Pending.

## Notes from others

- 2026-11-15 [Mati] T139 (merged on main) changed the labels / known-objects refresh in web/app.js: `setLabels()` and
  `loadObjects()` now call `refreshShown(fresh)` instead of `app.shownTarget = fresh; publishTarget(fresh)` (it also
  updates autoField and the running blink). If your "retain point selection across target/label refreshes" touches
  those lines, keep the refreshShown call; it still ends in publishTarget(fresh), so viewer:target fires as before.
