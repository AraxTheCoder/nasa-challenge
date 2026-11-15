# T109: C/A: Chemistry maps at a redshift (galaxies)

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T109-chemistry-redshift`
- **Depends on / feeds:** T93, T96, T107, T108

## Goal
Asked by Mati (2026-11-15): a chemical feature of a receding object arrives at λ(1 + z), so a map made at the rest
wavelength can miss it. A chemistry map can be made at a redshift z (feature window, continuum and the bright
lines kept out of the continuum all at λ(1 + z)); the viewer suggests z from SIMBAD for galaxies in the field.

How much it matters (window = max(feature half-width, half a SPHEREx channel); R 41 / 35 / 112 / 130 per band):
the feature centre leaves its window at z = 0.0045 (Br-α, cz ≈ 1 300 km/s), ≈ 0.007 (CO₂ ice, CO), ≈ 0.012–0.014
(Pa-β, Br-γ, PAH, CH₃OH), 0.026–0.036 (water). Milky Way objects (|cz| < ~300 km/s) need nothing; galaxies from
the Virgo cluster outwards do. CO leaves SPHEREx's 5 µm at z > 0.07, Br-α at z > 0.23.

## Plan
- [ ] pipeline/chemistry.py: `z` in compute/combine (shift all wavelengths), file key `<feature>_z<z·10⁴>`, out-of-range error
- [ ] combined pictures: one z for all their features
- [ ] Live API: `?z=` for chemistry, `GET /api/targets/<id>/redshift` (SIMBAD rvz_redshift of galaxies in the field)
- [ ] viewer: "Redshift z" box in the Chemistry list, suggestion from SIMBAD
- [ ] check on real galaxies (M100 Br-α, NGC 6240 PAH); tests; CONTRACTS + Decision

## Findings

## Questions / needs from others

## Handoff

## Notes from others
