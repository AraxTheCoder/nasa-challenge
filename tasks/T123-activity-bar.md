# T123: One progress bar for everything that runs

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T122-T123-region-progress`

## Goal
The user always knows what is happening: a thin bar at the top of the page with the running processes, the
current step and "n of m" where the Live API says it, "working…" otherwise.

## Plan
- [x] `web/activity.js`: watches the page's Live API requests (fetch), reads progress from the answers jobs already
      give (`status: building`, `done` / `total`, `progress.message`), names them by route (field build, spectrum,
      unusual spectra, motion, chemistry, quality flags, labels, known objects, map tiles)
- [x] Determinate bar for a job with a total, moving bar otherwise; hidden when nothing runs
- [x] Browser check on a fresh field

## Findings / handoff
- `web/activity.js` wraps `window.fetch` (the answer is passed on untouched; a clone is read for progress). Only
  `/api/…` requests that take longer than 350 ms show up, so quick answers never flash the bar.
- Field builds: one entry for `/api/target` + its `/api/jobs/<id>` polls, text from `progress.message` + percent.
  Jobs with `done`/`total` (all-exposure spectrum, unusual spectra, motion, chemistry) fill the bar; others
  (flags, labels, known objects, redshifts, sky labels) show a moving bar. Map tiles: "Map images: n loading".
- A polled job that is not asked for 5 s is dropped; one that answers ready / error / no data ends at once.
- New route? Add a line to `ROUTES` in activity.js. Console: `spherexActivity.jobs()`, `.text()`.
- Respects `prefers-reduced-motion`.

## Notes from others
