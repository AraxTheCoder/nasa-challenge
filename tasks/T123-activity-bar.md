# T123: One progress bar for everything that runs

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T122-T123-region-progress`

## Goal
The user always knows what is happening: a thin bar at the top of the page with the running processes, the
current step and "n of m" where the Live API says it, "working…" otherwise.

## Plan
- [ ] `web/activity.js`: watches the page's Live API requests (fetch), reads progress from the answers jobs already
      give (`status: building`, `done` / `total`, `progress.message`), names them by route (field build, spectrum,
      unusual spectra, motion, chemistry, quality flags, labels, known objects, map tiles)
- [ ] Determinate bar for a job with a total, moving bar otherwise; hidden when nothing runs
- [ ] Browser check on a fresh field

## Notes from others
