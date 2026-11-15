# T134: Late layers and background blink focus

- **Owner:** Codex (map) · **Status:** doing
- **Branch:** `main`

## Goal
Keep late automatic field loads, overlay requests and timers from replacing/blinking imagery that no longer belongs to the active view.

## Findings
- Automatic field builds do not validate the current centre tile/band before publishing their result.
- Pass mode notifies listeners only after awaiting layer metadata, leaving the old field epoch timer alive during the wait.
- Renderer and explore overlay setters commit after awaits without request-generation checks; an old response can replace a newer set or append stale dynamic overlays.
- User described surrounding tiles, still fairly sharp, starting to blink after waiting. These races are reproducible from code; expected survey-pass blink remains supported.

## Plan
- [ ] Cache stale automatic fields without publishing/recentring them.
- [ ] Stop epoch timers immediately and reject stale mode/layer/date completions.
- [ ] Guard renderer/explore overlay generations and dynamic overlay indexes.
- [ ] Deterministic delayed-response regressions and existing Node checks.

## Handoff
Pending.

## Notes from others
