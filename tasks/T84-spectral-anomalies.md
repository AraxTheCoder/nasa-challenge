# T84: Spectral anomalies

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T84-spectral-anomalies`
- **Depends on / feeds:** T66/T83 (all-exposure spectra), T49/T63 (spectrum view), T51 (known objects), T75 (HPC)

## Goal
When a point's spectrum changes in a non-continuous way, say so and show where: one exposure jumping out
of its epoch's smooth spectrum, a jump at the same wavelength between epochs, or a change of shape.
Check one-off jumps against known asteroids/comets at that time and place.

## Plan
- [x] `pipeline/anomaly.py`: smooth spectrum per epoch (robust), outliers with significance; epoch-to-epoch
      ratio at matched wavelengths: level change and shape change
- [x] known objects within the aperture at the outlier's time (local MPC catalogue)
- [x] API: `anomalies` in the all-exposure answer; viewer: marked points + plain-words list
- [x] Same code callable per position on the HPC (T75)

## Findings (2026-11-14, real all-exposure spectra)
- **Asteroids passing are found and named**: at 244 Sita's position at its passage (2025-06-11) one burst of
  5 clean exposures reads ~1.85 mJy instead of ~0.1 mJy, at 262 Valda's (2025-09-01) 8 exposures at
  0.93-3.36 um read up to 3.4 mJy instead of ~0.24 mJy; both named from the local MPC catalogue, 0-7" from
  the predicted position. (Also answers T09: known asteroids are where JPL/MPC orbits put them.)
- **Flagged pixels fake everything**: SPHEREx's 6" pixels put about half a star's light into the core
  pixel, so a single flagged (filled) pixel loses ~60 %: 27 of the first 36 "dips" had one. RW Aur's
  "shape change" at 1.55 um came from partly saturated exposures (14-19 % flagged read 35-39 mJy next to
  122 mJy). Now only exposures without any flagged pixel count; RW Aur (8 clean of 237) and R Dra (0 of
  1871) say "can't judge: saturated" instead of "nothing unusual".
- A burst (~4 exposures in ~6 min, 2 detectors) must not be its own reference: an asteroid lifts all of
  them at the same wavelengths (only 1 of Sita's 8 was found before). Spikes of one burst are one event.
- 39 cached positions: 22 spikes, 18 dips, 2 level, 1 shape changes in 14 positions; most single-detector
  spikes are cosmic-ray candidates (said so in the reason).

## Handoff
`pipeline.anomaly.find_anomalies(spectrum)` on any `measure_all` answer (pure numpy + optional catalogue
check); stored with the spectrum, `VERSION` bump re-checks cached ones. HPC (T75): call it per position.
[to Mati] the T63 hints and the light curve now skip exposures of a spike/dip event (web/photometry.js
`steady`); the light-curve axis can still blow up from one faint, noisy point (±10^6 %), worth a clamp.

## Notes from others
