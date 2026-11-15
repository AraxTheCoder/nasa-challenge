# T146: Community comments turned off (trolling)

- **Owner:** Mati  ·  **Status:** review
- **Branch:** `mati/T145-T146-build-moderation`
- **Depends on / feeds:** T120 / T129 / T133 (community), T14 (deploy)

## Goal
People trolled the public discussion (team chat, 2026-11-15: "goon spot?" posts, a `<script>` that showed as plain
text). Mati: block adding comments for now, with no admin who has to manage anything, and delete the existing ones.

## Plan
- [x] Server: posting closed by default; `POST /api/community/tiles/<pix>/comments` → 403 "posting is closed for now";
      `SPHEREX_COMMUNITY_POSTING=open` in the server's environment opens it again (read at start)
- [x] Tile answers carry `posting_closed`; the viewer keeps the comment box, Post and Reply visible but muted, and a
      click shows the toast "Comments are turned off for now."
- [x] The comments written so far are deleted once per database on the first start with this code, after a full
      copy is saved as `data/community/community-before-T146-<UTC>.db` (views and coverage stay)
- [x] CONTRACTS v0.45 + Decision; tests (server 98 passed, all 14 Node files)

## Findings
- Dropped on Mati's word: admin "Delete" / "Hide" per comment with `?admin=<token>`; a server-side admin switch.
- The `<script>` post showed as text: the viewer never renders comments as HTML (T120), so nothing ran.

## Questions / needs from others
- [to Joerg] after the merge, `deploy/docker/upgrade.sh` makes it live (pull + API restart). The first start writes
  the backup and deletes the old comments. To allow comments again later: add `SPHEREX_COMMUNITY_POSTING: open`
  to the api service's `environment` in `deploy/docker/compose.yaml` and restart.

## Handoff
- Server: `server/community.py` (`POSTING_OPEN`, `_clear_once`), tests in `server/test_community.py`.
- Viewer: `web/community.js` (`closedForm`, `toast`), style.css `.cm-closed`, `.cm-toast`.
- `web/tests/community_browser_test.py` starts its server with `SPHEREX_COMMUNITY_POSTING=open` (it posts comments).
- Restore old comments if ever wanted: they are in the backup file (same schema), copy rows back by hand.

## Notes from others
(anyone may append here, dated and signed)
