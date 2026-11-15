# T120: Citizen collaboration per map tile

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T120-community`
- **Depends on / feeds:** the map (T36/T55/T90), HEALPix order-6 tiles (`FIELD_ORDER`), T58 limits, submission (T15)

## Goal
The tool is for citizen scientists (the scope Decision): they should be able to work together. Every tile of the
map can be commented on, shows how often it has been viewed, and has a discussion thread.

## Plan
- [ ] `server/community.py`: SQLite `data/community/community.db`; per tile (order 6, nested pix): views (one per
      browser per tile per hour), comments with replies (one level), author name, text, optional position + field
      of view ("look here"); recent comments across all tiles; most viewed / most discussed tiles
- [ ] Plain text only (no HTML anywhere), lengths limited, posting rate-limited per address
- [ ] `web/community.js`: "💬" button on the map for the tile under the view centre (views + comment count); a
      panel with the thread, a reply per comment, a form (name remembered in the browser), "look here" buttons;
      a "Recent discussions" tab across the sky
- [ ] CONTRACTS + Decisions line; tests; browser check

## Notes from others
