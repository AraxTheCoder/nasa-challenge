# T99: Spectrum workers outlive their server

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T99-orphan-workers`
- **Depends on / feeds:** T83 (worker pool), T98 (pool sized + idle shutdown, Mati)

## Goal
When the Live API stops (restart by the auto-pull, Ctrl+C, crash), its spectrum worker processes exit too.

## Findings
- 2026-11-15 ~02:00, WireGuard host: 324 `multiprocessing.forkserver` processes, 28.7 GB RSS, 1 GB RAM free;
  all but 17 older than the running server (each restart left its 16 workers + fork server). A headless browser
  tab crashed on the R Dra field. The 289 orphans stopped by hand: 28 GB free again.
- Cause: workers come from the fork server, not the API process; nothing tells them the API is gone, and T98's
  idle shutdown runs in the API process, so it dies with it.

## Plan
- [ ] Pool initializer: a watchdog thread in each worker exits when the server process (pid passed in) is gone
- [ ] Test: a pool whose "server" pid disappears ends its workers

## Notes from others
