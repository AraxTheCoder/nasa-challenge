# T61: B: Appear / disappear / brightness change between epochs, not only motion: sources present in one epoch and not another, or much brighter / fainter

- **Owner:** Mati  ·  **Status:** review (panel not yet seen in a browser)
- **Branch:** `mati/T61-variables`
- **Depends on / feeds:** T06, T49

## Goal
Detection also reports objects that appear, vanish or change brightness between epochs (variables, transients), not only movers.

## Plan
- [x] Appear at one moment, gone otherwise: already T06 (`detect.movers`, unknown "moved on, flared or passed by")
- [x] Flux change at matched wavelength for every catalogue source (T85 field spectra = T49 photometry in every
      exposure), field-calibrated, flag large changes: `detect/variability.py`
- [x] Plain-words `reason`; delivered with the spectral-outliers answer (`variability`, CONTRACTS v0.33), not as
      detections: the field spectra are measured on request, after the build that writes detections
- [x] Viewer: "Changes brightness" list in the unusual-spectra panel (`web/outliers.js`); a name opens its spectrum
      and light curve
- [ ] Mark them on the map (like T88's rings): not done

## Findings
- Method in the module docstring. Pairs per source position (the wavelength changes across a field), same
  detector, Δλ ≤ ½ bandwidth, ≥ 0.5 d apart; offset per exposure pair = field median; amplitude = 90th pct |Δm|.
- Real data (2026-11-15), the two measured 86′ Ophiuchus fields: 34 flagged, 24 catalogued variables (Miras,
  EBs, RR Lyr, LPVs; 28 % of all sources are catalogued variables). Before the blend / extended-source filter it
  was ~50 %: close doubles (STF 2227, BD+04 3520 A/B) and a shell (GSH) changed through the aperture.
- ~0.5 s per field. Only fields whose spectra were measured (press "Find sources with unusual spectra") get it.
- Vanish: a catalogued star that drops below S/N 5 has no pair there, so it shows only as far as its remaining
  pairs change. Not tuned for that.
From idea I6a in TEAM.md (moved to the Board by Mati, 2026-11-14). Needs T06 source extraction.

## Questions / needs from others

## Handoff
To see it: open a field, press "Find sources with unusual spectra" (or open
`?ra=269.2969&dec=4.7802&size=86`, already measured); below the outlier list is "Changes brightness".
CLI: `python -m detect.variability data/targets/<id>`.

## Notes from others
