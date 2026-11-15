# T126: Say what an automatic tile field is

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T126-auto-field-hint`
- **Depends on / feeds:** T55 (automatic tile fields), T122 (Select region)

## Goal
Joerg: "where is the difference in selecting a region and just zooming somewhere?" Zooming builds the map tile's
field for the shown band's detector only (~6 cutouts, to blink); a selected region builds all 6 detectors × 3
passes in the user's framing. The UI didn't say so.

## Plan
- [x] blink line for an automatic field: "Blink: field epochs (this band only) · ▭ Select region to analyse all bands"
- [x] browser check

## Handoff
- `showBlinkStatus` (app.js): epochs of an automatic tile field → "Blink: field epochs, this band only · ▭ Select
  region to analyse all bands"; an asked-for field (link, Select region, tour) keeps "Blink: field epochs".
- Browser: M101 at level 7 shows the new text; the 6′ selected field there shows the old one. browser_test 0 failures.

## Notes from others
