# T12: Epoch timeline and wavelength filter

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T12-timeline-filter` (merged)
- **Depends on / feeds:** T11/T20 (viewer), T17 (`pairs` in target.json, CONTRACTS v0.2)

## Goal
See when each frame was taken and at which wavelength, and blink fair comparisons: frames of
different epochs at (nearly) the same wavelength. Stars change brightness with wavelength
(SPHEREx's filters step ~0.03 µm per exposure), so comparing arbitrary frames shows false changes.

## Plan
- [x] Timeline strip: one tick per frame placed by time, grouped by epoch, coloured by wavelength;
      shown frame and A/B marked; click a tick to view it
- [x] Wavelength filter (min/max µm, plus detector-band presets); table, timeline, stepping and A/B
      follow the filter
- [x] Matched pairs (v0.2 `pairs`): pick a pair → A/B; default A/B prefers a pair when present
- [x] Keep state in one place in `viewer.js` (one update path for table, timeline, labels) so filters
      and A/B can't disagree
- [x] Browser test on a generated multi-epoch target (temp folder, offline mode), fixture stays as is

## Findings
- Timeline form: one panel per epoch (time inside an epoch on x), shared wavelength y axis. A plain
  time axis is useless here: epochs are ~6 months apart, frames inside one are hours to days apart.
  Same height across panels = same wavelength = fair blink. Dots in one neutral colour; colour is
  reserved for A (green), B (orange) and the shown frame (white ring); filtered-out frames dimmed.
- Default A/B: the v0.2 pair with the longest time between its frames (most motion), else the first
  frame and the frame from another epoch closest in wavelength (same detector preferred). Before
  T12, B was "first frame of a later epoch", whatever its wavelength.
- "Wavelength-matched" = in a v0.2 pair, or |Δλ| ≤ 0.5 × bandwidth (same rule as CONTRACTS "Pair"),
  or ≤ 0.05 µm when frames have no `bandwidth_um`. The frame info says so, or warns that stars may
  change brightness.
- Filter UX: typing one bound past the other clears the other (swapping both boxes was confusing).
- Tested on a generated 9-frame, 3-epoch synthetic target (written to `data/test-targets/` by the
  browser test, removed afterwards). Not yet tried on a real live target: `pipeline.build` landed
  while this was in progress.

## Questions / needs from others

## Handoff
- Keys: `M` = match B to A's wavelength (pair partner, else closest λ in another epoch).
- State: `state.filter`, `state.pairs` in `web/viewer.js`; every change ends in `refreshMarks()`,
  which updates stage label, buttons, table, timeline and pair picker. Add new views there.
- `web/timeline.js` is view-only: `renderTimeline(host, frames, {onPick})`, `markTimeline(host, {...})`.
- T22 paths: the `viewer:target` / `viewer:frame` events are kept; `viewer:target` now fires after the
  viewer is visible (so the paths layer can measure the stage).

## Notes from others
(anyone may append here, dated and signed)
