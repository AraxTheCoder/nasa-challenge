# T58: All: Limits before a public deploy: rate limit per IP, cap on concurrent builds, `refresh=1` only with a token, cache size cap with eviction

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T58-public-limits`
- **Depends on / feeds:** T14 (deploy), T47

## Goal
A public Live API can't be made to download unlimited IRSA/AWS data or flood JPL: per-IP rate limit, a cap on concurrent builds, `refresh` behind a token, a cache size cap with eviction.

## Plan
- [x] `server/limits.py`, only with `python -m server --public` (or `SPHEREX_PUBLIC=1`): per-IP token buckets for
      all API calls (tiles separate, larger) → 429 + Retry-After
- [x] New expensive jobs (field build, all-exposure spectrum, field spectra) cost one job per IP (30/h, burst 10)
      and are capped server-wide (`--max-jobs`, default 4) → 503 `busy` + Retry-After; polling / cached is free
- [x] `refresh=1` ignored and `POST /api/settings` 403 without `SPHEREX_ADMIN_TOKEN` (`?token=` / `X-Admin-Token`)
- [x] Cache cap (`--cache-gb`, default 20): LRU sweep every 10 min over targets, cutouts, spectra, field spectra,
      sky labels; a field being built counts but is never evicted. Orbit catalogue, index, HiPS cache untouched
- [x] CONTRACTS v0.22 + Decisions line; tests `server/test_limits.py`

## Findings
From idea I1 in TEAM.md (moved to the Board by Mati, 2026-11-14). Server side, ~1 h. Suggested owner: Jonathan (server).

## Questions / needs from others

## Handoff
Public server: `SPHEREX_ADMIN_TOKEN=… python -m server --public --host 0.0.0.0 [--trust-proxy behind your own
proxy] [--cache-gb 20] [--max-jobs 4]`. The viewer shows the server's message for 429 / 503 as is. Off by
default: the team's servers are unchanged.

## Notes from others
