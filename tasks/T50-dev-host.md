# T50: `web/dev.py --host ADDR` (serve on one address only)

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T50-dev-host`
- **Depends on / feeds:** T21 (run kit), T14 (deploy)

## Goal
Run the viewer and the Live API so they are reachable on one network only, e.g. the WireGuard
network 10.0.0.0/24 (`--host 10.0.0.2`), without exposing them on every interface like `--lan`.

## Plan
- [x] `--host ADDR` in `web/dev.py` (overrides `--lan`); health check, printed URL and `--warm` use that address
- [x] README option table
- [x] Verified on Joerg's host: listens on 10.0.0.2:8000/8080 only; ens18 address refuses

## Findings
- The viewer finds the API on port 8000 of the page's host, so no viewer change is needed.
- Live deep-zoom tiles need `data/mirror/index.npz` (`python -m pipeline.mirror harvest`, `build`);
  without it every `/api/sky/spherex-live/...` tile is 502.

## Handoff
`.venv/bin/python web/dev.py --host 10.0.0.2 --no-browser` -> http://10.0.0.2:8080/web/

## Notes from others
