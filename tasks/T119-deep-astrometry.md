# T119: Measured motion from deep per-epoch stacks

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T119-deep-astrometry`
- **Depends on / feeds:** T91 (measured motion), T85 (cutouts), tour stop 3 (WISE 0855)

## Goal
WISE 0855 (W2 ≈ 14, invisible below ~3 µm) is too faint in one SPHEREx exposure; T91 says "not found". Stack each
epoch's long-wavelength exposures (detectors 5–6, 3.8–5 µm) on one grid, each exposure pointing-corrected with
reference stars first, and fit the star in the deep epoch images.

## Plan
- [ ] Fallback in `measure_motion_uncached` when the singles fail: stack per epoch, fit, same motion / parallax fit
- [ ] Say in the result that it came from stacks (how many exposures per epoch)
- [ ] WISE 0855 on the real field; a test on synthetic faint movers

## Findings

## Notes from others
