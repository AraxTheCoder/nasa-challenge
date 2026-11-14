# T55: UI redesign under /app/ (web/ stays as it is)

- **Owner:** Jonathan  ·  **Status:** doing
- **Branch:** `main` (short-lived worktrees only for edits, merged straight back; from 2026-11-14 ~17:00)
- **Depends on / feeds:** T11–T49 viewer work (copied from `web/`)

## Goal
Rework the UI without blocking anyone: the redesign lives in `app/` (URL `/app/`), while `web/`
(URL `/web/`) stays the working viewer that everyone else keeps developing in.

## Plan
- [x] Copy the viewer files of `web/` to `app/` (no tests, no dev.py/warm.py)
- [x] `web/dev.py` also serves `/app/` and prints its URL; `/` still redirects to `/web/`
- [ ] UI redesign in `app/`
  - [x] Step 1 (Jonathan, 2026-11-14): map is the whole page: only "SPHEREx · 102 bands · live deep
        zoom" (picker removed), north-up button + N key removed, everything below the map removed
        (frame viewer, blink controls, timeline, brightness/spectrum analysis, side panel, footer),
        offline `?data=` mode removed; unused modules deleted from `app/`
  - [x] Step 2 (Jonathan, 2026-11-14): map fills the whole window; controls float over it in panels
        around the edges (top left form/progress/messages, top right switches, bottom left band +
        epochs, bottom right position + Blink this spot, bottom centre hint)
  - [x] Step 3 (Jonathan, 2026-11-14): panels draggable (grip ⠿ or empty panel area), layout
        remembered per browser, double-click ⠿ resets a panel (`app/hud.js`)
  - [x] Step 4 (Jonathan, 2026-11-14): Jonathan's arrangement is the default: left docks, top = field
        request then Blink this spot, bottom = switches above band + epochs; hint moved bottom right
  - [x] Step 5 (Jonathan, 2026-11-14): no title, no ? help, no map/epochs captions, no "cursor", button
        "Blink"; defaults Debug on, Traces off, Labels off
  - [x] Step 6 (Jonathan, 2026-11-14): "Go" (was Show) only jumps + pins, no build; position + Blink on one
        line, Band + Labels + Tiles + Debug on the line below in the same panel
  - [x] Step 7 (Jonathan, 2026-11-14): 📍 + RA/Dec pill follow the mouse; Go puts the position under the
        mouse (no fixed marker); Field input removed (Blink = 1/3 of the view)
  - [x] Step 8 (Jonathan, 2026-11-14): mouse at the pin head, RA/Dec two lines to the right; Go centres +
        zooms to order 7, pin on the centre until the mouse moves; epochs = line 3 of the band panel
  - [x] Step 9 (Jonathan, 2026-11-14): pin left of the point; after Go it stays on the position and fades
        after 5 s; 📍 button = pick mode (follows the mouse, left click sets form + URL, then fades)
  - [x] Steps 10-12 (Jonathan, 2026-11-14): pin tip on the point with RA/Dec below; Blink builds the whole
        view (≤ 60′, API limit) and the red outline marks that part of the view; no jump when it is ready
  - [x] Step 13 (Jonathan, 2026-11-14): survey passes blink by themselves at level 7 (`app/passes.js`,
        T82 layers `spherex-live-p<n>` on the map's own tile grid, no build); loaded one level earlier
        (order 6: the tiles a zoom in at the centre needs), only fully loaded passes take part; switch
        "Blink: survey passes / field epochs" next to Debug (epochs = the old Blink button, now only at
        level 7); a built field switches to epochs. Server: the VM renders pass tiles
        (`/tiles/live-p<n>/`), the Live API asks it in remote mode (old VM → local), passes listed in
        the live properties (`x_survey_passes`)
  - [x] Step 14 (Jonathan, 2026-11-14): no Blink button, no red outline, no play/pause: at level 7 the map
        blinks by itself; passes / epochs labelled with when they were taken ("Aug–Sep 2025", from
        `GET /api/pass-dates` / the epoch's frame dates); "field epochs" builds the view's field once the
        map rests 2 s. Faster passes: base map stops at order 6 while passes blink (no competing live
        renders), the Live API renders the other passes of a tile as soon as one is asked, VM 12 slots +
        36 image / 48 S3 threads (`deploy/install-app.sh` drop-in)
  - [x] Step 15 (Jonathan, 2026-11-14): the source switches by itself: survey passes; resting 2 s at level 7 on
        one HiPS order-6 tile builds that tile's field quietly (square over the whole tile, ~86′, ~40 s; same
        grid for everyone, so built once) and its epochs blink while the view stays on the tile; out of the
        tile or zoomed out → passes again. Text indicator "Blink: …" instead of the switch. Tiles mode
        `balanced` (default): local + VM by measured throughput (`tilegen/client.py`)
  - [x] Step 16 (Jonathan, 2026-11-14): passes blink from level 6 (field epochs at 7); base under the passes
        capped at order 5; pass labels per visit ("Apr & Oct 2025", `visits` in `/api/pass-dates`)
- [ ] Port relevant `web/` changes made after the copy
- [ ] When done: decide (TEAM.md Decisions) whether `app/` replaces `web/`

## Findings
- Step 13: pass vs epoch. Epoch = the visits to that spot, grouped by gaps > 30 d (pipeline/query.py);
  pass = a fixed 182.6 d all-sky window from 2025-05-01 (tilegen/render.py). Usually the same; near the
  ecliptic poles (observed almost all the time) a pass boundary cuts through. A pass tile is a mosaic
  (1 image, more where it has holes): a fast asteroid can be cut or doubled at a tile edge; slow movers
  (stars, Planet X) are fine. Index (data/mirror) has passes 1-3 (to 2026-10).
- Step 14 speed (18 new pass tiles = 6 positions x 3 passes, 4 browser connections, via the Live API):
  20-24 s before -> 12-13 s. The VM (e2-medium, 2 vCPU) is CPU-bound (0 % idle; one Python process only
  reached ~1.2 CPUs: GIL -> now 2 workers); pass tiles use 1 image + fill (was 3); pass tiles beyond 6 at
  the VM render on this PC (`TILES_REMOTE_MAX`); a pass tile asked for starts the other passes. Next lever
  costs money: a bigger VM (e2-standard-8 + `--workers 8`).
- Step 15 balancing, fresh spots, 18 pass tiles, 12 at once, interleaved (2026-11-14): balanced 9.1 s
  (36 local / 18 VM), local only 13.2 s, VM only 13.8 s. A latency-only cost (avg x (in flight + 1)) was
  worse (14-19 s): it ignores that both sides render many tiles at once; throughput (Little's law) fixed it.
- Copy taken from main at 6026134 (2026-11-14); refreshed from `web/` at 07974ed (2026-11-14, before any redesign edit): T52 labels, T63 spectrum, T72 map names, new `skylabels.js` + `spectrum.js`.

## Questions / needs from others
- [to everyone] Don't build features in `app/`; keep working in `web/` as before. `app/` is UI work only.

## Handoff
`python web/dev.py`, then open `http://localhost:8080/app/` (redesign) or `/web/` (current viewer).

## Notes from others
