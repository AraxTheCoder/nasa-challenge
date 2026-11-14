# T84: Spectral anomalies

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T84-spectral-anomalies`
- **Depends on / feeds:** T66/T83 (all-exposure spectra), T49/T63 (spectrum view), T51 (known objects), T75 (HPC)

## Goal
When a point's spectrum changes in a non-continuous way, say so and show where: one exposure jumping out
of its epoch's smooth spectrum, a jump at the same wavelength between epochs, or a change of shape.
Check one-off jumps against known asteroids/comets at that time and place.

## Plan
- [ ] `pipeline/anomaly.py`: smooth spectrum per epoch (robust), outliers with significance; epoch-to-epoch
      ratio at matched wavelengths: level change and shape change
- [ ] known objects within the aperture at the outlier's time (local MPC catalogue)
- [ ] API: `anomalies` in the all-exposure answer; viewer: marked points + plain-words list
- [ ] Same code callable per position on the HPC (T75)

## Findings

## Handoff

## Notes from others
