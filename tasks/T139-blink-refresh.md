# T139: Field blink keeps going when labels / known objects arrive

- **Owner:** Mati  ·  **Status:** review
- **Branch:** `mati/T139-blink-refresh`
- **Depends on / feeds:** T134 (blink checks, Codex), T51 (known objects), T40/T104 (labels), T138 (Codex, same file)

## Goal
A field's epochs keep blinking (and a date click works) after its labels or known asteroids/comets arrive, and the
next pan / zoom no longer swaps the old copy of the field back (which dropped those labels / known objects again).
T134's checks stay as they are.

## Findings
- `setLabels()` and `loadObjects()` (web/app.js) re-fetch target.json and set `app.shownTarget = fresh`, a new object
  for the same field, without telling `autoField.explicit` / `autoField.ready` or the running epoch blink.
- T134's `pick()` (each blink step and a date click) checks the exact object: `app.shownTarget !== target` and
  `explicitHere() === target || autoField.ready.get(fieldKey()) === target`. After the swap every step is refused: the
  blink freezes on one date. That check is right (a timer holds that call's layers and date buttons; any replacement
  must restart it, so a stale timer never blinks images that aren't the view's); the refresh paths skipped the hand-over.
- Older, same cause: `decideSource()` swaps `explicitHere()` (still the old copy) back in on the next view change
  (`ready !== app.shownTarget`): the labels / known objects vanished again after a pan.

## Plan
- [x] `refreshShown(fresh)`: same field (id) -> the fresh copy replaces the old one in app.shownTarget,
      autoField.explicit, autoField.ready and the running blink's field; then publishTarget.
- [x] setLabels / loadObjects use it; pick() compares with the blink's current field (one variable).
- [x] Light checks: Node suites blink_check / field_focus_check (+ a case for this), syntax.

## Handoff
- `web/app.js`: `epochField` = the field object the latest `showEpochLayers` call blinks (set at its start).
  `refreshShown(fresh)`: when `fresh` has the shown field's id (another object), it replaces the old object in
  `app.shownTarget`, `autoField.explicit`, `autoField.ready` and `epochField`, then `publishTarget(fresh)`. The labels
  refresh (`setLabels`) and the known-objects refresh (`loadObjects`) use it instead of setting `app.shownTarget`.
- T134's checks are unchanged in meaning: `pick()` and the two post-await checks compare the exact object, now
  `epochField` instead of the call's `target` (the same object unless refreshShown handed it over). Any other
  replacement (another field, a copy swapped in without the hand-over) still stops the old timer.
- No reload of the epoch tiles: the fresh copy has the same images, the running blink just carries on.
- Tests: `web/tests/blink_refresh_check.mjs` (new; the real app.js with stubbed I/O and timers, like
  field_focus_check): blink goes on after a fresh copy, a view change keeps it (no swap back), an unannounced
  replacement and another field's copy still stop the timer, a fresh copy during the epoch metadata load. It fails
  with the old refresh (checked by removing the hand-over). All 11 Node suites pass, app.js syntax ok. No browser run.
- **To look at:** open a field that isn't built yet (all of them since the cache was cleared), leave Blink on and wait
  until "looking up known asteroids and comets" ends (or turn Labels on): the dates keep blinking and a date click
  works; pan a little: the known objects / labels stay.

## Notes from others
