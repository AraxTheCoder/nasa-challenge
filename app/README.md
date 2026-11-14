# app/: UI redesign (T55), work in progress

**Only for UI redesign work (Jonathan's UI session).** Everything else (features, fixes, API
wiring, tests, other agents' work) stays in `web/` exactly as before; `/web/` remains the working
viewer and the default URL.

- Started 2026-11-14 as a 1:1 copy of the viewer files in `web/`; refreshed to `web/` at 07974ed.
- Open it via `python web/dev.py` → `http://localhost:8080/app/` (same API, same fixtures;
  `?data=../fixtures/targets/` etc. work as in `web/`).
- Changes made in `web/` after the copy are **not** picked up automatically; the T55 owner ports
  them into `app/` when needed. When the redesign is done, `app/` replaces `web/` (decided then,
  with a line under TEAM.md "Decisions").
- Tests, `dev.py`, `warm.py` stay in `web/`. Docs on how the viewer works: `web/README.md`.
