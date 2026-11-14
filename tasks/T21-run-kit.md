# T21: Everyone can run the viewer locally

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T21-run-kit`
- **Depends on / feeds:** T18 (server), T20 (viewer ↔ API); helps T14, T16

## Goal
Any teammate (Linux, macOS, Windows, WSL) can go from a fresh clone to the working viewer in a
browser with a few copy-paste commands, without port clashes or guessing which process to start.

## Plan
- [ ] `web/dev.py`: one command starts the Live API + a static server for the viewer, prints the URL,
      opens the browser; `--fixture` / `--live`, `--api-port`, `--web-port`; Ctrl+C stops both
- [ ] Viewer finds the API on the same host as the page (not hard-coded `localhost`), so it also
      works when opened from another machine on the LAN
- [ ] Top-level `README.md` "How to run": Python version, venv on Linux/macOS/Windows, install, run
- [ ] Check it from a clean venv; note dev-only deps (pytest, httpx, playwright)

## Findings

## Questions / needs from others

## Handoff

## Notes from others
(anyone may append here, dated and signed)
- 2026-11-14 [Joerg] FYI: T22 (movement paths) adds two event-dispatch lines to `web/viewer.js`
  (`viewer:target`, `viewer:frame`) and imports a new `web/paths.js`. Shouldn't touch your T21 files;
  shout in tasks/T22-movement-paths.md if it does.
