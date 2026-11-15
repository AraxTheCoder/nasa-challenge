# T134: Late layers and background blink focus

- **Owner:** Codex (map) · **Status:** done
- **Branch:** `main`

## Goal
Keep late automatic field loads, overlay requests and timers from replacing/blinking imagery that no longer belongs to the active view.

## Findings
- Automatic field builds do not validate the current centre tile/band before publishing their result.
- Pass mode notifies listeners only after awaiting layer metadata, leaving the old field epoch timer alive during the wait.
- Renderer and explore overlay setters commit after awaits without request-generation checks; an old response can replace a newer set or append stale dynamic overlays.
- User described surrounding tiles, still fairly sharp, starting to blink after waiting. These races are reproducible from code; expected survey-pass blink remains supported.

## Plan
- [x] Cache stale automatic fields without publishing/recentring them.
- [x] Stop epoch timers immediately and reject stale mode/layer/date completions.
- [x] Guard renderer/explore overlay generations and dynamic overlay indexes.
- [x] Deterministic delayed-response regressions and existing Node checks.

## Handoff
Implemented generation checks in sky.js and explore.js for replacing/clearing/appending overlay sets. Mode changes notify the page immediately, invalidate old epoch work, and old timer callbacks check source, target and focus before changing imagery. Automatic builds retain their captured tile/band key; results which arrive after navigation or while an explicit field/tool owns the map stay cached without publishing/recentring the view.

Validation: all 9 Node suites pass, including new deterministic delayed-response regressions in `blink_check.mjs` (real renderer/explore/pass controller) and `field_focus_check.mjs` (page controller with controlled I/O/timers). JavaScript syntax and diff checks pass. Browser/live visual validation not performed. Survey-pass mode intentionally continues to blink its visible tiles once loaded; this fix prevents obsolete requests/fields/timers from taking over.

To inspect: pan away during a tile build or switch band/source while metadata loads, wait for the old requests to finish, and verify the current view stays selected. Return to the old tile to reuse its cached field. Turn Blink off or select a chemistry/frame tool and verify delayed work does not restart the old field's timer.

## Notes from others
