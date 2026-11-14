# T91: Measured motion of the official targets

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T91-measured-motion`
- **Depends on / feeds:** T85 (field cutouts of every exposure), T19 (catalogue positions + proper motions), demo / pitch

## Goal
Not just draw a star's catalogue path: measure it from SPHEREx alone. Fit the star's position in every epoch
and turn it into a proper motion with an error bar, next to Gaia's value. "SPHEREx says 10.3″/yr; Gaia 10.4."

## Plan
- [ ] Per epoch: the star's position in each of its exposures (centroid / PSF fit on the cutout, WCS to sky),
      robust mean per epoch with scatter
- [ ] Linear fit over epochs → µα*, µδ, total and direction, with errors; reference: neighbouring field stars
      (their mean shift removes WCS offsets between epochs)
- [ ] Compare with the catalogue (label pm) and say how well they agree
- [ ] API + a line in the inspector / spectrum panel; tests on synthetic cutouts
- [ ] Barnard's Star, Eps Indi B, WISE 0855

## Findings

## Notes from others
