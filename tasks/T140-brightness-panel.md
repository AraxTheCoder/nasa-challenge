# T140: Clear source brightness analysis

- **Owner:** Codex (brightness) · **Status:** done
- **Branch:** `codex/T140-brightness-panel`
- **Depends on / feeds:** T49, T63, T84, T138

## Goal
Explain what the selected-position brightness measurement shows and make the panel readable: distinguish spectrum from between-epoch brightness comparisons, give each a clear view, and keep advanced interpretation optional.

## Plan
- [x] Explain aperture measurement, spectrum axes and same-wavelength comparisons in plain language.
- [x] Show one readable observing period or period pair at a time, preserving error bars and flags.
- [x] Move model hints, feature overlays and quality details behind optional controls.
- [x] Verify scientific matching/empty states, new interaction, mobile layout and T138 selection retention.

## Findings
- The existing so-called light curve has wavelength, not time, on its horizontal axis; it compares exposure pairs between epochs with wavelengths within half a channel.
- Flux is aperture photometry at the selected position, with local background subtraction. Neighbours and calibration can affect measurements; not an isolated-source or simultaneous full spectrum.
- T138's selected-point/region behavior is already committed; this task preserves its controller logic.

## Handoff
- The panel is **Brightness at this spot**, with two tabs: **Spectrum** and **Changes between visits**.
- Spectrum displays one survey visit at full width, with dates, usable-observation count and a shared brightness scale. Each dot is one exposure, bars are measurement uncertainty where available, crosses are flagged measurements.
- Changes selects one earlier/later visit pair. The horizontal axis is still wavelength; percent change is relative to the earlier exposure. A zero line and median measured difference explain the comparison without claiming variability is established.
- **Overlays and interpretation** holds other visits in grey, the approximate stellar baseline/hints and feature markers (off by default). **Data quality** and **How is brightness measured?** hold diagnostic flags and measurement details. All-flagged, absent, one-visit and unmatched data have explicit explanations.
- All eligible visit pairs are selectable now; the former three-pair cap served the simultaneous colour legend. Wavelength matching keeps the half-narrower-channel criterion, with a tiny numerical tolerance at the boundary. Unknown error estimates remain unknown rather than showing ±0.
- The pipeline, API and T138 loading/point/region controllers are unchanged. Existing point selection, delayed response protection and automatic all-exposure updates remain intact.
- Reload the viewer to use it; no API restart or data migration is needed.

## Validation
- All 12 Node suites passed, including new brightness checks for percent differences, propagated error, missing errors, masked/negative values, closest-wavelength matching, boundary tolerance, date grouping and all six pairs from four visits.
- Extended `web/tests/browser_test.py`: 0 failures. Covers spectrum/visit-pair selection, model/features/grey overlays, keyboard focus and tab navigation, 390 px layout, all-flagged/one-visit/unmatched/unknown-error states. Existing viewer scenarios also run.
- `web/tests/selection_browser_test.py`: passed (crosshair/point/region consistency, refresh retention, rapid-selection races, ignored drag/double-click, pin and Go).
- `web/tests/analysis_browser_test.py`: passed (hover/focus/tap, Escape, mobile popovers and rerender).
- Desktop and phone screenshots inspected under `/tmp/nasa-brightness-browser/`; final captures under `/tmp/nasa-brightness-final-check/`. These checks use labelled synthetic/stubbed data; live SPHEREx data was not remeasured.
