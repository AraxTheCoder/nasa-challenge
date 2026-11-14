# T05: Pre-build the demo fields in the Live API cache

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T05-warm`
- **Depends on / feeds:** T02–T04 + T17 (pipeline.build with pairs), `web/presets.json`; T14/T16 (demo)

## Goal
The five official test fields (`web/presets.json`) are built in the cache before the demo, so they
open instantly instead of after a 30+ minute IRSA download. Since the live-data decision this is cache
warm-up, not committed files (TEAM.md Decisions: "T05 becomes cache warm-up").

## Plan
- [ ] `web/warm.py`: request every preset from a Live API (any `--api`), show progress, wait until ready
- [ ] `python web/dev.py --warm` runs it against the local API
- [ ] Warm the five fields locally with T17 pairs; check each in the viewer

## Findings

## Questions / needs from others

## Handoff

## Notes from others
(anyone may append here, dated and signed)
