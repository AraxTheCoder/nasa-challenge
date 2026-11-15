# T100: Map blink switch; chemistry picture survives zooming

- **Owner:** Mati  ·  **Status:** done (checked in a browser by Joerg, 2026-11-15)
- **Branch:** `mati/T100-blink-toggle`
- **Depends on / feeds:** T90 (automatic blink), T93/T96 (chemistry maps)

## Goal
1. A "Blink" switch on the map: off = the picture stands still (survey passes and field epochs); a click on
   a date label shows that one. Remembered in the browser.
2. Bug (Mati, 2026-11-15): with a chemistry map shown, zooming in or out throws it away. It must stay while
   the view is on the field it was made for.

## Plan
- [x] Switch + status text; passes and epochs stop stepping; date labels clickable
- [x] Chemistry: no hand-back to the automatic blink while a map tool holds the map and the view is on its field
- [x] node tests (6 pass), `node --check`
- [ ] browser test: could not run on Mati's machine (Chromium lacks system libraries, needs `sudo playwright install-deps`); CI runs it
- [ ] Mati looks at both in the browser

## Findings
- Cause of the bug: `decideSource()` in `web/app.js` hands the map back to the automatic blink whenever the
  key "tile under the view centre + zoom-dependent variant" changes (T90: "another tile / zoom level:
  automatic again"), and `chemistry.js` forgets its picture on that hand-back. A zoom changes the key.

## Questions / needs from others

## Handoff
- **Blink switch** (`#blink-on`, next to the blink status): off = `passes.setStill(true)` (autoblink.js `step()`
  does nothing) and the epoch timer in app.js skips; date labels (passes and epochs) are clickable and show
  that one. Stored in `localStorage` as `spherex.blink`.
- **Chemistry**: `app.mapTool` is set on `map:take` and cleared in `setManual(false)`. While it is set and the
  view centre is on the shown field (`viewOn`), `decideSource()` returns early: no hand-back, no other field
  swapped in. Leaving the field or unticking all features resumes the automatic blink as before.
- To check by hand: open a field at level 7, tick a Chemistry feature, wait for the map, zoom out two levels
  and in again: the picture must still be there and the feature still ticked. Then untick Blink: the dates
  stop changing; click another date: it shows and stays.

## Notes from others
(anyone may append here, dated and signed)
