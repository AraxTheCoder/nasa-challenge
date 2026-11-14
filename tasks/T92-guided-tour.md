# T92: Guided tour of the official targets

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T92-tour`
- **Depends on / feeds:** T90 (web/ layout), T16 (demo video)

## Goal
A first-time visitor or judge clicks "Tour" and is walked through the five official targets: each stop opens the
field, picks the right layer, starts the blink and shows one sentence of what to watch.

## Plan
- [x] `web/tour.js`: "▶ Tour" on the map (bottom-left on phones) or `?tour=1` in a link; a card (fixed, stays while
      the page scrolls) with intro, the five official targets and "Your turn"; Back / Next / × / Esc
- [x] Each stop opens its field like a shared link (`?ra=&dec=&size=15` + the page's own popstate handling), so it
      builds or opens from cache and blinks by itself; nothing in app.js changed but one import line
- [x] Barnard's Star and eps Ind B: "Measure its speed" opens the spectrum and starts the T91 motion measurement
      directly (`motion.measureNext()`); RW Aur: its spectrum over time

## Findings
- Browser check: all 7 cards, each field opens (cached: at once), Barnard measured from the tour inside the map's
  automatic tile field in ~15 s (10.41 ± 0.14″/yr), whole tour 53 s, no page errors, no phone overflow.
- Text is one or two sentences per stop, in plain words; claims match what the tool shows (R Dra: "too bright,
  the tool says so"; WISE 0855: "slide the band towards 4.5 µm", no measured motion claimed).

## Notes from others
