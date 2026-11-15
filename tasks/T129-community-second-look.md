# T129: Community second looks and reliable drafts

- **Owner:** Codex · **Status:** done
- **Branch:** `codex/T129-community`
- **Depends on / feeds:** T120, T92; ideas I25–I27; complements I7

## Goal
Volunteers can request a second look with saved evidence, share a direct discussion link, and find unanswered requests. Drafts survive refreshes, tile/tab changes and failed posts.

## Plan
- [x] Add backwards-compatible SQLite migration, validated post kind/evidence and unanswered feed.
- [x] Preserve per-tile/per-reply drafts and bind asynchronous submissions to their original tile.
- [x] Add second-look composer, saved evidence/share links, unanswered tab and clickable discussed tiles.
- [x] Test API migration/validation/feed behavior and frontend draft/navigation behavior; update contracts and handoff.

## Findings
- Current form is replaced on render, including when view counts arrive; reply state survives tile changes.
- Other agents are editing unrelated files in the main worktree; implementation isolated in /tmp/nasa-community.

## Handoff
- Open 💬 on the map, select **Request a second look**, write an observation and optional title, then Post.
- **Unanswered** lists requests without replies. **Recent** includes clickable most-discussed tiles.
- **Share** copies a link to the exact comment/reply; clipboard-denied browsers show a selectable link.
- **Open saved evidence** loads the cached field and available A/B frames, map wavelength/layer and quality-mask setting. Frame times and observation IDs are checked. Missing/changed evidence is explained; metadata does not preserve cache pixels.
- Drafts persist per tile/reply across tabs/reloads, with memory fallback if browser storage is unavailable. Background counts do not replace the composer. Failed posts retain drafts and submissions stay bound to their original tile.
- Restart the Live API for new routes and the additive SQLite migration. Existing discussions remain intact.
- No identity, moderation or scientific verification roles in this slice. Optional map discussion pins remain I31; follows/outcomes, onboarding and moderation remain I28–I30.

## Validation
- `python -m pytest server/test_community.py -q`: 26 passed (migration, validation, second-look round trips, replies and unanswered filtering).
- All `web/tests/*.mjs`: passed, including new draft/storage/share-link checks.
- `python web/tests/community_browser_test.py`: passed (real SQLite/API + deterministic map/viewer adapters; draft/focus/reload/navigation/failure/in-flight post regressions, plain text, evidence/link/feed/mobile behavior, changed/missing frames, plus real application cached-field loading).
- `python web/tests/browser_test.py /tmp/nasa-community-browser`: 0 failures.
- Full `python -m pytest detect server pipeline tilegen tests -q`: 301 passed, 1 failed. The unrelated `tilegen/test_tilegen.py::test_fresh_checkout_without_index` also fails in isolation on clean main at 858e6b7; reported in TEAM Questions.
- CI now runs the community browser check alongside the existing browser suite.
