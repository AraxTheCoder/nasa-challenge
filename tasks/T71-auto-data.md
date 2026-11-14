# T71: the Live API sets up its own data on start

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T71-auto-data`
- **Depends on / feeds:** T31 (image index), T51/T53 (orbit catalogue), T21 (run kit)

## Goal
`python -m server` (and so `python web/dev.py`) fetches and builds what it needs under `data/` in a
background thread: the MPC orbit catalogue (missing or older than a week) and the SPHEREx image index
(missing). The server answers from the first second; builds use the fallbacks (SkyBoT, IRSA TAP) until
the local data is there. `--no-data-setup` turns it off.

## Plan
- [ ] `server/data_setup.py`, started from `server/__main__.py` (not `create_app`: tests stay offline)
- [ ] Atomic replace + in-memory reload of the orbit catalogue after a refresh
- [ ] Tests (fakes, no network); README

## Findings

## Handoff

## Notes from others
