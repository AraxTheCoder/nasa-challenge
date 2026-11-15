# T141: Fixes from Mati's bug analysis (ring clicks, blink after a click, Gaia labels, SPHEREx-only vs Gaia)

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T141-analysis-fixes`
- **Depends on / feeds:** T138 (click = analysis focus, Codex), T128 (Spots rings), T86/T88/T130 (Unusual spectra rings),
  labels (Codex), T135 (SPHEREx-only sources)

## Goal
1. A click on a numbered ring on the map (chemistry Spots, Unusual spectra) selects its row and opens its spectrum,
   nothing else: no field build at the ring, no cleared picture / lists (since T138 the map's own click did that 280 ms
   later).
2. A field built for a map click (T138 keeps the camera where it is) blinks its epochs while its centre is in view;
   before, it only did when the view centre was within half a field of it, and automatic tile fields are off while a
   click is selected, so only survey passes blinked.
3. Gaia labels when ESA's Gaia TAP doesn't answer (Mati's machine: 0 Gaia labels in all 8 fields, 10 s timeouts):
   the same query from VizieR (I/355/gaiadr3, CfA mirror, answers in ~1 s).
4. T135: a source found in SPHEREx's images is "SPHEREx-only" only if no Gaia star is there either (Barnard's Star's
   field had 113 "SPHEREx-only" sources, some at S/N 200, because the labels had no Gaia stars).

## Plan
- [ ] Rings: the ring handlers take the click (preventDefault + open the spectrum); the map click checks it when its
      timer fires (it runs first, so it can't see it at pointerup).
- [ ] explicitHere(): with a click selected (app.analysisFocus), its field counts as here while its centre is in view.
- [ ] labels.py: Gaia via VizieR when ESA's TAP fails (same columns, provenance says VizieR); ESA skipped for a while
      after a failure.
- [ ] srcfind.py: one Gaia cone (VizieR, proper motion to SPHEREx's date) per field; matched detections are named and
      kept as Gaia stars, only the rest are SPHEREx-only; cache version bumped.
- [ ] Light tests only (unit tests with faked network, Node harness); no browser runs.

## Findings

## Handoff
Pending.

## Notes from others
