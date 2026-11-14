# T29: RA/Dec help as a popup bubble (off for now)

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T29-form-tip`
- **Depends on / feeds:** T25 (form hint); T16 (demo: switch it on)

## Goal
The "how to enter RA/Dec / field of view" help appears as a bubble under the inputs (like the
browser's "Please fill out this field." popup) instead of a permanent line under the form. Built but
switched off for now so it doesn't get in the way while testing; easy to switch on for the demo.

## Plan
- [ ] Bubble anchored under RA with an arrow; text: formats, 5–60 arcmin, test fields; "Got it"
- [ ] Shows on the start page and on focus of RA/Dec; closes on Got it (remembered), Escape, Show
- [ ] Switch `FORM_TIP_ENABLED = false` in `web/app.js`; `?tip=1` previews it, `?tip=0` forces off
- [ ] Remove the inline hint line (T25); keep tooltips and the empty-state text
- [ ] Browser test checks (off by default, on with `?tip=1`, dismissal remembered)

## Findings

## Questions / needs from others

## Handoff

## Notes from others
(anyone may append here, dated and signed)
