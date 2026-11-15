# T102: Field epoch blink runs several times at once

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T102-epoch-blink-race`
- **Depends on / feeds:** T55 / T89 (`showEpochLayers` in web/app.js, Jonathan), T100 (Blink switch, Mati)

## Findings
- 2026-11-15, live site, RW Aur field: `#explore-epochs` holds 18 `.pass-label`s for 3 epochs (6 sets), 6 of them
  marked current; with Blink on, the joined "current" set did not change over 10 s.
- Cause: `showEpochLayers` is async and called from several places (field ready, band / colour change, mode
  change). Each call clears the row and the *last* timer, then awaits; overlapping calls each append their labels
  and `setInterval` their own 800 ms timer; the earlier timers are never cleared and all step `epochShown`.

## Plan
- [x] Call counter `epochCall`: a call overtaken by a newer one stops after each await; the row is replaced (not
      appended to) and the timer cleared right before a new one starts
- [x] Browser check on the live site, RW Aur: 3 labels, one current, steps Sep 2025 → Feb–Mar 2026 → Sep 2026 every
      0.8 s; Blink off stands still; a click on a date shows it; no page errors

## Notes from others
