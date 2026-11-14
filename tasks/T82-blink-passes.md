# T82: Blink survey passes anywhere on the map

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T81-map-frames`
- **Depends on / feeds:** T42/T47 (live tiles, tilegen), T36 (map)

## Goal
Blink the same patch of sky between SPHEREx's 6-month survey passes anywhere on the map when zoomed in, not only inside a built field.

## Plan
- [ ] tilegen: `render(..., pass_=n)` uses only images from that pass
- [ ] skycache: layers `spherex-live-p<n>` (orders 6-7; nothing lower: the IRSA cube combines passes)
- [ ] map: "Blink passes" when zoomed in to the live orders

## Findings

## Questions / needs from others
- [to Jonathan] tilegen + skycache are yours: the VM needs a redeploy before it can render pass tiles; until then the Live API renders them locally.

## Handoff

## Notes from others
