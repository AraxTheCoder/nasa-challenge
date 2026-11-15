# T125: Cache sweep keeps the disk from filling

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T125-disk-guard`
- **Depends on / feeds:** T58, T97 (the LRU cache sweep)

## Goal
The Live API never fills the disk. The size cap (`--cache-gb` / `SPHEREX_CACHE_GB`) is checked every 10 minutes;
parallel field builds (explicit + automatic tile builds) added ~8 GB in between and the disk (92 GB, ~60 GB used by
other things) ran full twice on 2026-11-15: builds and the browser test failed with ENOSPC.

## Plan
- [ ] every minute a cheap free-space check (`shutil.disk_usage`); below `min_free_gb` (default 5) a sweep right away
      that evicts LRU entries until that much is free (on top of the size cap)
- [ ] the full size-cap sweep keeps its interval
- [ ] test

## Notes from others
