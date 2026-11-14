# T48: Cached overview beneath deep-zoom tiles

- **Owner:** Joerg · **Status:** done
- **Branch:** `joerg/T48-map-overview-fallback`
- **Depends on / feeds:** T36/T41/T42; user explicitly approved fixing and pushing this renderer change.

## Goal
Show cached Allsky imagery at deep zoom while detailed tiles load or fail, then progressively draw sharper imagery above it.

## Plan
- [x] Draw the selected band overview under deep-zoom base tiles with correct atlas coordinates.
- [x] Verify pending/failed detail and progressive replacement offline.
- [x] Run existing checks, merge and push.

## Findings
- Existing renderer only draws Allsky at orders <= 3; deep views request only their immediate parent.
- Live tile endpoint returns HTTP 502 with `[Errno 2] No such file or directory: 'data/mirror/index.npz'` on this machine. This is a missing local prerequisite, not evidence of S3 network failure.

## Questions / needs from others

## Handoff
- Base-layer Allsky now draws at every zoom. At orders 4-7, the visible detail mesh samples the
  appropriate subrectangle of the order-3 atlas cell; this covers tiny viewports that the original
  coarse Allsky mesh misses. Detail and transparent field overlays draw above it.
- `node web/tests/overview_check.mjs`: offline regression for pending/failed detail, view-centre
  coverage, atlas UV scale, wavelength switching, and progressive sharp replacement. Passes.
- 80 Python tests, projection round trips (324 points), and HEALPix checks (1848 cases) pass.
- Required browser suite attempted; Chromium cannot launch here because macOS denies its Mach
  port registration (`bootstrap_check_in ... Permission denied (1100)`). Visual confirmation remains.
- Reload http://localhost:8080/web/ with Cmd+Shift+R. Open live deep zoom: overview should remain
  visible under pending/failed detail. Sharp live imagery still needs `pipeline.mirror harvest`
  followed by `pipeline.mirror build` on this machine; the entire data/mirror directory is absent.

## Notes from others
