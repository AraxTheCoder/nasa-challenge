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
