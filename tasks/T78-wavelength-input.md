# T78: C: Type an exact wavelength: a µm input next to the sky map's band slider (snaps to the nearest of the 102 channels, shows its exact centre) and "frames at λ" in the blink viewer (A/B = the frames nearest that wavelength in two epochs)

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T78-wavelength-input`
- **Depends on / feeds:** T12 (wavelength filter, pairs), T42 (102-band live map), T55 (`app/` redesign)

## Goal
Users can type a wavelength in µm (e.g. 2.17 for Br-γ, 3.05 for water ice, 4.27 for CO₂ ice) and see the sky
or the frames at exactly that wavelength, instead of dragging a slider or hunting for frames.

## Plan
- [ ] Sky map: a number input (µm, 0.75–5.0, step 0.001) next to the band slider (`#explore-band`, 102 channels);
      Enter snaps to the nearest channel, slider and input stay in sync, the exact channel centre and width are shown
- [ ] Blink viewer: "frames at λ": typing a wavelength picks A and B = the frames nearest that wavelength (at the
      field centre) from the two epochs farthest apart, same detector; says how far off each frame is
      (SPHEREx's LVF means no frame hits it exactly)
- [ ] Keyboard-friendly, works on phone width; the URL remembers it (`?lam=2.17`) so links show the same view
- [ ] Optional: the T63 feature list as quick picks in the input (Br-γ, H₂O ice, CO₂ ice, …)
- [ ] Browser test; port to `app/` with Jonathan (T55: the map is the whole page there)

## Findings
Mati's request, 2026-11-14. Today: the map's band control is a 102-step range slider (`web/app.js` setupBand);
the blink viewer has min/max filter inputs (`#lam-min`/`#lam-max`, T12) but no "show me X µm".

## Questions / needs from others
- [to Jonathan] Which UI is the submission: `web/` or `app/` (T55)? Then this goes there first.

## Handoff

## Notes from others
