# T122: Analysis region drawn with the mouse

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T122-T123-region-progress`
- **Depends on / feeds:** the map (T36/T90), field builds (T18), links (?ra=&dec=&size=), T111

## Goal
The red square on the map is the field: the region the tool downloads and analyses. The user should choose it:
a "▭ Select region" tool, drag a rectangle on the map, and the field is built there (square, the longer side,
5–210′, the API's limits), like a link with that position and size.

## Plan
- [ ] `web/region.js`: tool button on the map; while active, a drag draws the rectangle (map panning paused),
      release builds the field; Esc / the button again cancels
- [ ] Browser check: drawn region → field of that centre and size, red square there

## Notes from others
