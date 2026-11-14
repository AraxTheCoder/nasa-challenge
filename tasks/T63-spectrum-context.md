# T63: C/A: Spectrum context: what a normal source looks like, and why a deviation is interesting (expected baseline + feature markers on the T49 chart)

- **Owner:** –  ·  **Status:** open
- **Branch:** –
- **Depends on / feeds:** T49

## Goal
When a spectrum looks unusual, the viewer says how it differs from what we expect and why that is interesting. To spot an anomaly we first need a baseline of normal.

## Plan
- [ ] Baseline: a simple expected spectrum for the source (stellar / blackbody fit to its own short-wavelength points, or from Gaia / 2MASS colours)
- [ ] Mark points that deviate beyond their errors (infrared excess, absorption dips)
- [ ] Feature markers that explain what a deviation at that wavelength could mean: H₂O ice 3.05, PAH 3.3, CH₃OH ice ~3.5, CO₂ ice 4.27, CO ice 4.67 µm; Pa-β 1.28, Br-γ 2.17, Br-α 4.05 µm; dust (rising red continuum)
- [ ] Plain-words note per flagged deviation ("more light at 3–5 µm than a star this colour should give: warm dust?"), clearly marked as a hint, not a result
- [ ] Toggle; browser test

## Findings
From idea I8 in TEAM.md (moved to the Board by Mati, 2026-11-14). Rephrased from idea I8 (feature markers) by Mati: know what normal looks like, then explain anomalies. C `web/photometry.js` + maybe a small fit in `pipeline/photometry.py`.

## Questions / needs from others

## Handoff

## Notes from others
