# T95: T90 follow-ups (browser test, field labels)

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T95-t90-followups`
- **Depends on / feeds:** T90 (Jonathan), T46 (CI). Not in scope: missing tiles and the 422 layers (T94, Jonathan)

## Goal
CI green again and the viewer's field object complete after the T90 merge, with the smallest possible changes in
Jonathan's files.

## Plan
- [x] Browser test green again (0 failures). Causes and fixes:
      - two coordinate forms since T90 (`#go-form` on the map, `#field-form` below): the test's `input[name=ra]`
        hit the map's; the test now says `#field-form input[...]`
      - **real bug, not only the test:** with the map off (`?explore=0`, offline `?data=`) the map screen is hidden,
        and with it everything T90 put on it: build progress (`#job`), messages (`#messages`: errors were
        invisible), the quick pick's reason (`#pick-why`), the synthetic badge, the Labels switch.
        `panelsOffMap()` in `web/app.js` moves these under the field form in those two modes (map mode unchanged)
      - `?ra=&dec=` without `size=` only moves the map since T90 (no build, so no "can't reach the API"): the
        test's unreachable-API link now has `size=15`
- [x] `currentTarget().labels` empty: by design. With the Labels switch off (the default now) the viewer shows the
      field with `labels: []` (app.js `showTarget(app.labelsOn ? target : {...target, labels: []})`). No change;
      code that needs labels regardless asks the server (T91's motion box does)

## Findings

## Notes from others
