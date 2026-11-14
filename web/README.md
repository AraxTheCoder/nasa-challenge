# web/ (track C)

Static viewer, no build step. It only reads `index.json`, `<id>/target.json` and frame images
(see `docs/CONTRACTS.md`).

## Run locally

From the repo root:

```
python3 -m http.server 8000
```

Open <http://localhost:8000/web/>. The viewer uses `web/targets/` if it has an `index.json` and
otherwise falls back to `fixtures/targets/`. The 404 for `web/targets/index.json` in the console
is that probe.

URL parameters:

- `?data=<folder>` reads targets from another folder (relative to `web/`), e.g. `?data=../data/targets/`
- `?target=<id>` opens that target.

Keys: `Space` blink on/off, `X` flip A/B, `←`/`→` step through frames.

Transparent pixels in a frame are shown hatched as "no data".
