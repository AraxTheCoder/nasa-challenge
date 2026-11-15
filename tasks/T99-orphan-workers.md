# T99: Spectrum workers outlive their server

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T99-orphan-workers`
- **Depends on / feeds:** T83 (worker pool), T98 (pool sized + idle shutdown, Mati)

## Goal
When the Live API stops (restart by the auto-pull, Ctrl+C, crash), its spectrum worker processes exit too.

## Findings
- 2026-11-15 ~02:00, WireGuard host: 324 `multiprocessing.forkserver` processes, 28.7 GB RSS, 1 GB RAM free;
  all but 17 older than the running server (each restart left its 16 workers + fork server). A headless browser
  tab crashed on the R Dra field. The 289 orphans stopped by hand: 28 GB free again.
- Cause, reproduced: a Live API stopped with **SIGTERM** (what the auto-pull's restart and `kill` send) leaves
  its pool: the fork server is re-parented to init and its 16 workers wait forever. (An abrupt `os._exit` does not:
  the workers see their pipe close.) T98's idle shutdown runs in the API process, so it dies with it.
- With the fix, the same SIGTERM test: all 16 workers and the fork server gone within seconds.

## Plan
- [x] Pool initializer `photometry._watch_parent(server_pid)`: a daemon thread in each worker checks every 5 s
      (`os.kill(pid, 0)`) that the process that made the pool exists, and ends the worker if not
- [x] Test `pipeline/test_photometry.py::test_workers_end_when_their_server_is_gone`; by hand: SIGTERM of a real
      server holding a pool → 0 processes left (before the fix: 17)

## Notes from others
