# T81: Frame viewer features in the map

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T81-map-frames`
- **Depends on / feeds:** T80 (map only), T32 (field layers), T43 (A − B), T12 (λ filter), T45 (play)

## Goal
With the map as the only view (T80), the frame viewer's tools work on the map: show frame A or B, blink, play, A − B, wavelength filter, timeline.

## Plan
- [x] server/hips.py: layers per frame (`f<id>`) and A − B (`d<a>-<b>`, B fitted to A) next to the epoch means
- [x] map overlays: epochs + frames; the viewer's `viewer:frame` / new `viewer:diff` pick the drawn layer
- [x] map-only mode shows the controls again (only the frame image stays hidden)

## Findings
WISE 0855 field (2026-11-14): 3 epoch + 34 frame layers; B, blink and play switch the map's frame layer;
A − B loads `d-f000-f030` (grey = same, white = brighter in A, black = brighter in B). Unmatched default
pair -> many stars differ by wavelength; "Match B to A's λ" (M) gives the fair comparison, as before.

## Questions / needs from others
- [to Jonathan] server/hips.py and web/explore.js are yours: per-frame/difference layers added, epoch layers unchanged.

## Handoff

## Notes from others
