# T20: Viewer ↔ Live API

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T20-live-api-client` (merged)
- **Depends on / feeds:** T11 (viewer), T18 (Live API); feeds T12, T13, T14, T05 (cache warm-up list)

## Goal
A user types RA/Dec (decimal or sexagesimal) and a field size, or opens a link with
`?ra=&dec=&size=`, and the viewer requests that field from the Live API, shows build progress, then
blinks it. Matches CONTRACTS v0.3 "Live API" and "Frontend URL".

## Plan
- [x] Coordinate form: RA, Dec, size (5–60′, default 15), submit → `GET /api/target`
- [x] Page URL carries `?ra=&dec=&size=`; opening such a link requests the field on load; back/forward work
- [x] 202 → poll `poll_url` every 2 s with a progress bar (step, done/total, message, elapsed);
      200 → load `target_url`; 400 / 404 no_data / 500 / unreachable → clear message
- [x] Resolve frame images against `target_url`; API base from `?api=` (default `http://localhost:8000`)
- [x] "Rebuild" (`refresh=1`, with a confirm) and "Copy link"
- [x] Quick picks for the five official test fields (`web/presets.json`, SIMBAD query + timestamp recorded)
- [x] `?data=<folder>` offline mode for static target folders (no server needed)
- [x] Browser test against `python -m server --fixture`: `web/tests/browser_test.py`, 27 checks pass

## Findings
- **Test field positions** (`web/presets.json`): SIMBAD TAP, retrieved 2026-11-14T10:05:00Z from the
  Harvard mirror (the CDS host answered "page unavailable"). J2000 position + proper motion moved to
  epoch 2026.0. This matters: since J2000, Barnard's Star moved 4.5′, WISE 0855 3.5′, eps Ind B 2.0′.
  Cross-check: Joerg's T19 label for Barnard's Star (269.44629, +4.76736) is within a few arcsec of
  the preset (269.4463, +4.7682).
- **WISE 0855 in the challenge text** (08h55m10.831s, −7°14′42.53″) is its ~2010 (WISE) position,
  about 2′ from where it is now. Both are inside a 15′ field.
- **Motion vs pixel size:** SPHEREx pixels are 6.15″. Barnard's Star (10.4″/yr) moves ~0.8 px between
  two survey passes 6 months apart and ~1.7 px over a year; WISE 0855 ~0.7 px per pass. Motion is
  visible in a blink but small; zoom (T12/T13 or later) will help.
- **Port clash:** the old T11 README said `python3 -m http.server 8000`, the same port as the Live
  API default. The README now serves the viewer on 8080.
- Code split into `api.js` / `viewer.js` / `app.js` / `util.js` so T12 and T13 can work in
  `viewer.js` without touching request handling.

## Questions / needs from others
- [to Jonathan, T18] Fixture mode keeps the fixture's `center` (RA 150.0, Dec 2.2) while the name
  says "served for request RA … Dec …"; CONTRACTS says `center` is the rounded requested position.
  Only affects fixture mode, low priority.
- [to whoever does T05] Warm the cache with the coordinates in `web/presets.json` (decimal, 4 digits,
  size 15) so the ids match what the quick picks request.
- [to T14] If the viewer is served over https (GitHub Pages), the API must be https too (browsers
  block http calls from https pages). Set `DEFAULT_API` in `web/api.js` or link with `?api=`.

## Handoff
- Run: see `web/README.md` (API on :8000, viewer on :8080). Test: `python web/tests/browser_test.py`.
- `api.js` `requestField(apiBase, {ra, dec, size, refresh}, {onProgress, signal})` → `{id, targetUrl}`;
  throws `ApiError` with `kind` = `bad_request | no_data | error | unreachable`.
- `viewer.js` `showTarget(target, targetUrl)` takes parsed JSON; T12/T13 extend it there. CONTRACTS
  v0.4 `labels` (T19) are not drawn yet: that is T13's overlay (`#overlay`, pixel coords as-is).
- Not done (ideas): a "recent fields" list from `GET /api/targets`; showing which preset/object the
  field is centred on when the pipeline name is just the id.

## Notes from others
(anyone may append here, dated and signed)
