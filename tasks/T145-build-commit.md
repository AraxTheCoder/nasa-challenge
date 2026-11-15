# T145: The page shows which commit it runs

- **Owner:** Mati  ·  **Status:** review
- **Branch:** `mati/T145-T146-build-moderation`
- **Depends on / feeds:** T14 (deploy at nasa.jbarkoczi.de)

## Goal
The page shows the git commit of the code it runs, linked to GitHub, so anyone can see whether a deployment is up to
date (Jonathan's ask in the team chat, 2026-11-15).

## Plan
- [x] `GET /api/health` adds `commit` (read from the repo's `.git`, no git binary needed; the deploy bind-mounts the
      repo) and `api_commit` (the commit the API process started with)
- [x] Small grey "build 1b889a6" next to the title, linked to the commit; says so when the API still runs older code
- [x] CONTRACTS v0.45 + Decision; tests (`server/test_version.py`: loose / packed refs, detached HEAD, worktree, no repo, health)

## Findings

## Questions / needs from others

## Handoff
- `server/version.py` (`commit()`, `STARTED`), `/api/health` in server/app.py; viewer `web/buildinfo.js`, the link
  `#build-info` inside the title in index.html (hidden below 480 px width). Links to github.com/AraxTheCoder/nasa-challenge.
- Shows "build abc1234 · API def5678" when the checkout was pulled but the API not restarted.

## Notes from others
(anyone may append here, dated and signed)
