# T130: Shared spectral analysis and automatic profile candidates

- **Owner:** Codex (spectra) · **Status:** doing
- **Branch:** `main`
- **Depends on / feeds:** T85/T86, T127; complements T128

## Goal
Reuse measurements and feature evidence for automatic chemistry-profile candidates; compare stellar and extragalactic spectra to separate peers.

## Plan
- [x] Shared raw field spectra for anomaly, variability and chemistry-profile checks.
- [x] Persistent combined analysis cache and chemistry-map reprojection cache.
- [x] Separate stars, galaxies/quasars and unclassified models; sparse groups unjudged.
- [ ] Finish validation and document API behavior.

## Findings
Existing chemistry presets describe feature patterns, not physical spectral templates. Automatic candidates require two signed features with local continuum and epoch agreement. No new images are downloaded for profile matching. Redshift profiles skip objects without known redshifts. T128 searches image spots; this task checks catalogue-source aperture spectra.

## Handoff
Select a region, then inspect the unusual-spectra panel for automatic chemistry candidates. Spectrum links reuse seeded aperture measurements. Full physical template fitting and uncatalogued source discovery are outside this change.

## Notes from others
