# server/ — Live API (T18, CONTRACTS v0.3)

Builds a target folder on request for any RA/Dec, caches it under `data/targets/<id>/`, and serves
it to the frontend. API spec: `docs/CONTRACTS.md` → "Live API".

```
pip install -r requirements.lock   # from the repo root; exact pinned versions
python -m server                    # live: real SPHEREx data, cache in data/targets/
python -m server --fixture          # tests / offline: the synthetic demo field for every request (own cache)
python -m server --cutouts-remote none   # T57: builds read S3 directly instead of asking the team VM (default)
python -m pytest server -q
```

Try it:

```
curl "http://localhost:8000/api/target?ra=08h55m10.831s&dec=-7d14m42.53s&size=15"
# 202 {"status":"building",...,"poll_url":"/api/jobs/c1337951-m072451-s15"}  -> poll every 2 s
# 200 {"status":"ready","target_url":"/api/targets/c1337951-m072451-s15/target.json"}
```

Notes for other tracks:

- **A:** the server calls `build_target(id, ra, dec, size_arcmin, out_root=<tmp>)` exactly as in
  CONTRACTS. If `build_target` also accepts `progress=callable(step, done=None, total=None,
  message="")`, the server forwards it to the UI's progress bar. Optional, but users wait 1-2 min.
- **B:** `detect.run.detect_target(target)` runs when the viewer asks `GET /api/targets/<id>/objects`
  (T51), in the background; same for catalogue labels via `GET /api/targets/<id>/labels` (T37).
- Also served: photometry (`/api/targets/<id>/photometry`, T49), newer data for a field (`/api/targets/<id>/updates`, T64, `server/updates.py`), per-epoch HiPS (`/api/hips/…`, T32),
  sky-map tiles (`/api/sky/…`, T41/T42), tile settings (`/api/settings`, T47), `/api/health`.
  All in `docs/CONTRACTS.md` → "Live API".
- **C:** fetch `/api/target`, poll `poll_url` while 202, then load `target_url`; frame image paths
  are relative to it. In fixture mode every answer is `"synthetic": true` — show the badge.
- Builds run in a background thread, one per target id; a second request for the same id joins the
  running job. A half-finished build is never served (built in `data/targets/.building/`).
