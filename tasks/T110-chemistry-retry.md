# T110: C: Bug: a Live API restart during a chemistry measurement leaves "Failed to fetch"

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `main` (one function)
- **Depends on / feeds:** T93, T107

## Goal
Reported by Joerg's session (TEAM.md Log, 2026-11-15, T107 check): an auto-pull restart of the Live API while a
chemistry map was being measured left "Chemistry map unavailable: Failed to fetch" until the preset was picked
again. The viewer retries for a while instead (the job is gone after a restart, so the retry starts it again).

## Plan
- [ ] `ensure()` in web/chemistry.js: network errors and 5xx while polling -> wait and retry (with `start=1`) for up
      to ~60 s, note says "Live API not answering, retrying…"

## Findings

## Handoff

## Notes from others
