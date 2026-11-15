# T132: Chemistry notes short, details under "More"

- **Owner:** Mati  ·  **Status:** review
- **Branch:** `mati/T132-chemistry-notes`
- **Depends on / feeds:** T93, T96, T107, T127

## Goal
The chemistry note under the map was a paragraph (Mati's screenshot, Brown dwarfs: 11 lines). Now: two visible
lines (what is shown + colour keys, how to read it), the rest under a collapsed "More" (remembered per browser).
Preset and feature texts shortened in the data; no information lost; no "(T127)" in shown text.

## Plan (agreed with Mati 2026-11-15)
- [x] note layout: single map and pictures (line 1 keys, line 2 reading, More: looks for, fooled by, exposures,
      scale, mix warning, tried-on link, picture link)
- [x] PRESETS looks_for / read / caveats and FEATURES "what" shortened
- [x] tests (light only: chemistry + contract tests, JS syntax; no browser)

## Findings

## Handoff
- Visible: line 1 = preset / feature names with colour keys (hover a name for what it is) + "brighter = …";
  line 2 = the preset's `read` (or how to read mixed colours). More: looks for, fooled by, exposures per map,
  colour scale, tried-on link, picture link. Single map: name − continuum + keys, its description; More: counts.
- `localStorage["spherex.chemMore"]` = "1" keeps More open. Feature descriptions are taken from the features list,
  not from the cached map JSON (old long texts stay in those files, unused by the note).
- Not seen in a browser yet.

## Notes from others
