# T14: Public deploy at https://nasa.jbarkoczi.de/

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T14-docker`
- **Depends on / feeds:** T58 (public limits), T97/T125 (cache sweep), T15 (submission link)

## Goal
The tool answers at https://nasa.jbarkoczi.de/ without login: viewer and Live API on one origin (the viewer then
uses the same origin as API, `web/api.js`), public limits on, caches capped.

## Plan
- [x] `deploy/docker/`: Dockerfile (Python 3.13 + requirements.lock), compose with `api` (`python -m server
      --public --trust-proxy`) and `web` (nginx: `/` → `/web/`, static `web/` + `fixtures/`, `/api/` → api)
- [x] published only on the WireGuard address (10.0.0.2), port 8090; data/ bind-mounted (warm caches)
- [x] AWS nginx server block for Joerg (`deploy/docker/README.md`); end to end through the stack checked
- [ ] Joerg: certificate + server block on AWS; then check https://nasa.jbarkoczi.de/ from outside

## Findings / handoff
- Stack: `deploy/docker/compose.yaml` (`api` = python:3.13-slim + requirements.lock, runs as uid 1001 so data/ files
  keep their owner; `web` = nginx:1.27-alpine). Code and web/ are bind-mounted from the checkout: a deploy is
  `git pull && docker compose restart api`. Root `.dockerignore` keeps the build context to requirements.lock (data/ is 12 GB).
- `/` and `/?ra=..` redirect (relative, `absolute_redirect off`) to `/web/` with the query, so the submission link
  https://nasa.jbarkoczi.de/ and short shared links work. Only `/web/`, `/fixtures/`, `/api/` are served.
- Checked 2026-11-15 on 10.0.0.2:8090: `/` 302 → `/web/`, `/api/health` 200, `/.env` and `..` paths 404; a new
  8′ field (Pleiades, c0567500-p241200-s8) built through the container API with no 5xx or page errors, files owned by peon.
- The dev servers (web/dev.py :8080, `python -m server` :8000) still run on the same data/; they don't conflict
  for reading, and the community database is shared on purpose. Stop them before the judging if in doubt.
- Gotcha: on a non-default port the viewer looks for the API on :8000 (web/api.js); through the public https URL
  (port 443) it uses the same origin. Testing the stack locally: add `&api=http://10.0.0.2:8090`.

## Notes from others
