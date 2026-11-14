# T75: B: Discovery survey pass 2 (HPC): flag tiles from the pass-1 lists (moved / appeared / changed at matched λ / odd spectrum), then all exposures there at full resolution, forced photometry, spectra, candidates with class + score + reason

- **Owner:** Mati (from Joerg, 2026-11-14 evening; not started there)  ·  **Status:** doing
- **Branch:** `mati/T73-survey-pilot` (T73–T75 together)
- **Depends on / feeds:** T74, T08, T09, T63

## Goal
A ranked candidate list per pilot tile, each with class (brown dwarf / variable / spectral outlier / mover), score and a plain-words reason, and a measured completeness.

## Plan
- [ ] Match pass-1 detections to Gaia (moved to frame time) and CatWISE: static + known out
- [ ] Leftovers: link within an epoch (asteroid tracklets vs. MPC) and across epochs (proper motion)
- [ ] Flagged tiles: all exposures, forced photometry, per-epoch spectra (T63 baseline), variability at matched λ (T12 pairs), T09 recovery check
- [ ] Injection test: fake movers + fake brown dwarfs planted in real images, recovery rate vs. brightness
- [ ] Validation: WISE 0855, Eps Ind B and known T/Y dwarfs in the pilot must come out as candidates

Design of the whole survey (passes, data volumes, candidate classes, open questions): [T73](T73-survey-plan.md).

## Findings

## Questions / needs from others

## Handoff

## Notes from others

- 2026-11-14 Mati (Claude): **outlier method for the scoring step (Mati's approach, to keep in mind):**
  compute the *expected* spectral profile (the peaks and dips of the 0.75–5 µm spectrum) for every source in a
  tile, compare with the measured one, and map where the measurements fall outside the expected range as a
  heatmap: the hot spots are the candidates. Two rules so the heatmap shows the sky and not our model's weak spots:
  1. **Calibrated boundaries.** The expected range per tile comes from the data: how far *ordinary* sources in
     that tile stray from their prediction (robust scatter), not a fixed number. Crowded fields, nebulae,
     galaxies, saturated stars and ghosts, sources fainter than the catalogues and SPHEREx's ~10 % calibration
     would otherwise light up. Score = robust z against that scatter; control positions and injected fakes give
     the false-alarm rate. Heatmap = observed outliers minus expected chance outliers per tile.
  2. **Only consistent outliers count** (millions of sources × 102 channels × epochs = many chance hits): a
     deviation must span several neighbouring channels (T63 already needs ≥ 2), repeat across epochs, or show on
     both detectors that see the sky at the same moment (T09).
  Peaks are judged against a continuum first (T63's baseline); a plain star should show almost none at SPHEREx's
  resolution, so any significant peak or dip is a candidate, and for known types (young star, brown dwarf, Mira,
  galaxy) a missing, extra or (galaxies: redshifted) peak. Sparse spectra miss narrow peaks (PAH 3.3, Br-α are
  ~1 channel wide), so this depends on fuller spectra (T66).
