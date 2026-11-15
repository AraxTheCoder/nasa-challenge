# T139: Field blink keeps going when labels / known objects arrive

- **Owner:** Mati  ·  **Status:** doing
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
- [ ] `refreshShown(fresh)`: same field (id) -> the fresh copy replaces the old one in app.shownTarget,
      autoField.explicit, autoField.ready and the running blink's field; then publishTarget.
- [ ] setLabels / loadObjects use it; pick() compares with the blink's current field (one variable).
- [ ] Light checks: Node suites blink_check / field_focus_check (+ a case for this), syntax.

## Handoff
Pending.

## Notes from others
