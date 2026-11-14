# T48: Cached overview beneath deep-zoom tiles

- **Owner:** Joerg · **Status:** doing
- **Branch:** `joerg/T48-map-overview-fallback`
- **Depends on / feeds:** T36/T41/T42; user explicitly approved fixing and pushing this renderer change.

## Goal
Show cached Allsky imagery at deep zoom while detailed tiles load or fail, then progressively draw sharper imagery above it.

## Plan
- [ ] Draw the selected band overview under deep-zoom base tiles with correct atlas coordinates.
- [ ] Verify pending/failed detail and progressive replacement offline.
- [ ] Run existing checks, merge and push.

## Findings
- Existing renderer only draws Allsky at orders <= 3; deep views request only their immediate parent.
- Live tile endpoint returns HTTP 502 with `[Errno 2] No such file or directory: 'data/mirror/index.npz'` on this machine. This is a missing local prerequisite, not evidence of S3 network failure.

## Questions / needs from others

## Handoff

## Notes from others
