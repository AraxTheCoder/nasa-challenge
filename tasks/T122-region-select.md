# T122: Analysis region drawn with the mouse

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T122-T123-region-progress`
- **Depends on / feeds:** the map (T36/T90), field builds (T18), links (?ra=&dec=&size=), T111

## Goal
The red square on the map is the field: the region the tool downloads and analyses. The user should choose it:
a "▭ Select region" tool, drag a rectangle on the map, and the field is built there (square, the longer side,
5–210′, the API's limits), like a link with that position and size.

## Plan
- [x] `web/region.js`: tool button on the map; while active, a drag draws the rectangle (map panning paused),
      release builds the field; Esc / the button again cancels
- [x] Browser check: drawn region → field of that centre and size, red square there
- [x] The red square stays during the computation (asked by Joerg): `loadField` in app.js outlines the asked-for
      field as soon as an explicit load starts, not only when it is ready

## Findings / handoff
- "▭ Select region" sits under the 💬 button (top right of the map; bottom right on phones). While it is on, the
  cursor is a crosshair, dragging draws a dashed red rectangle and a line at the bottom says the field it will
  become ("6′ field at RA …, Dec …", with "(largest field: 210′)" when clamped).
- Release = `?ra=&dec=&size=` pushed + `popstate` (same path as a shared link / the tour), so the field is built
  or opened from the cache, and the URL can be shared. Size = longer sky side of the rectangle, 5–210′.
- Map panning is paused by capture-phase pointer listeners on `#sky` (sky.js untouched). A drag under 6 px is
  ignored; Esc or the button cancels. Console: `spherexRegion.set(true)`.
- Browser test (`web/tests/browser_test.py`) 0 failures; live check on M101: square drawn, build starts, square
  stays in place for the whole build.

## Notes from others
