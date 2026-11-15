# T104: The chemistry map stays until the user ends it

- **Owner:** Mati  ·  **Status:** done (checked in a browser by Joerg, 2026-11-15)
- **Branch:** `main`
- **Depends on / feeds:** T93 / T96, T100

## Goal
A shown chemistry map goes away only when the user unticks it, picks another view (frames, A − B, a date by
hand) or leaves the field. Never by itself.

## Plan
- [x] A quiet (automatic) field build that finishes while Chemistry holds the map does not open its field
- [x] The same field announced again (labels, known objects, Labels switch) keeps the picture

## Findings
Mati, 2026-11-15: "it deactivates after some time", after T100 fixed the loss on zoom.
- `chemistry.js` dropped its picture on every `viewer:target` event. `app.js` fires it again for the same
  field when its labels or known objects arrive (seconds to minutes after the field opens) and when the Labels
  switch is used.
- A background tile-field build started before the feature was ticked finishes later (tens of seconds to
  minutes) and `loadField` then opened that other field. In Mati's Live API log: the job
  `c2700000-p041815-s86-d1` turns 200, its `target.json`, six frames, outliers, updates follow.

## Questions / needs from others

## Handoff
`web/app.js` `loadField`: `quiet && app.mapTool && app.manualMap` → return without opening (the field is cached
on the server; `autoField.key = null` makes the blink look again once it resumes). `web/chemistry.js`
`viewer:target`: same id → keep `st.shown`, put the layer back on top.
Check: level 7, tick a feature right after arriving on a new tile, leave it for 2–3 minutes: still there.

## Notes from others
(anyone may append here, dated and signed)
