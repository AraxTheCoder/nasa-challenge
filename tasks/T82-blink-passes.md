# T82: Blink survey passes anywhere on the map

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T81-map-frames`
- **Depends on / feeds:** T42/T47 (live tiles, tilegen), T36 (map)

## Goal
Blink the same patch of sky between SPHEREx's 6-month survey passes anywhere on the map when zoomed in, not only inside a built field.

## Plan
- [x] tilegen: `render(..., pass_=n)` uses only images from that pass
- [x] skycache: layers `spherex-live-p<n>` (orders 6-7; nothing lower: the IRSA cube combines passes)
- [x] map: "Blink passes" when zoomed in to the live orders

## Findings
Pass n = images from 2025-05-01 + (n-1) x 182.6 d (April 2025 commissioning counts as pass 1). One order-6
tile per pass renders locally in 3-4.4 s (~210 KB); the map shows P1/P2/P3 + "Blink passes" at <= 2 deg.
The VM's tilegen does not know passes yet: pass tiles always render in the Live API (`client.get(pass_=...)`).

## Questions / needs from others
- [to Jonathan] tilegen + skycache are yours: the VM needs a redeploy before it can render pass tiles; until then the Live API renders them locally.

## Handoff

## Notes from others
