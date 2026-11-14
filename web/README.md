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
| `chemistry.js` | Chemistry (T93): for the shown field, the map of a chemical feature (ices, PAH, hydrogen lines) minus its continuum, as a map layer, with a plain-words note; takes the map from the automatic blink (`map:take`) |
| `photometry.js` | spectrum + change-at-same-wavelength charts from `/api/targets/<id>/photometry` (T49) |
| `explore.js`, `sky.js`, `healpix.js` | sky map: own WebGL HiPS renderer, surveys, the field's epochs (T30, T36, T41, T42) |
| `traces.js` | the field's objects drawn on the sky map (T35) |
| `util.js` | DOM and formatting helpers |
| `presets.json` | the five official test fields (SIMBAD positions moved to epoch 2026.0, with query + timestamp) |
| `discover.json`, `make_discover.py` | more quick picks (T65): fastest-moving stars + brown dwarfs SPHEREx covers in ≥ 2 epochs, with a reason each; "Surprise me" picks one. Regenerate: `python web/make_discover.py` (needs the local image index) |
| `dev.py` | one-command launcher: Live API + viewer, opens the browser (`python web/dev.py --help`) |
| `warm.py` | pre-builds the five test fields in a Live API cache before a demo (`python web/warm.py --help`) |
| `tests/browser_test.py` | end-to-end browser test against `python -m server --fixture` (also in CI) |
| `tests/*.mjs` | Node checks, e.g. HEALPix geometry against astropy-healpix |

## Page layout (T90)

One page. The first screen is the T55 map: the sky map fills the window and the controls float over it
(`hud.js`, draggable; `cursorpin.js` for the 📍, `coords.js` for RA/Dec input). "Go" only moves the map.
Blinking starts by itself (`autoblink.js` + `app.js`): from level 6 the survey passes, at level 7 resting on
one HiPS order-6 tile builds that tile's field for the shown band in the background and blinks its epochs;
the band slider (+ typed µm) and "false colour" apply to all of it. Scroll the page (scrollbar on the right;
the mouse wheel over the map zooms) for everything else: map tools (base map, N↑, the T82 pass buttons,
"Blink this spot"), the field form ("Show" builds a field of a chosen size), the frame viewer,
analysis, spectra, objects, frames, provenance. Using the map tools or the frame viewer takes the map over
until the view moves to another tile; the "Blink:" text on the map says what is shown.

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
