# T12: Epoch timeline and wavelength filter

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T12-timeline-filter`
- **Depends on / feeds:** T11/T20 (viewer), T17 (`pairs` in target.json, CONTRACTS v0.2)

## Goal
See when each frame was taken and at which wavelength, and blink fair comparisons: frames of
different epochs at (nearly) the same wavelength. Stars change brightness with wavelength
(SPHEREx's filters step ~0.03 µm per exposure), so comparing arbitrary frames shows false changes.

## Plan
- [ ] Timeline strip: one tick per frame placed by time, grouped by epoch, coloured by wavelength;
      shown frame and A/B marked; click a tick to view it
- [ ] Wavelength filter (min/max µm, plus detector-band presets); table, timeline, stepping and A/B
      follow the filter
- [ ] Matched pairs (v0.2 `pairs`): pick a pair → A/B; default A/B prefers a pair when present
- [ ] Keep state in one place in `viewer.js` (one update path for table, timeline, labels) so filters
      and A/B can't disagree
- [ ] Browser test on a generated multi-epoch target (temp folder, offline mode), fixture stays as is

## Findings

## Questions / needs from others

## Handoff

## Notes from others
(anyone may append here, dated and signed)
