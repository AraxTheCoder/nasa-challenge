# T131: Automatic redshift candidates

- **Owner:** Codex (spectra) · **Status:** done
- **Branch:** `main`
- **Depends on / feeds:** T109, T130

## Goal
Share catalogue redshifts with automatic source matching, estimate missing shifts from already measured spectra, and avoid observed-frame comparisons between differently redshifted galaxies.

## Plan
- [x] Share the chemistry map catalogue cache and spatially associate individual sources.
- [x] Fit shifted emission-feature templates plus continuum, refine peaks, report ambiguity and weak evidence.
- [x] Reuse accepted shifts for chemistry matching and rest-frame galaxy peers.
- [x] Validate recovery, aliases, noise, stellar exclusions, caching and API/UI.

## Findings
The project has feature-pattern presets rather than empirical spectral-template libraries. Initial estimates will therefore be explicitly experimental emission-feature fits over the currently supported z=0..1 range. Catalogue values take priority. Stellar/brown-dwarf sources stay at rest. No extra exposure downloads.

## Handoff
Reload the viewer with the updated API and select a region. Analysis now shows a Redshifts section with catalogue values, experimental estimates and unresolved alternatives; accepted shifts are reused for chemistry profiles. Galaxy shape charts show rest-frame wavelengths. Known stellar/brown-dwarf sources remain unshifted. z>1 and absorption-only galaxy fitting remain outside this initial feature-template experiment.

Validation: 99 targeted/regression tests pass across redshift/profile/field-spectra/chemistry, shared catalogue cache/API, server, variability and limits. JavaScript syntax and diff checks pass. Tests recover injected quasar and starburst shifts and reject noise, single lines, competing peaks, missing coverage and gross template mismatch; they verify catalogue priority, spatial association, stellar exclusion and cache correction.

Read-only smoke tests on locally cached real spectra used no image/network reads: 17 eligible sources took ~0.4 s; a 122-source field took ~2.6–8.2 s across runs under shared-machine load. The final fit-quality gate retained one catalogue value and left the other 121 spectra unresolved (including a rejected tentative fit). These are performance/smoke checks, not independent redshift validation or accuracy/completeness measurements. No browser visual validation performed.

Method references: [SDSS redshift fitting](https://www.sdss4.org/dr16/algorithms/redshifts/) and [SPHEREx instrument wavelength/resolution](https://spherex.caltech.edu/page/instrument). Our implementation uses simplified feature templates and measured bandwidths, not the SDSS template library or a full calibrated SPHEREx spectral response.

## Notes from others
