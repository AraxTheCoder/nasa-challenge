# web/ (track C)

Static viewer, no build step: plain HTML/CSS and ES modules.

| File | What |
|---|---|
| `index.html`, `style.css` | page and styles |
| `app.js` | page controller: RA/Dec form, page URL, build progress, offline mode, labels / known objects on request, sky-map wiring |
| `api.js` | Live API client (`docs/CONTRACTS.md` v0.3): request a field, poll, resolve `target_url` |
| `viewer.js` | frame viewer: stacks the frames of one `target.json`, A/B blink, play as video, pairs + wavelength filter, frame table |
| `timeline.js` | epoch timeline: one panel per epoch, y = wavelength (T12) |
| `diff.js` | difference view A − B (T43) |
| `stack.js`, `stackview.js` | stacks (T59): the shown frame's epoch (all detectors) or detector (all epochs) added together, background removed per frame; blinkable; shift-and-stack (T69) along a clicked object or a guessed motion; display only |
| `lambda.js`, `lampick.js` | type an exact wavelength (T78): "Frames at λ" picks A/B closest to it, the map's µm box picks the closest of 102 channels; `?lam=` in links |
| `spectrum.js` | spectrum context (T63): star-like baseline per epoch, points that leave it, plain-words hints, feature list; pure, checked by `tests/spectrum_check.mjs` |
| `trail.js` | trail view: brightest pixel over the frames, movers leave a row of dots (T23) |
| `paths.js`, `paths.css` | names and motion paths on the image, label priority + hover (T22, T34) |
| `inspector.js` | side panel for a clicked object: what it is, how it moves, frame by frame (T23) |
| `objects.js` | objects panel: known / unknown / artifact detections, known objects, synthetic badge (T13) |
| `chemistry.js` | Chemistry (T93): for the shown field, the map of a chemical feature (ices, PAH, hydrogen lines) minus its continuum, as a map layer, with a plain-words note; takes the map from the automatic blink (`map:take`); T96/T108: several ticked at once = one colour picture; T107: presets at the top of the list; T127: presets for objects |
| `chemcands.js` | Spots to check (T128): the spots where the chemistry picture's features show, as a numbered list under its note and rings on the map; a click centres the spot and opens its spectrum |
| `photometry.js`, `brightness.js` | Selected-position brightness (T49/T140): one-visit Spectrum and Changes between visits tabs; dates, matched-wavelength pairs, optional model/features/quality details |
| `explore.js`, `sky.js`, `healpix.js` | sky map: own WebGL HiPS renderer, surveys, the field's epochs (T30, T36, T41, T42) |
| `traces.js` | the field's objects drawn on the sky map (T35) |
| `skylabels.js` | catalogue labels anywhere on the zoomed-in map from `/api/sky-labels` (T72), follows the Labels switch |
| `autoblink.js` | the survey passes blink by themselves from level 6 (T55); dates per pass |
| `hud.js`, `wheel.js` | the floating panels (draggable) and the thumbwheel that scrolls between map and analysis (T124) |
| `mapframes.js` | the frame viewer's tools act on the map (T81): the shown frame / A − B drawn as its layer |
| `flagsmap.js` | "Quality flags" in the map bar (T60): where the field's pixels are unreliable, as a mask |
| `outliers.js` | "Unusual spectra" (T86/T88): sources whose spectral shape stands out, as a panel and rings on the map; T61: "Changes brightness", sources whose flux changes at the same wavelength (dashed V rings) |
| `motion.js` | a catalogued star's motion measured from SPHEREx alone, in the spectrum panel (T91) |
| `community.js`, `community-state.js`, `community-coverage.js` | Tile discussions, second-look requests with saved evidence and share links, unanswered/recent feeds, per-tile/reply browser drafts (T120/T129) |
| `tour.js` | guided tour of the five official targets (T92, `?tour=1`) |
| `util.js` | DOM and formatting helpers |
| `presets.json` | the five official test fields (SIMBAD positions moved to epoch 2026.0, with query + timestamp) |
| `discover.json`, `make_discover.py` | more quick picks (T65): fastest-moving stars + brown dwarfs SPHEREx covers in ≥ 2 epochs, with a reason each; "Surprise me" picks one. Regenerate: `python web/make_discover.py` (needs the local image index) |
| `dev.py` | one-command launcher: Live API + viewer, opens the browser (`python web/dev.py --help`) |
| `warm.py` | pre-builds the five test fields in a Live API cache before a demo (`python web/warm.py --help`) |
| `tests/browser_test.py` | end-to-end browser test against `python -m server --fixture` (also in CI) |
| `tests/live_check.py` | exploratory browser check on real data against the running web/dev.py (10 scenarios, report + screenshots, no asserts; T115–T117) |
| `tests/*.mjs` | Node checks, e.g. HEALPix geometry against astropy-healpix |

## Page layout (T124/T133)

The fixed header has **Explore / Community** tabs. Community opens a full-width discussion workspace with
Recent, Unanswered, Coverage and This tile; `?view=community` links directly to it. It works before the sky map
is ready and keeps the explorer's field and drafts while switching. View tile on map returns to Explore.
Coverage classifies attention by distinct visiting browser IDs: 0 unvisited, 1–2 light, 3–9 some, 10+ high;
repeat hourly visits do not raise the distinct count. These are attention estimates, not certified complete
scientific reviews. Coverage includes a less/most-visited list and an optional **Community coverage** map
checkbox (order-6 tile outlines when zoomed to a view of up to 8°).

The sky map stays behind the whole page; everything floats over it as panels. First screen: the wordmark and
one form (RA, Dec, **Go** = move the map; field size + **Build field** = build that field; test fields,
Surprise me), the view panel (band, False colour, Labels, Unusual spectra, Quality flags, Blink, *More*: base
map, tiles, tile outlines; what blinks; Chemistry), a position readout with N↑ bottom left, Tour and discussion
top right. Blinking starts by itself (`autoblink.js` + `app.js`): from level 6 the survey passes, at level 7
resting on one HiPS order-6 tile builds that tile's field in the background and blinks its epochs.
The mouse wheel over the map zooms, so the page scrolls with the thumbwheel on the right edge (`wheel.js`:
roll over it, drag it, or its arrows) or with the wheel over any panel. Scrolling brings up the analysis
(`#analysis`): the spectrum of a map click, unusual spectra, the field with its frame tools, objects, frames,
provenance. On wide screens (≥ 1280 px) the map's panels stay on the left and the analysis is a column on the
right, so the map stays visible while the frame tools drive it; the ⇤ button under the wheel widens it.
Without the map (`?explore=0`, offline) the same panels sit in an ordinary page (`body.no-map`).

## Brightness at this spot (T140)

The point selected on the map (or a position in the frame viewer) is measured in each exposure by adding
light inside a small aperture and subtracting the local sky background. Nearby objects can contribute;
a moving source can drift through the aperture. Flux is shown in µJy/mJy/Jy; higher means more light.

- **Spectrum** asks where the source is brightest in infrared wavelength. One survey visit is shown at a
  time, with its dates and usable-observation count; the brightness scale is shared across visits. Dots are
  exposures, bars are measurement uncertainty where available, crosses are excluded measurements.
- **Changes between visits** compares an earlier and later exposure at nearly the same wavelength (within
  half of the narrower spectral channel). Choose a visit pair; +50% means 50% brighter in the later exposure.
  Both charts have wavelength on the horizontal axis. This is not a time-axis light curve. The median is
  a summary of the displayed matches, not proof of variability; calibration, motion and blends can contribute.
- Other visits in grey, an approximate stellar baseline, and feature markers are optional under **Overlays
  and interpretation**. Model hints remain tentative. **Data quality** and **How is brightness measured?**
  expand the diagnostic flags and method. Brief-event exposures are marked in the spectrum and omitted
  from the between-visit comparison. Missing error estimates stay unknown instead of becoming zero error.

The previous three-pair colour cap is removed: one pair is displayed at a time, so all eligible visit pairs
can be selected. Background loading, selected-point retention (T138), aperture photometry and the API
are unchanged. The interface explains one-visit, unmatched-wavelength, missing and fully flagged data.

## Run locally

Easiest, from the repo root with the venv active (setup steps: top-level `README.md`):

```
python web/dev.py              # Live API on :8000 + viewer on :8080, opens the browser
```

Or the two parts by hand:

```
python -m server --fixture                       # Live API on :8000
python -m http.server 8080 --bind 127.0.0.1      # viewer; NOT on 8000, that's the API
```

Keep `--bind 127.0.0.1`: without it `http.server` shares the whole repo folder (including `.git` and
any local keys) with everyone on your network. `dev.py` only ever serves `web/` and `fixtures/`.

Open <http://localhost:8080/web/>, type RA/Dec or pick a test field. Links work too:
<http://localhost:8080/web/?ra=08h55m10.831s&dec=-7d14m42.53s&size=15>

URL parameters:

- `?ra=&dec=&size=` request that field on load. RA/Dec decimal degrees or sexagesimal, size 5–60′.
- `?api=<url>` Live API address. Default: port 8000 on the host that served the page (`DEFAULT_API`
  in `api.js`), so it is `localhost` locally and the host's machine for teammates on the LAN.
- `?data=<folder>` offline mode: read a static targets folder with `index.json`, no server needed,
  e.g. `?data=../fixtures/targets/`. Add `&target=<id>` to pick a target: `demo-epochs` has every
  feature (3 epochs, pairs, labels, known / unknown / artifact objects), `demo-synthetic` is minimal.
- `?explore=0` no sky map (embeds, slow connections, tests). `?debug=1` sky-map tile outlines.
- `?view=community` opens the Community workspace (Recent, Unanswered, Coverage and tile discussions).
- `?community=<pix>&comment=<id>` opens and highlights a discussion comment and restores its saved evidence when still cached (T129).
- `?lam=2.17` a wavelength in µm (T78): the blink viewer shows the frames closest to it, the sky map the closest channel.
- `?tip=1` / `?tip=0` force the RA/Dec help bubble on / off (it is switched off by default, T29).

Keys: `Space` blink on/off, `P` play the series, `D` difference A − B, `X` flip A/B, `M` match B to
A's wavelength, `←`/`→` step through frames, `Esc` closes popups and the Measure mode.

Transparent pixels in a frame are shown hatched as "no data". Synthetic targets get a badge in the
header and a watermark on the image.

## Test

```
python -m pip install -r requirements-dev.lock && playwright install chromium   # once, from the repo root
python web/tests/browser_test.py            # starts the API (:8001) + static server (:8081) itself
```

## Map only (T80)

By default the page shows only the explore map: the field's epochs, traces and names appear in it,
and a click anywhere gives that point's spectrum and light curve (T79). The frame viewer (frame image,
blink A/B, A − B, play, wavelength filter, timeline, frame panels) is still in the code: add `?frames=1`
to the URL. Offline folders (`?data=`) and `?explore=0` show it automatically.


Map selection (T138): clicking the map, picking with 📍, Go or a preset selects a point spectrum and a field
centred there, using the form's field size (all bands). Direct clicks preserve the camera; Go centres it.
Old field results clear while the new field loads. The selected point survives label/target refreshes and
panning; automatic tile builds do not replace the selected analysis. A new selection/region replaces it.
Named-source links in existing analysis lists open the point spectrum while keeping their field context.
The Unusual spectra comparison still starts through its own control.
