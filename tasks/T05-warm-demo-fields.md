# T05: Pre-build the demo fields in the Live API cache

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T05-warm` (merged)
- **Depends on / feeds:** T02–T04 + T17 (pipeline.build with pairs), `web/presets.json`; T14/T16 (demo)

## Goal
The five official test fields (`web/presets.json`) are built in the cache before the demo, so they
open instantly instead of after a 30+ minute IRSA download. Since the live-data decision this is cache
warm-up, not committed files (TEAM.md Decisions: "T05 becomes cache warm-up").

## Plan
- [x] `web/warm.py`: request every preset from a Live API (any `--api`), show progress, wait until ready
- [x] `python web/dev.py --warm` runs it against the local API
- [x] Warm the five fields locally with T17 pairs; check each in the viewer

## Findings
- Warmed on Mati's machine (live server with T17 pairs), all five ready in ~9.5 min (Barnard's
  Star re-rendered from cached cutouts; the other four cold):

  | Field | frames | epochs | pairs | labels |
  |---|---|---|---|---|
  | Barnard's Star | 36 | 3 | 9 | 271 |
  | Epsilon Indi B | 44 | 4 | 8 | 61 |
  | WISE 0855-0714 | 36 | 3 | 6 | 83 |
  | RW Aurigae | 36 | 3 | 4 | 183 |
  | R Draconis | 24 | 2 | 5 | 42 |

- Gotcha: a fixture-mode run leaves synthetic copies under the same cache ids; live mode served them
  as "ready" until `refresh=1` (reported to Jonathan in TEAM.md Questions). `warm.py --refresh` fixes it.
- The cache is per machine (`data/targets/`): whichever machine runs the demo (T14) must be warmed there.

## Questions / needs from others

## Handoff
- Before a demo, on the machine that serves the API: `python web/warm.py` (or `python web/dev.py --warm`).
  Against a deployed API: `python web/warm.py --api https://…`. `--refresh` after a new data release
  or pipeline change; `--only "<name>"` for single fields.
- Fields come from `web/presets.json`; add one there and it is warmed and offered in the quick picks.

## Notes from others
(anyone may append here, dated and signed)
