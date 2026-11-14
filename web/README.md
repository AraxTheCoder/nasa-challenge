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
| `tests/browser_test.py` | end-to-end browser test against `python -m server --fixture` |

## Run locally

Two processes, from the repo root:

```
pip install -r server/requirements.txt      # once
python -m server --fixture                  # Live API on :8000 (synthetic fixture until pipeline.build exists)
python3 -m http.server 8080                 # serves the viewer; NOT on 8000, that's the API
```

Open <http://localhost:8080/web/>, type RA/Dec or pick a test field. Links work too:
<http://localhost:8080/web/?ra=08h55m10.831s&dec=-7d14m42.53s&size=15>

URL parameters:

- `?ra=&dec=&size=` request that field on load. RA/Dec decimal degrees or sexagesimal, size 5–60′.
- `?api=<url>` Live API address (default `http://localhost:8000`, constant `DEFAULT_API` in `api.js`).
- `?data=<folder>` offline mode: read a static targets folder with `index.json`, no server needed,
  e.g. `?data=../fixtures/targets/`. Add `&target=<id>` to pick a target.

Keys: `Space` blink on/off, `X` flip A/B, `←`/`→` step through frames.

Transparent pixels in a frame are shown hatched as "no data". Synthetic targets get a badge in the
header and a watermark on the image.

## Test

```
pip install playwright fastapi uvicorn && playwright install chromium   # once
python web/tests/browser_test.py            # starts the API (:8001) + static server (:8081) itself
```
