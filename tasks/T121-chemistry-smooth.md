# T121: Chemistry maps smoother (noise speckle, blocky tiles) + errors in the running viewer

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T121-chemistry-smooth`
- **Depends on / feeds:** T93, T96, T108

## Goal
Chemistry maps on the sky map look smooth instead of speckled and blocky: pixel noise softened, map tiles
sampled bilinearly instead of nearest pixel. Works on the maps already cached (no recompute). Plus: errors seen
by Mati in the running viewer fixed.

## Plan
- [ ] NaN-aware Gaussian smoothing of the grey map when it is read (single maps and combined pictures)
- [ ] bilinear sampling of `x-` layers in `server/hips.py` tile rendering
- [ ] tests; restart the viewer (the running API predated T109/T120 routes: 404s on /redshift, /community)

## Findings

## Questions / needs from others

## Handoff

## Notes from others
