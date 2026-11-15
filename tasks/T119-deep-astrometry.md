# T119: Measured motion from deep per-epoch stacks

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T119-deep-astrometry`
- **Depends on / feeds:** T91 (measured motion), T85 (cutouts), tour stop 3 (WISE 0855)

## Goal
WISE 0855 (W2 ≈ 14, invisible below ~3 µm) is too faint in one SPHEREx exposure; T91 says "not found". Stack each
epoch's long-wavelength exposures (detectors 5–6, 3.8–5 µm) on one grid, each exposure pointing-corrected with
reference stars first, and fit the star in the deep epoch images.

## Plan
- [x] `_stacked_epochs`: each epoch's detector 5–6 exposures, each pointing-corrected with the reference stars,
      resampled onto one 25 × 25 grid around the star, averaged; Gaussian fit per epoch stack; error = the two
      half-stacks' disagreement (the fit's own error was ~5× too optimistic on stacks)
- [x] Used when the single exposures don't find the star, or find it only weakly (median S/N < 10, whose fits bias
      the motion); `measured_in: "deep stacks"`, per-epoch `stacked` counts; CLI, motion box and tour say so
- [x] Tests: synthetic faint mover recovered within its errors; 8 noise seeds: mean pull +0.18σ, rms 1.27

## Findings
- WISE 0855 (field c1337598-m072422-s15): in the stacks at 11.5 / 19.5 / 20.1σ (9 / 44 / 30 exposures), moving west
  epoch by epoch. **SPHEREx: 7.22 ± 1.02″/yr toward PA 282°; catalogue 8.15″/yr toward 275°: agrees.** Parallax
  (true 0.44″) not significant with these epochs (0.01 ± 0.46″), so no distance claimed.

## Notes from others
