# T11: Static viewer skeleton

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T11-viewer-skeleton` (merged)
- **Depends on / feeds:** feeds T12, T13, T14 and the Live API client (CONTRACTS v0.3)

## Goal
A browser page that loads `index.json` + `target.json`, shows the frames and blinks between two,
with no build step.

## Plan
- [x] Load `index.json` and `target.json` from a target folder; target picker
- [x] Stack all frames (preloaded) and toggle visibility, so blinking doesn't flicker
- [x] A/B choice per frame, blink with adjustable interval, keys Space / X / ←→
- [x] Frame info (time, MJD, epoch, wavelength, detector, obs id, FITS link, A–B time and λ gap)
- [x] Synthetic: header badge + watermark on the image; missing flag counts as synthetic
- [x] Transparent pixels shown hatched as "no data" (matches CONTRACTS v0.2 alpha 0)
- [x] Accept `schema_version` 0.1 and 0.2

## Findings
- Plain HTML/CSS + one ES module (`web/app.js`, ~400 lines) is enough at this size. If state gets
  tangled in T12/T13 (filters vs. A/B vs. overlays), the fallback is Preact + htm vendored into
  `web/vendor/`, still no build step.
- Tested headless (Playwright/Chromium) on the fixture: load, badge/watermark, A/B defaults, flip,
  step, row click, blink alternation, phone width (390 px, no horizontal scroll), missing data root
  and unknown target messages. The test script is not committed yet.

- **Fix (2026-11-14, Mati's report):** in the narrow layout the frame table sits under the image and
  `scrollIntoView()` on the shown row scrolled the whole page there on every blink. Now only the
  table's own box scrolls (`keepRowVisible` in `viewer.js`). Arrow keys also step when a button has
  focus. Regression checks in `web/tests/browser_test.py`.

## Questions / needs from others
- (answered) [to Joerg] no-data pixels as alpha 0: yes, in CONTRACTS v0.2.

## Handoff
- Run: `python3 -m http.server 8000` from the repo root, open <http://localhost:8000/web/>.
  URL params `?data=<folder>` and `?target=<id>`. See `web/README.md`.
- Data root: `web/targets/` if it has an `index.json`, else `../fixtures/targets/` (the 404 in the
  console is that probe).
- **Not yet consistent with CONTRACTS v0.3:** the viewer reads static folders and does not call the
  Live API (`/api/target?ra=&dec=&size=`, job polling, images relative to `target_url`, `?ra=&dec=`
  in the page URL). That needs its own task.
- For T13: `#overlay` is an SVG on top of the image with `viewBox="-0.5 -0.5 W H"`, so JSON `x/y`
  pixel coordinates can be used as-is.
- For T12: `state.frames` is sorted by MJD; `show(id)`, `setSlot("a"|"b", id)` and
  `renderFrameTable()` are the hooks. v0.2 `pairs` are not used yet (a "matched pairs" blink mode
  would start from `defaultPair()`).

## Notes from others
(anyone may append here, dated and signed)
