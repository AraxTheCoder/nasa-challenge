# server/ — Live API (T18, CONTRACTS v0.3)

Builds a target folder on request for any RA/Dec, caches it under `data/targets/<id>/`, and serves
it to the frontend. API spec: `docs/CONTRACTS.md` → "Live API".

```
pip install -r server/requirements.txt
python -m server --fixture          # until pipeline.build (T02-T04) exists: synthetic fixture only
python -m server                    # live: pipeline.query + pipeline.build (+ detect.run if present)
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
- **B:** `detect.run.detect(target_dir)` runs after the build when the module is importable.
- **C:** fetch `/api/target`, poll `poll_url` while 202, then load `target_url`; frame image paths
  are relative to it. In fixture mode every answer is `"synthetic": true` — show the badge.
- Builds run in a background thread, one per target id; a second request for the same id joins the
  running job. A half-finished build is never served (built in `data/targets/.building/`).
