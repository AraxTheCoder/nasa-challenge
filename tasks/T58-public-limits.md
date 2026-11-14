# T58: All: Limits before a public deploy: rate limit per IP, cap on concurrent builds, `refresh=1` only with a token, cache size cap with eviction

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T58-public-limits`
- **Depends on / feeds:** T14 (deploy), T47

## Goal
A public Live API can't be made to download unlimited IRSA/AWS data or flood JPL: per-IP rate limit, a cap on concurrent builds, `refresh` behind a token, a cache size cap with eviction.

## Plan
- [ ] Rate limit per IP on `/api/target` (and `/objects`, `/labels`)
- [ ] Cap concurrent builds; queue or 503 + Retry-After beyond it
- [ ] `refresh=1` only with a server token (env var); ignored otherwise
- [ ] Cache size cap for `data/targets` + `data/raw`, evict least recently used
- [ ] CONTRACTS + Decisions line for the new answers (429 / 503)

## Findings
From idea I1 in TEAM.md (moved to the Board by Mati, 2026-11-14). Server side, ~1 h. Suggested owner: Jonathan (server).

## Questions / needs from others

## Handoff

## Notes from others
