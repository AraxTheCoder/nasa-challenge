# web/ (track C)

Static viewer, no build step: plain HTML/CSS and ES modules.

| File | What |
|---|---|
| `index.html`, `style.css` | page and styles |
| `app.js` | page controller: RA/Dec form, page URL, build progress, offline mode |
| `api.js` | Live API client (`docs/CONTRACTS.md` v0.3): request a field, poll, resolve `target_url` |
| `viewer.js` | frame viewer: stacks the frames of one `target.json`, A/B blink, frame table |
| `util.js` | DOM and formatting helpers |
| `presets.json` | the five official test fields (SIMBAD positions moved to epoch 2026.0, with query + timestamp) |
| `dev.py` | one-command launcher: Live API + viewer, opens the browser (`python web/dev.py --help`) |
| `photometry.js` | spectrum + change-at-same-wavelength charts from `/api/targets/<id>/photometry` (T49) |
| `diff.js` | difference view A − B (T43) |
| `warm.py` | pre-builds the five test fields in a Live API cache before a demo (`python web/warm.py --help`) |
| `tests/browser_test.py` | end-to-end browser test against `python -m server --fixture` |

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
  e.g. `?data=../fixtures/targets/`. Add `&target=<id>` to pick a target.

Keys: `Space` blink on/off, `X` flip A/B, `←`/`→` step through frames.

Transparent pixels in a frame are shown hatched as "no data". Synthetic targets get a badge in the
header and a watermark on the image.

## Test

```
python -m pip install -r requirements-dev.lock && playwright install chromium   # once, from the repo root
python web/tests/browser_test.py            # starts the API (:8001) + static server (:8081) itself
```
