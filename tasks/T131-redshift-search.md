# T131: Automatic redshift candidates

- **Owner:** Codex (spectra) · **Status:** doing
- **Branch:** `main`
- **Depends on / feeds:** T109, T130

## Goal
Share catalogue redshifts with automatic source matching, estimate missing shifts from already measured spectra, and avoid observed-frame comparisons between differently redshifted galaxies.

## Plan
- [ ] Share the chemistry map catalogue cache and spatially associate individual sources.
- [ ] Fit shifted emission-feature templates plus continuum, refine peaks, report ambiguity and weak evidence.
- [ ] Reuse accepted shifts for chemistry matching and rest-frame galaxy peers.
- [ ] Validate recovery, aliases, noise, stellar exclusions, caching and API/UI.

## Findings
The project has feature-pattern presets rather than empirical spectral-template libraries. Initial estimates will therefore be explicitly experimental emission-feature fits over the currently supported z=0..1 range. Catalogue values take priority. Stellar/brown-dwarf sources stay at rest. No extra exposure downloads.

## Handoff
Pending.

## Notes from others
