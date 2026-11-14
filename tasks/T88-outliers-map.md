# T88: Unusual spectra on the map

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T88-outliers-map`
- **Depends on / feeds:** T86 (spectral outliers + panel), T72 (labels toggle in the map bar), T79 (map click = spectrum)

## Goal
The spectral analysis is hard to use while it lives in a panel 1300 px below the map. Make it a toggle in the
map: switch it on and the field's unusual sources are ringed where they are, click one for the reason.

## Plan
- [ ] Toggle "Unusual spectra" in the map bar (next to Labels), remembered per browser; starts the measurement
      when the field hasn't been measured (progress in the bar)
- [ ] Rings on the map (orange, size by score, rank number), selected one blue; through `explore.addDrawHook`
- [ ] Click a ring → card on the map: name, reason, caveats, mini chart, "Spectrum" and "Charts" buttons
- [ ] Linked selection with the T86 panel (list, colour diagram)

## Findings

## Notes from others
