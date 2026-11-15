# T115: C: Bug: the tour's first stop (Barnard's Star) and any explicit field inside a tile built before show the tile field instead (decideSource prefers the tile's field over the asked-for one)

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T115-T117-browser-test`
- **Depends on / feeds:** found by the browser test on real data (Mati: "a thorough app test", 2026-11-15)

## Goal
C: Bug: the tour's first stop (Barnard's Star) and any explicit field inside a tile built before show the tile field instead (decideSource prefers the tile's field over the asked-for one). Fixed and checked again in a browser.

## Plan
- [x] fix (web/app.js decideSource)
- [x] browser check

## Findings
- Cause: `decideSource` (web/app.js) took `autoField.ready.get(key) || explicitHere()`: a field built earlier for
  the tile under the view won over the asked-for field. The default view is Barnard's Star, so its 86′ tile field
  is always built first; the tour's first stop and the Barnard quick pick then showed the 86′ tile field (trace:
  Barnard's target.json at 5.0 s, then the tile field's again, shown last). Stops 2-5 worked (no tile field there).
- Fix: `explicitHere() || autoField.ready.get(key)`, as the comment on explicitHere already meant.
- Browser check: tour stop 1 and the Barnard quick pick open the 15′ field (RA 269.4463, 36 frames) within 1 s and
  keep it; its own epochs blink inside the red outline. Fixture browser test: 0 failures.
- Side effect, harmless: more 404s for the 15′ field's tiles outside its footprint in a 45′ view (HiPS "no tile").

## Handoff
Merged. Re-check: `python web/tests/live_check.py <out>` (real data, needs web/dev.py running).

## Notes from others
