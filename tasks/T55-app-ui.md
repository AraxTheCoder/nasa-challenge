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
- [ ] Port relevant `web/` changes made after the copy
- [ ] When done: decide (TEAM.md Decisions) whether `app/` replaces `web/`

## Findings
- Copy taken from main at 6026134 (2026-11-14); refreshed from `web/` at 07974ed (2026-11-14, before any redesign edit): T52 labels, T63 spectrum, T72 map names, new `skylabels.js` + `spectrum.js`.

## Questions / needs from others
- [to everyone] Don't build features in `app/`; keep working in `web/` as before. `app/` is UI work only.

## Handoff
`python web/dev.py`, then open `http://localhost:8080/app/` (redesign) or `/web/` (current viewer).

## Notes from others
