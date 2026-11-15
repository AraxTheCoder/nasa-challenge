# T138: Crosshair and analysis selection

- **Owner:** Codex (selection) · **Status:** done
- **Branch:** `main`

## Goal
A direct map click or pin pick focuses the exact point spectrum and centres the field analysis there, using the current field-size setting. Do not retain old field results or lose the selection to automatic tile/label updates.

## Findings
The crosshair is local to photometry.js. Region tools still use the last viewer target; every viewer:target event resets the point spectrum to the field centre. Pin picks update only coordinates/URL. A 280 ms click delay also projects the clicked pixel after the view may have moved.

## Plan
- [x] Connect map/pin selection to an explicit analysis field without moving the camera.
- [x] Clear stale field results while loading; retain point selection across target/label refreshes.
- [x] Keep automatic tile builds from replacing a selected region.
- [x] Preserve drag/double-click behavior; verify rapid selection and stale responses.

## Handoff
Map clicks and pin picks now dispatch a shared point/region selection. Go/presets use it too. The region uses the current field-size setting and all bands; a direct click preserves the camera. A selection clears old target-dependent results immediately, then publishes only the new field. Point photometry retains its own selection/token through viewer:target/label refreshes. An explicit analysisFocus prevents automatic tile cache hits/completions from replacing the selected field. New region builds/Go/back navigation release the previous selection. Named-source spectrum links keep their field context.

Click coordinates are resolved before the double-click delay; new gestures/cancellation clear that timer. Pin events prevent duplicate photometry without blocking the map's pointer-up cleanup. The unusual-spectra panel includes its centre and field size.

Validation: 11 Node suites pass (including extended field_focus_check and T139 blink refresh). Existing viewer browser suite 0 failures. New selection browser regression covers real page/photometry controllers with deterministic map/API adapters: exact click coordinates/full-band region size, no camera recenter, no field-centre photometry reset, refresh/pan retention, out-of-order point responses, pin once, ignored drag/double-click and Go. Added to CI. Screenshot artifacts under /tmp/t138-browser and /tmp/t138-viewer. Live SPHEREx data was not remeasured for this UI test.

## Notes from others

- 2026-11-15 [Mati] T139 (merged on main) changed the labels / known-objects refresh in web/app.js: `setLabels()` and
  `loadObjects()` now call `refreshShown(fresh)` instead of `app.shownTarget = fresh; publishTarget(fresh)` (it also
  updates autoField and the running blink). If your "retain point selection across target/label refreshes" touches
  those lines, keep the refreshShown call; it still ends in publishTarget(fresh), so viewer:target fires as before.
