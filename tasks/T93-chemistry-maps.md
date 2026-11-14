# T93: C/A: Chemistry maps: continuum-subtracted feature images for the shown field (ices, PAH, hydrogen lines)

- **Owner:** Mati  ·  **Status:** open
- **Branch:** –
- **Depends on / feeds:** T49/T66 (cached FITS cutouts + per-pixel wavelength), T43 (difference view), T81 (map layers), T63 (feature list)

## Goal
For the field a user opened, pick a chemical feature (water ice 3.05 µm, CO₂ ice 4.27 µm, CO 4.67 µm, PAH /
methane 3.3 µm, CH₃OH ice 3.53 µm, Pa-β 1.28 µm, Br-γ 2.17 µm, Br-α 4.05 µm, water 1.4 / 1.9 µm) and see an
image of where it absorbs (dark) or emits (bright): the image at the feature's wavelength minus the continuum
interpolated from just below and above, so ordinary stars and smooth spectra cancel. Visualization only
(Decision 2026-11-14): the user looks and judges; nothing is classified.

## Plan
- [ ] Server: per field and feature, from the cached SPHEREx cutouts (real fluxes, MJy/sr) and each pixel's own
      wavelength (WCS-WAVE, linear variable filters): on-band = exposures whose wavelength at that pixel lies in
      the feature, continuum = exposures just below and above; per pixel (on − continuum) / continuum, per epoch
      and all epochs; PNG with a symmetric stretch (dark = absorption, bright = emission) + no-data alpha
- [ ] API route (new APIRouter, CONTRACTS + Decisions line); cached per field + feature
- [ ] Viewer: a "Chemistry" control (feature list from `web/spectrum.js` FEATURES + water 1.4 / 1.9 µm) that shows
      the map as a field layer on the sky map (like A − B, T81) and in the frame viewer; legend and a plain-words
      note (what the feature is, what dark / bright means, limits)
- [ ] Check on dusty fields (RW Aur / Taurus, a molecular cloud, an HII region); browser test

## Findings
- 2026-11-14: IRSA's all-sky cube (what the map shows) has PNG tiles only, asinh stretch, cut 0–40: invertible
  only approximately, bright stars clipped. So the maps are made from the field's own FITS cutouts instead.
- Limits to say in the UI: narrow features (PAH 3.3, Br-α) are about one SPHEREx channel wide, so the contrast is
  diluted; works best on extended emission / absorption (clouds, nebulae), single stars only when strongly odd.

## Questions / needs from others

## Handoff

## Notes from others
