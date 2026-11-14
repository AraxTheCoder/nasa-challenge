# T88: Unusual spectra on the map

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T88-outliers-map`
- **Depends on / feeds:** T86 (spectral outliers + panel), T72 (labels toggle in the map bar), T79 (map click = spectrum)

## Goal
The spectral analysis is hard to use while it lives in a panel 1300 px below the map. Make it a toggle in the
map: switch it on and the field's unusual sources are ringed where they are, click one for the reason.

## Plan
- [x] Toggle "Unusual spectra" in the map bar (next to Labels, added by `web/outliers.js`), remembered per browser
      (`localStorage spherex.outliers`); starts the measurement when the field hasn't been measured, progress in
      the bar ("measuring 120/237…" → "9 ringed"). Mirror checkbox "show on the map" in the panel header
- [x] Rings on the map (orange, size by score, rank number, dark halo), selected one blue; `explore.addDrawHook`
- [x] Click a ring → card on the map: rank + name, score, band chart, reason, caveats, "Spectrum" and "Charts ↓";
      the map's own click opens the spectrum at the same time (T79). Esc / × closes; the card follows pan and zoom
- [x] Linked selection: ring, list row and colour-diagram dot select the same source everywhere

## Findings
- Checked in the browser: RW Aur field 9 rings, card + panel follow each other, remembered after reload; RA 181
  Dec +0.5 (never measured) measured by itself in 30 s after switching on, 11 rings. No page errors, no phone overflow.
- `globalThis.spherexOutliers.placed()` lists the drawn rings (screen px in #sky), for tests / the console.
- [to Jonathan] nothing in explore.js / sky.js changed; if `/app/` wants it, the draw hook + card are in outliers.js.

## Notes from others
