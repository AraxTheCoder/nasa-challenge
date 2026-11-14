# T43: Difference view A − B

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T43-difference` (merged)
- **Depends on / feeds:** T11/T12 (A/B, wavelength-matched pairs), T23 trail view (exclusive with it)
- **From:** official Potential Considerations ("options to add together or subtract images taken at
  different times"); adding is covered by the trail view and shift-and-stack (T23), subtracting was not.

## Goal
One switch shows A − B instead of blinking: grey = unchanged, white = brighter in A, black = brighter in
B. Stars cancel (best for a wavelength-matched pair), anything that moved shows as a white/black pair.

## Plan
- [x] `web/diff.js`: load A and B (CORS), fit B to A's brightness (robust linear fit over valid pixels,
      the display PNGs are stretched per frame), D = A − (a·B + c), grey-centred, auto contrast;
      no-data in either frame stays transparent (hatched)
- [x] Button "A − B" next to Blink + key `D`; stage label + one-line legend; redraw when A/B change
- [x] Exclusive with the trail view (via its checkbox; no change to `trail.js`); overlay stays on top
- [x] Browser test: identical frames → all grey; moving fixture asteroid → a white/black pair

## Findings
- Real Barnard's Star field, default matched pair f004 − f032 (371 d, Δλ 0.008 µm): most stars cancel
  to grey; Barnard's Star shows its proper motion as white (south, A) / dark (north, B) around its
  masked core. Bright stars leave small white/black residual pairs (sub-pixel alignment, PSF changes
  between epochs); the legend says so.
- Masked / no-data pixels showed the stage's dark hatching, which reads as "brighter in B"; they now get
  their own colour (muted blue) and a legend entry.
- Each display PNG is stretched on its own, so B is fitted to A (least squares, then again without
  > 2.5σ outliers) before subtracting; auto contrast from the 99th percentile of |A − B| (floor 6 DN).
- Pixels are read from CORS-loaded copies of the frames (like the T23 inspector); works across ports
  with the Live API (checked in the browser test) and same-origin in offline mode.
- Found on the way: offline mode (`?data=`) showed an empty sky-map box (no tile server); now hidden.

## Questions / needs from others

## Handoff
- Button "A − B" / key `D`. Ends when the trail view is switched on or a blink starts (`viewer:blink`).
- `web/diff.js`: `differenceImage(rgbaA, rgbaB)` is pure (reusable, e.g. for a server-side or
  calibrated version later); `viewer.js` exports `currentPair()` and fires `viewer:blink`.
- Best with a wavelength-matched pair (T12 picker or `M`); with unmatched pairs the legend warns.

## Notes from others
(anyone may append here, dated and signed)
