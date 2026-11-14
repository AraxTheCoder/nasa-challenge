# T62: B/C: Candidate ranking + a dedicated candidate list in the viewer: motion significance, consistency across frames, catalogue match, artifact probability from FLAGS

- **Owner:** –  ·  **Status:** open
- **Branch:** –
- **Depends on / feeds:** T06, T08, T60

## Goal
The most promising unknown objects are listed first with a clear score, so a user (or judge) sees the candidates without searching.

## Plan
- [ ] Score: motion significance, track consistency, catalogue match, artifact probability from FLAGS bits (extends detect.classify, T08)
- [ ] Viewer: candidate list across the field (and later across fields), sortable, click jumps to the object

## Findings
From idea I6c in TEAM.md (moved to the Board by Mati, 2026-11-14). Partly done: score + reason per detection (T08), unknown first in the objects panel (T13).

## Questions / needs from others

## Handoff

## Notes from others
