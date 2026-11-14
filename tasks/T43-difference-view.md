# T43: Difference view A − B

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T43-difference`
- **Depends on / feeds:** T11/T12 (A/B, wavelength-matched pairs), T23 trail view (exclusive with it)
- **From:** official Potential Considerations ("options to add together or subtract images taken at
  different times"); adding is covered by the trail view and shift-and-stack (T23), subtracting was not.

## Goal
One switch shows A − B instead of blinking: grey = unchanged, white = brighter in A, black = brighter in
B. Stars cancel (best for a wavelength-matched pair), anything that moved shows as a white/black pair.

## Plan
- [ ] `web/diff.js`: load A and B (CORS), fit B to A's brightness (robust linear fit over valid pixels,
      the display PNGs are stretched per frame), D = A − (a·B + c), grey-centred, auto contrast;
      no-data in either frame stays transparent (hatched)
- [ ] Button "A − B" next to Blink + key `D`; stage label + one-line legend; redraw when A/B change
- [ ] Exclusive with the trail view (via its checkbox; no change to `trail.js`); overlay stays on top
- [ ] Browser test: identical frames → all grey; moving fixture asteroid → a white/black pair

## Findings

## Questions / needs from others

## Handoff

## Notes from others
(anyone may append here, dated and signed)
