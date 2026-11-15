# T110: C: Bug: a Live API restart during a chemistry measurement leaves "Failed to fetch"

- **Owner:** Mati  ·  **Status:** review (not yet seen in a browser)
- **Branch:** `main` (one function)
- **Depends on / feeds:** T93, T107

## Goal
Reported by Joerg's session (TEAM.md Log, 2026-11-15, T107 check): an auto-pull restart of the Live API while a
chemistry map was being measured left "Chemistry map unavailable: Failed to fetch" until the preset was picked
again. The viewer retries for a while instead (the job is gone after a restart, so the retry starts it again).

## Plan
- [x] `ensure()` in web/chemistry.js: network errors and 5xx while polling -> wait and retry (with `start=1`) for up
      to ~60 s, note says "Live API not answering, retrying…"

## Findings
- `ensure()` now polls in one loop: a failed fetch, a non-JSON answer or a 5xx without a job error -> note "the Live
  API is not answering (restarting?), trying again…", wait 3 s, ask again with `start=1`, for up to 90 s
  (`RETRY_S`); a `not_started` answer in the middle of polling (restarted between two polls) also starts it again.
  A real job error (`status: "error"`) still ends it with its message.
- Not reproduced end to end here (no browser; the test fields' exposures are cached, so maps finish in seconds).

## Handoff
Check: tick a feature on a field not measured yet, restart the Live API while "measuring…" shows: the note says it is
retrying, then the map appears without picking it again.

## Notes from others
