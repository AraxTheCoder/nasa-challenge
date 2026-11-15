# T101: Map tile downloads get a time limit

- **Owner:** Mati  ·  **Status:** doing
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

## Notes from others
(anyone may append here, dated and signed)
