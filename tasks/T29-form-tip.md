# T29: RA/Dec help as a popup bubble (off for now)

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T29-form-tip` (merged)
- **Depends on / feeds:** T25 (form hint); T16 (demo: switch it on)

## Goal
The "how to enter RA/Dec / field of view" help appears as a bubble under the inputs (like the
browser's "Please fill out this field." popup) instead of a permanent line under the form. Built but
switched off for now so it doesn't get in the way while testing; easy to switch on for the demo.

## Plan
- [x] Bubble anchored under RA with an arrow; text: formats, 5–60 arcmin, test fields; "Got it"
- [x] Shows on the start page and on focus of RA/Dec; closes on Got it (remembered), Escape, Show
- [x] Switch `FORM_TIP_ENABLED = false` in `web/app.js`; `?tip=1` previews it, `?tip=0` forces off
- [x] Remove the inline hint line (T25); keep tooltips and the empty-state text
- [x] Browser test checks (off by default, on with `?tip=1`, dismissal remembered)

## Findings
- Positioning: on a one-row form (desktop) the bubble sits under RA with its arrow on RA. When the
  form stacks (phone), a bubble under RA covered the Dec input, so it goes under the whole form there
  (browser test checks that no input is covered).
- "Got it" is remembered in localStorage (`spherex-blink.formTipDismissed`); Escape, Show and picking a
  test field only close it for now. Clear it with `localStorage.clear()` in the browser console.
- The form's `aria-describedby` points at the bubble text, so screen readers get the help even while
  the bubble is switched off.

## Questions / needs from others

## Handoff
- **Switch on for the demo (T16):** `FORM_TIP_ENABLED = true` at the top of `web/app.js`.
  Preview without changing code: add `?tip=1` to the page URL (`?tip=0` forces it off).
- Code: `showTip()` / `placeTip()` / `hideTip()` in `web/app.js`, markup `#form-tip` in `index.html`,
  styles `.form-tip*` in `style.css`.

## Notes from others
(anyone may append here, dated and signed)
