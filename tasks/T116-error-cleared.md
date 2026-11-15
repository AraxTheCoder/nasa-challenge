# T116: C: Bug: an error for a link or Go (bad coordinates, failed build) disappears ~2 s later: the automatic tile build's beginLoad clears the messages

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T115-T117-browser-test`
- **Depends on / feeds:** found by the browser test on real data (Mati: "a thorough app test", 2026-11-15)

## Goal
C: Bug: an error for a link or Go (bad coordinates, failed build) disappears ~2 s later: the automatic tile build's beginLoad clears the messages. Fixed and checked again in a browser.

## Plan
- [x] fix (web/app.js beginLoad / loadField)
- [x] browser check

## Findings
- Cause: `beginLoad()` cleared `#messages` for every load, also for the quiet automatic tile build that starts ~2 s
  after the page lands on the default view; `#messages` is hidden when empty, so the user saw nothing.
- Fix: quiet loads leave the messages alone (they report to the blink indicator).
- Browser check: `?ra=abc&dec=xyz` → "Can't use these coordinates: cannot parse "abc"", `?ra=10&dec=100&size=15` →
  "… Dec must be in [-90, 90] deg", both still visible after 8 s.

## Handoff
Merged. Re-check: `python web/tests/live_check.py <out>` (real data, needs web/dev.py running).

## Notes from others
