# T125: Cache sweep keeps the disk from filling

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T125-disk-guard`
- **Depends on / feeds:** T58, T97 (the LRU cache sweep)

## Goal
The Live API never fills the disk. The size cap (`--cache-gb` / `SPHEREX_CACHE_GB`) is checked every 10 minutes;
parallel field builds (explicit + automatic tile builds) added ~8 GB in between and the disk (92 GB, ~60 GB used by
other things) ran full twice on 2026-11-15: builds and the browser test failed with ENOSPC.

## Plan
- [x] every minute a cheap free-space check (`shutil.disk_usage`); below `min_free_gb` (default 5) a sweep right away
      that evicts LRU entries until that much is free (on top of the size cap)
- [x] the full size-cap sweep keeps its interval
- [x] test

## Handoff
- `server/limits.py`: `Config.min_free_gb` (5, 0 = off) and `disk_check_s` (60). The sweeper thread checks
  `free_shortfall()` every minute; when short it sweeps right away with `sweep(..., free_bytes_needed=short)`, which
  keeps evicting LRU entries past the size cap until that much is freed. Fields being built are still never evicted.
- Only active when a cache cap is set (`--cache-gb` / `SPHEREX_CACHE_GB`, as before). Log line says
  "(disk had … GB too little free)" when the guard fired.
- Test: `server/test_limits.py::test_sweep_frees_disk_space_beyond_the_cap`. pytest 162 passed.

## Notes from others
