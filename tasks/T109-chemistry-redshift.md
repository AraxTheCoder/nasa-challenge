# T109: C/A: Chemistry maps at a redshift (galaxies)

- **Owner:** Mati  ·  **Status:** done (checked in a browser by Joerg, 2026-11-15)
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
- [x] pipeline/chemistry.py: `z` in compute/combine (shift all wavelengths), file key `<feature>_z<z·10⁴>`, out-of-range error
- [x] combined pictures: one z for all their features
- [x] Live API: `?z=` for chemistry, `GET /api/targets/<id>/redshift` (SIMBAD rvz_redshift of galaxies in the field)
- [x] viewer: "Redshift z" box in the Chemistry list, suggestion from SIMBAD
- [x] check on real galaxies (M100 Br-α, NGC 6240 PAH); tests; CONTRACTS + Decision

## Findings
Real fields built 2026-11-15 (Live API): M100 `c1857287-p158222-s12` (12′), NGC 6240 `c2532454-p024009-s10` (10′).
SIMBAD (basic.rvz_redshift) gave M 100 z = 0.00524 and NGC 6240 z = 0.02472, both at the centre. Maps at z = 0 vs the
catalogue z (rounded 0.0052 / 0.0247), mean grey − 128 over the galaxy (+ = emission; star residuals give ±45 outside):

| Field | Feature | z = 0 | right z | |
|---|---|---|---|---|
| NGC 6240 | PAH 3.29 → 3.371 µm | +43 (star-like pair) | **+94** (clear blob) | window ±0.047, shift 0.081 |
| NGC 6240 | Br-α 4.052 → 4.152 µm | **−22 (looks like absorption)** | **+37** (emission) | the line sits in the red continuum at z = 0 |
| NGC 6240 | Pa-β 1.282 → 1.314 µm | +38 | +10 | inconclusive (dust-dimmed line) |
| M100 | Br-α → 4.073 µm | +21 | +28, arms sharper | shift 0.021 vs window ±0.018 |
| M100 | PAH, Pa-β, Br-γ | ≈ same | ≈ same | shift inside the window, as predicted |

Beyond 5 µm (e.g. CO at z = 0.1 → 5.14 µm): `no_data` with that sentence.

## Questions / needs from others

## Handoff
Chemistry ▾ → "Redshift z" (between the presets and the features). Opening the list asks `/api/targets/<id>/redshift`
once per field; a galaxy at the centre (or covering it) fills z in unless the user typed one; "use" takes another.
Changing z remakes the shown picture at that z (each feature map once per z, cached as `<f>_z<z·10⁴>`).
Code: `pipeline/chemistry.py` (`z_of`, `map_key`, `parse_key`, `galaxy_redshifts`, `compute(..., z=)`),
`server/chemistry.py`, `server/hips.py`, `web/chemistry.js` (`setZ`, `askRedshift`).

## Notes from others
- (Mati, 2026-11-15) Joerg's T112 fixed a miss here: SIMBAD gives `rvz_redshift` to Milky Way objects too (ρ Oph's
  molecular cloud, otype SFR, z 0.028, quality D) and the lookup took it for a galaxy; now galaxy otypes only.
