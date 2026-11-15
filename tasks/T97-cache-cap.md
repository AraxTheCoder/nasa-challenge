# T97: Cache cap for team servers too

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T97-cache-cap`
- **Depends on / feeds:** T58 (limits.sweep), T42 (s3chunks)

## Goal
A long-running team server must not fill its disk: the T58 cache sweep without `--public`, opt-in by size, and
covering the tile row chunks as well.

## Plan
- [x] `--cache-gb` / `SPHEREX_CACHE_GB` starts the sweep in any mode (default: off without `--public`, 20 with it);
      none of the other T58 limits apply without `--public`
- [x] `data/raw/s3chunks` entries in the sweep (least recently used first, like the rest)
- [x] WireGuard host: serve loop restarted with `SPHEREX_CACHE_GB=12`
- [x] Test: `server/test_limits.py::test_cache_cap_without_public_mode_and_tile_chunks`

## Findings
- 2026-11-15 ~01:00: 92 GB disk at 100 %, git and the auto-pull failed. data/raw: cutouts 9.9 GB, s3chunks 9.2 GB.
  11.4 GB of the least recently used evicted by hand (built fields kept).

## Notes from others
