# T117: C: Bug: on a phone the open Chemistry list runs off the right edge of the screen (words cut off)

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T115-T117-browser-test`
- **Depends on / feeds:** found by the browser test on real data (Mati: "a thorough app test", 2026-11-15)

## Goal
C: Bug: on a phone the open Chemistry list runs off the right edge of the screen (words cut off). Fixed and checked again in a browser.

## Plan
- [x] fix (web/style.css .chem-list)
- [x] browser check

## Findings
- Cause: the list is absolutely positioned under its summary (x ≈ 115 px on a phone) and wider than the rest of the
  screen. A `position: fixed` list does not help: the panel's backdrop-filter makes the panel its containing block
  (it ended 59 px above the screen).
- Fix (≤ 600 px): the open list is in the panel's flow, full width, scrolls itself (max 55vh); texts wrap.
- Browser check at 390 px: list 25-365 px, nothing cut off, page scrollWidth 390; desktop unchanged.

## Handoff
Merged. Re-check: `python web/tests/live_check.py <out>` (real data, needs web/dev.py running).

## Notes from others
