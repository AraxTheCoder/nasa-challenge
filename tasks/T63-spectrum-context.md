# T63: C/A: Spectrum context: what a normal source looks like, and why a deviation is interesting (expected baseline + feature markers on the T49 chart)

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T63-spectrum-context`
- **Depends on / feeds:** T49

## Goal
When a spectrum looks unusual, the viewer says how it differs from what we expect and why that is interesting. To spot an anomaly we first need a baseline of normal.

## Plan
- [x] Baseline: a simple expected spectrum for the source (stellar / blackbody fit to its own short-wavelength points, or from Gaia / 2MASS colours)
- [x] Mark points that deviate beyond their errors (infrared excess, absorption dips)
- [x] Feature markers that explain what a deviation at that wavelength could mean: H₂O ice 3.05, PAH 3.3, CH₃OH ice ~3.5, CO₂ ice 4.27, CO ice 4.67 µm; Pa-β 1.28, Br-γ 2.17, Br-α 4.05 µm; dust (rising red continuum)
- [x] Plain-words note per flagged deviation ("more light at 3–5 µm than a star this colour should give: warm dust?"), clearly marked as a hint, not a result
- [x] Toggle; browser test

## Findings
- Built client-side only (`web/spectrum.js` + drawing in `web/photometry.js`): no contract or server change, no
  effect on page or sky-tile loading (a few KB module; the fit takes < 1 ms after the photometry answer).
- Baseline: blackbody in F_ν fitted per epoch to the good points ≤ 2.5 µm (≥ 3 points over ≥ 0.3 µm),
  1,000–40,000 K grid, analytic scale, 10 % calibration floor in σ (statistical errors are 0.3 % for bright
  stars, channels agree to ~10 %). Reduced χ² > 5 = "doesn't follow one star shape".
- A deviation = ≥ 2 neighbouring points > 3σ and > 30 % above / > 25 % below; merged over epochs; a
  temperature is only named when the epochs agree (variables).
- Real data (Live API, 2026-11-14): RW Aur (young star with a disk): ~3,200–3,600 K baseline, 4.0–4.8 µm
  about 15× above it in epochs 2–3 → "warm dust (disk) or a cooler source", as expected; epoch 1 poor fit
  (variable). Eps Ind B (brown dwarf): no star shape in any epoch, 3.6–4.7 µm ~5× above → cool-atmosphere
  hint. WISE 0855 field centre: plain ~6,500 K (a neighbour dominates the aperture). Barnard's Star: all
  frames saturated, no spectrum.
From idea I8 in TEAM.md (moved to the Board by Mati, 2026-11-14). Rephrased from idea I8 (feature markers) by Mati: know what normal looks like, then explain anomalies. C `web/photometry.js` + maybe a small fit in `pipeline/photometry.py`.

## Questions / needs from others

## Handoff
- Toggles under the spectrum: "Expected + hints" (default on), "Feature markers" (default off).
- Tune in `web/spectrum.js` constants (FIT_MAX_UM, FLOOR, Z_MIN, RATIO_UP/DOWN, POOR_FIT); Node check
  `web/tests/spectrum_check.mjs` covers plain star, warm dust, water ice, single outlier, saturation, variable.
- Jonathan (T55): port `web/spectrum.js`, the photometry.js changes and the `.ph-*` T63 styles to `app/`.

## Notes from others
