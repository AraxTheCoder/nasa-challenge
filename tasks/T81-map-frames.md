# T81: Frame viewer features in the map

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T81-map-frames`
- **Depends on / feeds:** T80 (map only), T32 (field layers), T43 (A − B), T12 (λ filter), T45 (play)

## Goal
With the map as the only view (T80), the frame viewer's tools work on the map: show frame A or B, blink, play, A − B, wavelength filter, timeline.

## Plan
- [ ] server/hips.py: layers per frame (`f<id>`) and A − B (`d<a>-<b>`, B fitted to A) next to the epoch means
- [ ] map overlays: epochs + frames; the viewer's `viewer:frame` / new `viewer:diff` pick the drawn layer
- [ ] map-only mode shows the controls again (only the frame image stays hidden)

## Findings

## Questions / needs from others
- [to Jonathan] server/hips.py and web/explore.js are yours: per-frame/difference layers added, epoch layers unchanged.

## Handoff

## Notes from others
