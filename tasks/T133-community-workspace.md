# T133: Community workspace and tile coverage

- **Owner:** Codex (community) · **Status:** doing
- **Branch:** `codex/T133-community-tab`
- **Depends on / feeds:** T120, T129

## Goal
A dedicated Community tab makes discussions available outside the map popup. Classify tile attention from distinct visiting browsers, expose the counts behind the estimate, and help volunteers find less visited sky.

## Plan
- [ ] Add a separate Community workspace, with recent/unanswered discussions, tile thread and map return.
- [ ] Add coverage tiers based on distinct browser identifiers, preserving existing visit totals.
- [ ] Show a coverage overview and optional map layer; explain that attention does not certify scientific completeness.
- [ ] Check navigation/drafts/deep links, API coverage/deduplication, keyboard/mobile behavior; update docs and push.

## Findings
- Views already deduplicate hourly by browser; `seen` has one persistent row per tile/browser, allowing distinct-browser coverage without counting repeat visits as new volunteers.
- Other agents are editing spectral analysis and chemistry; implementation is isolated in /tmp/nasa-community-tab.

## Handoff
In progress.
