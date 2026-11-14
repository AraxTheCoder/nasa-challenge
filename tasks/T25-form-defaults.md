# T25: Default field and "you can change this" hint

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T25-form-defaults`
- **Depends on / feeds:** T20 (form, presets)

## Goal
The page opens with RA, Dec and field of view already filled in (a good default field) and makes it
obvious that you can change them or pick another test field.

## Plan
- [ ] Default = Barnard's Star, marked `"default": true` in `web/presets.json` (one list of fields)
- [ ] Prefill the form when the URL has no `?ra=&dec=`; no auto-load (live builds take minutes)
- [ ] Hint under the form, clearer labels ("Field of view … arcmin, 5–60"), empty state names the default
- [ ] Browser test checks

## Findings

## Questions / needs from others

## Handoff

## Notes from others
(anyone may append here, dated and signed)
