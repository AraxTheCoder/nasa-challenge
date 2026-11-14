# T55: UI redesign under /app/ (web/ stays as it is)

- **Owner:** Jonathan  ·  **Status:** doing
- **Branch:** `jonathan/T55-app-ui`
- **Depends on / feeds:** T11–T49 viewer work (copied from `web/`)

## Goal
Rework the UI without blocking anyone: the redesign lives in `app/` (URL `/app/`), while `web/`
(URL `/web/`) stays the working viewer that everyone else keeps developing in.

## Plan
- [x] Copy the viewer files of `web/` to `app/` (no tests, no dev.py/warm.py)
- [x] `web/dev.py` also serves `/app/` and prints its URL; `/` still redirects to `/web/`
- [ ] UI redesign in `app/`
- [ ] Port relevant `web/` changes made after the copy
- [ ] When done: decide (TEAM.md Decisions) whether `app/` replaces `web/`

## Findings
- Copy taken from main at 6026134 (2026-11-14).

## Questions / needs from others
- [to everyone] Don't build features in `app/`; keep working in `web/` as before. `app/` is UI work only.

## Handoff
`python web/dev.py`, then open `http://localhost:8080/app/` (redesign) or `/web/` (current viewer).

## Notes from others
