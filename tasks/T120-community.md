# T120: Citizen collaboration per map tile

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T120-community`
- **Depends on / feeds:** the map (T36/T55/T90), HEALPix order-6 tiles (`FIELD_ORDER`), T58 limits, submission (T15)

## Goal
The tool is for citizen scientists (the scope Decision): they should be able to work together. Every tile of the
map can be commented on, shows how often it has been viewed, and has a discussion thread.

## Plan
- [x] `server/community.py`: SQLite `data/community/community.db`; per tile (order 6, nested pix): views (one per
      browser per tile per hour), comments with replies (one level), author name, text, optional position + field
      of view ("look here"); recent comments across all tiles; most viewed / most discussed tiles
- [x] Plain text only (no HTML anywhere), lengths limited, posting rate-limited per address
- [x] `web/community.js`: "💬" button on the map for the tile under the view centre (views + comment count); a
      panel with the thread, a reply per comment, a form (name remembered in the browser), "look here" buttons;
      a "Recent discussions" tab across the sky
- [x] CONTRACTS + Decisions line; tests; browser check

## Findings
- Browser check (test Live API, desktop + phone): button "💬 0 · 👁 1" after resting on WISE 0855's tile (40905);
  a comment and a reply posted, reply nested, "📍 look here" on both, the button then "💬 2 · 👁 1"; Recent tab lists
  both; `<b>` in a comment shown as text; no page errors, no phone overflow. Test comments deleted afterwards.

## Notes from others
- 2026-11-15 [Mati (Claude)] T146 in your community code (asked by Mati after trolling on the public site): posting closed by default (`POSTING_OPEN`, env `SPHEREX_COMMUNITY_POSTING=open` reopens), `posting_closed` in tile answers, existing comments deleted once per database after a backup (`_clear_once`); viewer: muted form + toast. Details in tasks/T146.
