# app/: UI redesign (T55), work in progress

**Only for UI redesign work (Jonathan's UI session).** Everything else (features, fixes, API
wiring, tests, other agents' work) stays in `web/` exactly as before; `/web/` remains the working
viewer and the default URL.

- Started 2026-11-14 as a 1:1 copy of the viewer files in `web/`; refreshed to `web/` at 07974ed.
- Open it via `python web/dev.py` → `http://localhost:8080/app/` (same Live API as `web/`).
- 2026-11-14 redesign step 1: the sky map is the whole page. One base map only (SPHEREx 102
  bands, live deep zoom; no map picker), no north-up button/key, nothing below the map (no frame
  viewer, blink controls, timeline, brightness/spectrum analysis, side panel, footer) and no
  offline `?data=` mode. "Show" / "Blink this spot" still build the field; its epochs, traces and
  names show in the map. Modules: `app.js`, `api.js`, `util.js`, `explore.js`, `sky.js`,
  `healpix.js`, `traces.js`, `skylabels.js`.
- Step 2: the map fills the whole window (`#sky` fixed, no border); the controls float over it in
  glass panels at the edges (`.hud-tl` form + progress + messages, `.hud-tr` labels/tiles/debug,
  `.hud-bl` band + epochs + traces, `.hud-br` position + "Blink this spot", `.hud-bc` hint).
  Drags between the panels reach the map.
- Step 3 (`hud.js`): every panel group can be dragged anywhere by its grip ⠿ or any empty part of a
  panel; positions are remembered per browser (localStorage `spherex.app.hud`), double-click ⠿
  puts a panel back in its corner.
- Changes made in `web/` after the copy are **not** picked up automatically; the T55 owner ports
  them into `app/` when needed. When the redesign is done, `app/` replaces `web/` (decided then,
  with a line under TEAM.md "Decisions").
- Tests, `dev.py`, `warm.py` stay in `web/`. Docs on how the viewer works: `web/README.md`.
- Step 4: default layout = Jonathan's arrangement (2026-11-14): two docks on the left. Top: field
  request (+ progress, messages), then position + "Blink this spot". Bottom: switches above band +
  epochs. A dragged panel leaves its dock; double-click ⠿ docks it again (saved key `spherex.app.hud.v2`).
- Step 5: leaner panels: no title, no ? help button/bubble, no "SPHEREx · 102 bands" caption, no
  "SPHEREx epochs here" caption (synthetic layers still say "synthetic:"), position without "cursor",
  button "Blink". Defaults: Debug on (`?debug=0` off), Traces off, Labels off (own key `spherex.app.labels`).
- Step 6: "Show" is now "Go": jumps to the typed RA/Dec (parsed in the browser, `coords.js`, same rules
  as server/coords.py) and marks it with a pin; no build. Zoom = 3 × Field, so Blink there builds a field
  that size. Blink builds and adds `&blink=1` to the URL (a reload builds again). Panels: under the form one
  panel with position + Blink on one line and Band, Labels, Tiles, Debug on the line below; bottom: epochs.
- Step 7: a 📍 follows the mouse with the sky position in a pill below (`cursorpin.js`; hidden over panels).
  No fixed marker. "Go" moves the map so the typed RA/Dec lies under the mouse (`sky.placeAt`), keeps the
  zoom (zooms to 45′ only from wider than 3°); the Field input is gone, Blink builds 1/3 of the view
  (shown next to the button). URL: Go = ?ra=&dec=, Blink adds &size=&blink=1.
- Step 8: the mouse holds the 📍 by its head (needle below), RA and Dec in two lines to its right.
  Go centres the position and zooms to HiPS order 7 (3.22″/px, `sky.fovForOrder(7)`); the 📍 stands on the
  centre until the mouse moves (a page can't move the mouse). Epochs are line 3 of the band panel; one dock.
- Step 9: the 📍 sits just left of the point, RA/Dec right of it. After Go it stands on the position (moves
  with the map, not with the mouse) and fades after 5 s. The 📍 button next to Go is pick mode: the marker
  follows the mouse, a left click (not a drag) takes the spot into the form + URL (?ra=&dec=) and fades
  like Go; Esc cancels.
- Step 10: a standing 📍 (after Go / a pick) has its needle tip on the point and RA/Dec centred under it;
  while it follows the mouse it stays left of the cursor with RA/Dec to the right.
- Step 11: one look for the 📍 everywhere (also while it follows the mouse in pick mode): needle tip on
  the point, RA/Dec centred under it.
- Step 12: Blink builds what is on screen: a square over the whole view (its longer side; the API allows
  5–60′, so a wider view gets its centred 60′), at the map's detail (epoch tiles go to order 7). The red
  outline is that part of the view at the moment of the click (shown at once); the map no longer jumps
  when the field is ready, so you can move around while it builds and find it again by the outline.
