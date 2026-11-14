# T93: C/A: Chemistry maps: continuum-subtracted feature images for the shown field (ices, PAH, hydrogen lines)

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T93-chemistry-maps`
- **Depends on / feeds:** T49/T66 (cached FITS cutouts + per-pixel wavelength), T43 (difference view), T81 (map layers), T63 (feature list)

## Goal
For the field a user opened, pick a chemical feature (water ice 3.05 µm, CO₂ ice 4.27 µm, CO 4.67 µm, PAH /
methane 3.3 µm, CH₃OH ice 3.53 µm, Pa-β 1.28 µm, Br-γ 2.17 µm, Br-α 4.05 µm, water 1.4 / 1.9 µm) and see an
image of where it absorbs (dark) or emits (bright): the image at the feature's wavelength minus the continuum
interpolated from just below and above, so ordinary stars and smooth spectra cancel. Visualization only
(Decision 2026-11-14): the user looks and judges; nothing is classified.

## Plan
- [x] Server: per field and feature, from the cached SPHEREx cutouts (real fluxes, MJy/sr) and each pixel's own
      wavelength (WCS-WAVE, linear variable filters): on-band = exposures whose wavelength at that pixel lies in
      the feature, continuum = exposures just below and above; per pixel (on − continuum) / continuum, per epoch
      and all epochs; PNG with a symmetric stretch (dark = absorption, bright = emission) + no-data alpha
- [x] API route (new APIRouter, CONTRACTS v0.26 + Decisions line); cached per field + feature
- [x] Viewer (map only; the frame viewer is hidden by default since T80/T90): a "Chemistry" control (feature list from `web/spectrum.js` FEATURES + water 1.4 / 1.9 µm) that shows
      the map as a field layer on the sky map (like A − B, T81) and in the frame viewer; legend and a plain-words
      note (what the feature is, what dark / bright means, limits)
- [x] Check on dusty fields (RW Aur / Taurus, the Orion Nebula); browser test (synthetic field: no selector)
- [ ] Per epoch maps (blink a feature between epochs); frame-viewer view (`?frames=1`)

## Findings
- 2026-11-14: IRSA's all-sky cube (what the map shows) has PNG tiles only, asinh stretch, cut 0–40: invertible
  only approximately, bright stars clipped. So the maps are made from the field's own FITS cutouts instead.
- **Orion Nebula (field c0838300-m053900-s20, 20′, 2026-11-14):** Br-α (4.05 µm) shows M42's ionised gas and
  the round M43 nebula, PAH (3.3 µm) the filaments along the cloud edges, stars cancel; 34–43 exposures per
  map (per pixel 3–4 on the feature, 15–20 around it), 3–6 s with cached cutouts. The saturated core is no data.
- **Water ice (3.05 µm) in Orion traced the PAH filaments** (dark): the continuum above 3.05 µm contained the
  PAH band. Fixed by leaving bright emission features (PAH, hydrogen lines) out of other features' continua;
  the broad PAH plateau (3.2–3.6 µm) still darkens the ice map inside bright nebulae: said in the feature note.
  Excluding *every* feature left rows without any continuum (no-data stripes), so ices stay in.
- RW Aur field: no clear ice signal (not a dense cloud); star residuals as small black/white pairs (on-feature
  and continuum images differ slightly in sharpness), faint stripes from sky-level differences between exposures.
- Zero point: clipped median of the difference (a field a quarter full of emission otherwise turned the
  background dark); noise: clipped MAD.
- T90 (map first screen) blinks by itself; picking a feature takes the map (`map:take` → `setManual(true)`),
  the automatic blink taking it back (another tile) clears the chemistry note (`map:manual`).
- Limits to say in the UI: narrow features (PAH 3.3, Br-α) are about one SPHEREx channel wide, so the contrast is
  diluted; works best on extended emission / absorption (clouds, nebulae), single stars only when strongly odd.

## Questions / needs from others

## Handoff
Pick a field (a nebula works best: Orion RA 83.83 Dec −5.39), then **Chemistry** in the map's view panel. CLI:
`python -m pipeline.chemistry data/targets/<id> <feature>`. Features in `pipeline/chemistry.py FEATURES`.

## Notes from others
