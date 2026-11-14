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
| `trail.js` | trail view: brightest pixel over the frames, movers leave a row of dots (T23) |
| `paths.js`, `paths.css` | names and motion paths on the image, label priority + hover (T22, T34) |
| `inspector.js` | side panel for a clicked object: what it is, how it moves, frame by frame (T23) |
| `objects.js` | objects panel: known / unknown / artifact detections, known objects, synthetic badge (T13) |
| `photometry.js` | spectrum + change-at-same-wavelength charts from `/api/targets/<id>/photometry` (T49) |
| `explore.js`, `sky.js`, `healpix.js` | sky map: own WebGL HiPS renderer, surveys, the field's epochs (T30, T36, T41, T42) |
| `traces.js` | the field's objects drawn on the sky map (T35) |
| `util.js` | DOM and formatting helpers |
| `presets.json` | the five official test fields (SIMBAD positions moved to epoch 2026.0, with query + timestamp) |
| `dev.py` | one-command launcher: Live API + viewer, opens the browser (`python web/dev.py --help`) |
| `warm.py` | pre-builds the five test fields in a Live API cache before a demo (`python web/warm.py --help`) |
| `tests/browser_test.py` | end-to-end browser test against `python -m server --fixture` (also in CI) |
| `tests/*.mjs` | Node checks, e.g. HEALPix geometry against astropy-healpix |

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
