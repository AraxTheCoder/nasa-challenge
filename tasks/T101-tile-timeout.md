# T101: Map tile downloads get a time limit

- **Owner:** Mati  ·  **Status:** review (not yet seen working in a browser)
- **Branch:** `mati/T101-tile-timeout`
- **Depends on / feeds:** T94 (missing tiles; this was a note there)

## Goal
A tile download that gets no answer is given up after a while and asked again like any other failed tile,
so a crashed server or a dropped connection cannot leave the map without tiles until a reload.

## Plan
- [x] Time limit per download in `load()` (`web/sky.js`): longer for live-rendered tiles
- [x] A timed-out download counts as a failure (retry with back-off), not as "left the screen"

## Findings
Seen 2026-11-14 ~23:20: the Live API was OOM-killed twice (see T98); the tile downloads in flight in Mati's
browser (Windows browser → WSL) never got an answer, each kept one of the 6 slots (`st.loads`), and the tab
asked for no tile at all afterwards. `fetch` has no time limit of its own.

## Questions / needs from others

## Handoff
- `web/sky.js` `load()`: a timer aborts the download after 45 s (150 s for live-rendered tiles: deep zoom and
  survey passes) and marks the job `timedOut`; the abort then goes down the normal failure path (retry with
  back-off, after 5 tries the T94 pause and a fresh start) instead of "left the screen".
- Checked: `node --check`, the six node tests. Not checked in a browser (no working Chromium on Mati's
  machine); CI's browser test covers regressions, not the hang itself.
- To see it by hand: zoom to level 6+, stop the Live API while tiles are loading, start it again: tiles must
  come back within about a minute without a reload.

## Notes from others
(anyone may append here, dated and signed)
