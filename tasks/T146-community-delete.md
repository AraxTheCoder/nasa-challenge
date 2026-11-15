# T146: Delete community notes (admin)

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T145-T146-build-moderation`
- **Depends on / feeds:** T120 / T129 / T133 (community), T58 (admin token), T14 (deploy)

## Goal
People are already trolling the public discussion (team chat, 2026-11-15). Whoever holds the server's admin token can
delete a comment with its replies; visitors see nothing new.

## Plan
- [ ] `DELETE /api/community/comments/{id}`: admin token only (T58's `SPHEREX_ADMIN_TOKEN`, header `X-Admin-Token`),
      deletes the comment and its replies
- [ ] Viewer: opening the site once with `?admin=<token>` keeps the token in that browser (removed from the address
      bar) and shows "Delete" on every comment
- [ ] CONTRACTS + Decision; tests

## Findings

## Questions / needs from others

## Handoff

## Notes from others
(anyone may append here, dated and signed)
