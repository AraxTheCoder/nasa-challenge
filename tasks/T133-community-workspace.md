# T133: Community workspace and tile coverage

- **Owner:** Codex (community) · **Status:** done
- **Branch:** `codex/T133-community-tab`
- **Depends on / feeds:** T120, T129

## Goal
A dedicated Community tab makes discussions available outside the map popup. Classify tile attention from distinct visiting browsers, expose the counts behind the estimate, and help volunteers find less visited sky.

## Plan
- [x] Add a separate Community workspace, with recent/unanswered discussions, tile thread and map return.
- [x] Add coverage tiers based on distinct browser identifiers, preserving existing visit totals.
- [x] Show a coverage overview and optional map layer; explain that attention does not certify scientific completeness.
- [x] Check navigation/drafts/deep links, API coverage/deduplication, keyboard/mobile behavior; update docs and push.

## Findings
- Views already deduplicate hourly by browser; `seen` has one persistent row per tile/browser, allowing distinct-browser coverage without counting repeat visits as new volunteers.
- Other agents are editing spectral analysis and chemistry; implementation is isolated in /tmp/nasa-community-tab.

## Handoff
- **Explore / Community** in the fixed header switches between the mounted explorer and a full-width discussion workspace. Community has Recent, Unanswered, Coverage and This tile; it works even without waiting for the map. `?view=community` opens it directly; new comment share links include that parameter.
- **Coverage** shows four all-sky summary cards and least/most-visited tile lists. Each tile can be discussed or opened on the map. Tile discussion headers show the tier and distinct-browser count.
- **Community coverage** in the map controls colours order-6 tiles (view up to 8°, at most 200 IDs per request); wider views show a zoom hint. Toggle-off, API errors and navigation clear stale overlays.
- Tiers: 0 unvisited, 1–2 light, 3–9 some, 10+ high attention. These are transparent heuristic counts of browser IDs; they do not establish the probability of completeness or a count of verified individuals. Repeat hourly visits keep their old visit totals without increasing the distinct-browser count. No identity or review-completion claim added.
- Returning to Explore preserves the loaded field and per-tile/reply drafts. Keyboard tab navigation and browser Back/Forward preserve explorer state. Community browsing and hidden browser tabs do not accrue map visits.
- Restart the Live API for the new coverage endpoint/response metadata, then reload the viewer. Existing `seen` data supplies the counts; no database rebuild or new schema is needed.
- Synced with T131/T132 changes during implementation; T133 uses CONTRACTS v0.43 after preserving T131's v0.42.

## Validation
- `python -m pytest server/test_community.py tests -q`: 34 passed, including coverage thresholds, browser deduplication across 12 hourly returns, all-sky summary totals, least/most ordering, bounds and input validation.
- All Node checks `web/tests/*.mjs`: passed, including dedicated workspace share links.
- `python web/tests/community_browser_test.py`: passed; exercises real community API + drafts and navigation, Community tabs/history/direct links, real-app cached field preservation, mobile layout, coverage canvas painting/toggle/zoom and map return, and suppressed map counts while Community is visible.
- Existing viewer `browser_test.py`: 0 failures after navigation changes.
- Mobile screenshots inspected at `/tmp/nasa-community-tab-shots-final/`; tests use temporary output by default and can take an output folder argument.
