# T25: Default field and "you can change this" hint

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T25-form-defaults` (merged)
- **Depends on / feeds:** T20 (form, presets)

## Goal
The page opens with RA, Dec and field of view already filled in (a good default field) and makes it
obvious that you can change them or pick another test field.

## Plan
- [x] Default = Barnard's Star, marked `"default": true` in `web/presets.json` (one list of fields)
- [x] Prefill the form when the URL has no `?ra=&dec=`; no auto-load (live builds take minutes)
- [x] Hint under the form, clearer labels ("Field of view … arcmin, 5–60"), empty state names the default
- [x] Browser test checks

## Findings
- Barnard's Star as the default: official test field, largest proper motion of any star (10.4″/yr),
  so it is the best first thing to blink once real data is live.
- No auto-load on purpose: in live mode every visit to the bare page would start a build at IRSA.
  Once T05 warms the cache, auto-loading the default would be instant and could be switched on
  (one line in `main()` in `web/app.js`).

## Questions / needs from others

## Handoff
- The default is the entry with `"default": true` in `web/presets.json` (falls back to the first entry).
- `fillDefaults()` in `web/app.js` fills the form when the URL has no `?ra=&dec=`, and again when the
  back button returns to the bare page. Typing other coordinates clears the dropdown and the
  "filled in with …" note (`syncPresetSelect()`).

## Notes from others
(anyone may append here, dated and signed)
