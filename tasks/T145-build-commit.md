# T145: The page shows which commit it runs

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T145-T146-build-moderation`
- **Depends on / feeds:** T14 (deploy at nasa.jbarkoczi.de)

## Goal
The page shows the git commit of the code it runs, linked to GitHub, so anyone can see whether a deployment is up to
date (Jonathan's ask in the team chat, 2026-11-15).

## Plan
- [ ] `GET /api/health` adds `commit` (read from the repo's `.git`, no git binary needed; the deploy bind-mounts the
      repo) and `api_commit` (the commit the API process started with)
- [ ] Small grey "build 1b889a6" next to the title, linked to the commit; says so when the API still runs older code
- [ ] CONTRACTS + Decision; tests

## Findings

## Questions / needs from others

## Handoff

## Notes from others
(anyone may append here, dated and signed)
