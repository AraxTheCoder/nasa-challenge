# T14: Public deploy at https://nasa.jbarkoczi.de/

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T14-docker`
- **Depends on / feeds:** T58 (public limits), T97/T125 (cache sweep), T15 (submission link)

## Goal
The tool answers at https://nasa.jbarkoczi.de/ without login: viewer and Live API on one origin (the viewer then
uses the same origin as API, `web/api.js`), public limits on, caches capped.

## Plan
- [ ] `deploy/docker/`: Dockerfile (Python 3.13 + requirements.lock), compose with `api` (`python -m server
      --public --trust-proxy`) and `web` (nginx: `/` → `/web/`, static `web/` + `fixtures/`, `/api/` → api)
- [ ] published only on the WireGuard address (10.0.0.2), port 8090; data/ bind-mounted (warm caches)
- [ ] AWS nginx server block for Joerg; check end to end through the stack

## Notes from others
