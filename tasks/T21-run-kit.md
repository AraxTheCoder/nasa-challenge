# T21: Everyone can run the viewer locally

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T21-run-kit` (merged)
- **Depends on / feeds:** T18 (server), T20 (viewer ↔ API); helps T14, T16

## Goal
Any teammate (Linux, macOS, Windows, WSL) can go from a fresh clone to the working viewer in a
browser with a few copy-paste commands, without port clashes or guessing which process to start.

## Plan
- [x] `web/dev.py`: one command starts the Live API + a static server for the viewer, prints the URL,
      opens the browser; `--fixture` / `--live`, `--api-port`, `--web-port`, `--lan`, `--no-browser`;
      Ctrl+C (and SIGTERM / SIGHUP) stops both
- [x] Viewer finds the API on the same host as the page (not hard-coded `localhost`), so it also
      works when opened from another machine on the LAN
- [x] Top-level `README.md` "How to run": Python version, venv on Linux/macOS/Windows, install, run,
      troubleshooting; `web/README.md` updated
- [x] Checked from a fresh clone with a new venv, exactly as in the README

## Findings
- **Fresh clone check** (Linux/WSL, Python 3.12.3): clone → `python3 -m venv .venv` →
  `pip install -r server/requirements.txt` → `python web/dev.py` → field loads in the browser, no page
  errors. Default mode picked fixture (no `pipeline.build` yet).
- **Security:** a plain `python -m http.server` listens on all interfaces and serves the whole repo
  (`.git`, `.venv`, any `.secret/`) to the network. `dev.py` serves only `web/` and `fixtures/`
  (checked: `/.git/config`, `/web/../.git/config`, `/web/%2e%2e/.git/config` → 404). Manual steps in
  `web/README.md` now use `--bind 127.0.0.1`.
- **Port pre-check vs TIME_WAIT:** right after a restart Linux keeps the port in TIME_WAIT; uvicorn and
  http.server bind anyway (SO_REUSEADDR), so the pre-check does the same (not on Windows, where that
  flag would allow binding over a live server).
- **Orphaned API:** before the fix, SIGTERM to `dev.py` left the API running on its port. Now
  SIGTERM/SIGHUP/SIGBREAK are handled like Ctrl+C.
- **WSL:** the launcher opens the Windows browser via `explorer.exe` (or `wslview`). `localhost` URLs
  work from Windows. `--lan` binds 0.0.0.0, but the printed 172.x address is WSL-internal; other
  machines only reach it with `networkingMode=mirrored`.
- Not tested on native Windows or macOS (no machine here); `dev.py` uses only the standard library
  plus what `server/requirements.txt` installs, and avoids POSIX-only calls except where guarded.
- Dev-only packages are not in any requirements file: `pytest` + `httpx` (server tests),
  `playwright` (web tests).

## Questions / needs from others
- [to Jonathan, T18] `server/README.md` says `python -m pytest server -q`, but `pytest` and `httpx`
  are not in `server/requirements.txt`. Maybe a `requirements-dev.txt`?
- [to anyone on Windows/macOS] Please try the README steps once and note the result here.

## Handoff
- Run: `python web/dev.py` (README "How to run"). `--help` lists the options.
- If the demo is shown from one laptop to others in the room: `python web/dev.py --lan` (not from WSL
  unless mirrored networking is on).
- `DEFAULT_API` in `web/api.js` is now derived from the page's host (port 8000); a hosted deployment
  (T14) sets it explicitly or links with `?api=`.

## Notes from others
(anyone may append here, dated and signed)
- 2026-11-14 [Joerg] FYI: T22 (movement paths) adds two event-dispatch lines to `web/viewer.js`
  (`viewer:target`, `viewer:frame`) and imports a new `web/paths.js`. Shouldn't touch your T21 files;
  shout in tasks/T22-movement-paths.md if it does.
