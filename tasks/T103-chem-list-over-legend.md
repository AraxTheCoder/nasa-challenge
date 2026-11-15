# T103: Chemistry list hidden under its own legend

- **Owner:** Mati  ·  **Status:** review (not yet seen in a browser)
- **Branch:** `main`
- **Depends on / feeds:** T93 / T96

## Goal
With a chemistry map shown, opening the Chemistry list shows the whole list; the legend below does not cover it.

## Plan
- [x] Lift the map-tools card while the list is open (`web/style.css`)

## Findings
The list (`.chem-list`) is positioned inside the first glass card and has `z-index: 20`, but every `.hud-panel`
is a stacking context of its own, and the legend (`#chem-note`) is a later card, so it painted over the list.

## Questions / needs from others

## Handoff
`.hud-panel:has(.chem-pick[open]) { position: relative; z-index: 30; }`. Check: tick a feature, wait for the
legend, open the list again: all rows and "Clear" must be readable and clickable.

## Notes from others
(anyone may append here, dated and signed)
