# T141: Fixes from Mati's bug analysis (ring clicks, blink after a click, Gaia labels, SPHEREx-only vs Gaia)

- **Owner:** Mati  ·  **Status:** review
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
- [x] Rings: the ring handlers take the click (preventDefault + open the spectrum); the map click checks it when its
      timer fires (it runs first, so it can't see it at pointerup).
- [x] explicitHere(): with a click selected (app.analysisFocus), its field counts as here while its centre is in view.
- [x] labels.py: Gaia via VizieR when ESA's TAP fails (same columns, provenance says VizieR); ESA skipped for a while
      after a failure.
- [x] srcfind.py: one Gaia cone (VizieR, proper motion to SPHEREx's date) per field; matched detections are named and
      kept as Gaia stars, only the rest are SPHEREx-only; cache version bumped.
- [x] Light tests only (unit tests with faked network, Node harness); no browser runs.

## Findings
- Server logs today: no 5xx, no tracebacks; the only API 4xx is motion's deliberate "no moving star here" (404).
- Since T138 every map click (📍, Go) builds a field centred there (`focusAnalysis` -> `loadField`); a ring's click
  reached the same handler (photometry.js, registered first on #sky, 280 ms timer): field built at the ring, the
  current field cleared (chemistry picture, Spots list, Unusual spectra list).
- ESA's Gaia TAP (gea.esac.esa.int) doesn't answer from Mati's network (curl: no answer in 10 s; 11 "Gaia
  unavailable" in the logs): 0 Gaia labels in all 8 fields. VizieR's I/355/gaiadr3 (CfA) answers in ~1.2 s with
  the same stars (Barnard's field: 299 stars G < 16, sorted). sky_labels() uses Gaia for the glare filter too.
- T135 on Barnard's Star (14′): 113 "SPHEREx-only" sources, the brightest S/N ~200. Labels only hold Gaia to G 16
  (cap 400), and none here. Re-matched against VizieR Gaia (G < 20.5: 5924 stars over the field, 1.6 s): all 113 are
  Gaia stars (100 kept, the cap), 0 SPHEREx-only.

## Handoff
- **Ring clicks** (web/photometry.js, web/outliers.js, web/chemcands.js): a ring's handler calls `e.preventDefault()`,
  selects its row and opens the spectrum itself (`openSpectrum` without `focusRegion`: no build); the map's click
  checks `e.defaultPrevented` when its 280 ms timer fires. chemcands.js also ignores 📍 picks now (defaultPrevented).
- **Blink after a click** (web/app.js): `explicitHere()` = the view centre on the field (as before) or, while a click
  is selected (`app.analysisFocus`), the field's centre anywhere in view (`centreInView`: within half the smaller
  view side). Helper `fromViewCentre()` shared with `viewOn()`.
- **Gaia labels** (pipeline/labels.py): ESA first; on failure VizieR (`_gaia_vizier`, same columns -> same labels,
  provenance "Gaia DR3 via VizieR I/355/gaiadr3 …" with a note), and ESA isn't asked for `GAIA_TAP_PAUSE_S` (600 s).
- **SPHEREx-only vs Gaia** (pipeline/srcfind.py, VERSION 2): detections stored; `gaia_stars()` = one VizieR cone
  (G < 20.5, 30000 rows max, proper motion to SPHEREx's date); `_classify()`: within 8″ of a Gaia star -> that star
  (id `g…`, `source: "gaia_dr3"`, its name, G and motion; up to 100), else SPHEREx-only (`x…`, up to 150). VizieR
  down -> stored with `gaia_checked: false`; the next measurement redoes only the match (no second pass over the
  images). Stored results of VERSION 1 are found again on the next "Unusual spectra" click.
- CONTRACTS v0.44 documents T135's and these source ids / fields (`g…`, `x…`, `tag`, `catalogues`,
  `catalogues_failed`) and the Gaia-via-VizieR labels.
- Tests: pipeline/test_labels_gaia.py (3, new), pipeline/test_srcfind.py (+2), web/tests/blink_refresh_check.mjs
  (+ clicked-field case). All 12 Node suites; 16 labels, 20 srcfind/fieldspectra/Gaia, 18 outlier/server-related
  Python tests pass. No browser run. Real data: the Barnard re-match above.
- Needs a Live API restart (pipeline/). Fields built before keep their labels without Gaia until rebuilt or their
  labels are asked again.
- **To look at:** on a field with Unusual spectra or a chemistry picture on, click a numbered ring on the map: the
  row is selected and the spectrum opens; the list and picture stay, no "building field". Click a star near the
  screen's edge (a new field builds there): when it's ready its dates blink while its centre is on screen.


## Notes from others
