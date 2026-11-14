# T78: C: Type an exact wavelength: a µm input next to the sky map's band slider (snaps to the nearest of the 102 channels, shows its exact centre) and "frames at λ" in the blink viewer (A/B = the frames nearest that wavelength in two epochs)

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T78-wavelength-input`
- **Depends on / feeds:** T12 (wavelength filter, pairs), T42 (102-band live map), T55 (`app/` redesign)

## Goal
Users can type a wavelength in µm (e.g. 2.17 for Br-γ, 3.05 for water ice, 4.27 for CO₂ ice) and see the sky
or the frames at exactly that wavelength, instead of dragging a slider or hunting for frames.

## Plan
- [x] Sky map: a number input (µm, 0.75–5.0, step 0.001) next to the band slider (`#explore-band`, 102 channels);
      Enter snaps to the nearest channel, slider and input stay in sync, the exact channel centre and width are shown
- [x] Blink viewer: "frames at λ": typing a wavelength picks A and B = the frames nearest that wavelength (at the
      field centre) from the two epochs farthest apart, same detector; says how far off each frame is
      (SPHEREx's LVF means no frame hits it exactly)
- [x] Keyboard-friendly, works on phone width; the URL remembers it (`?lam=2.17`) so links show the same view
- [x] Optional: the T63 feature list as quick picks in the input (Br-γ, H₂O ice, CO₂ ice, …)
- [x] Browser test (7 checks) + Node check `web/tests/lambda_check.mjs`
- [ ] Port to `app/` (Jonathan, T55: the map is the whole page there; the µm box next to its band slider matters most)

## Findings
- Built in `web/` (pure logic `web/lambda.js`, wiring `web/lampick.js` + `setupBand` in `app.js`, one export
  `selectPair` in `viewer.js`). Accepts 2.17, 2,17, "2.17 µm" and 2170 nm.
- Sky map: the µm box replaces the slider's µm readout (the readout now says "ch. 81/102"); checked live:
  `?lam=3.05` → channel 60 at 3.033 µm, 4.27 → channel 81 at 4.257 µm, a typo goes back to the current channel.
- Blink viewer: A/B = closest frame per epoch, preferring the detector of the overall closest frame, then the
  earliest and latest epoch; epochs whose closest frame is > 0.25 µm off are skipped. Note says each frame's
  offset and whether the pair is a fair (matched) comparison. Re-applied after every re-show of the field
  (labels or known objects arriving reset A/B otherwise).
Mati's request, 2026-11-14. Today: the map's band control is a 102-step range slider (`web/app.js` setupBand);
the blink viewer has min/max filter inputs (`#lam-min`/`#lam-max`, T12) but no "show me X µm".

## Questions / needs from others
- [to Jonathan] Which UI is the submission: `web/` or `app/` (T55)? Then this goes there first.

## Handoff
- In the page: compare row "Frames at [ ] µm" (with feature suggestions: Pa-β, Br-γ, H₂O ice, …), map bar µm box
  next to the Band slider; links keep `?lam=`.
- Jonathan (T55): port the map's µm box (and `lambda.js`) to `app/`.

## Notes from others
