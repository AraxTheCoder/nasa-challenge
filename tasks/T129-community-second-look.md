# T129: Community second looks and reliable drafts

- **Owner:** Codex · **Status:** doing
- **Branch:** `codex/T129-community`
- **Depends on / feeds:** T120, T92; ideas I25–I27; complements I7

## Goal
Volunteers can request a second look with saved evidence, share a direct discussion link, and find unanswered requests. Drafts survive refreshes, tile/tab changes and failed posts.

## Plan
- [ ] Add backwards-compatible SQLite migration, validated post kind/evidence and unanswered feed.
- [ ] Preserve per-tile/per-reply drafts and bind asynchronous submissions to their original tile.
- [ ] Add second-look composer, saved evidence/share links, unanswered tab and clickable discussed tiles.
- [ ] Test API migration/validation/feed behavior and frontend draft/navigation behavior; update contracts and handoff.

## Findings
- Current form is replaced on render, including when view counts arrive; reply state survives tile changes.
- Other agents are editing unrelated files in the main worktree; implementation isolated in /tmp/nasa-community.

## Handoff
Implementation in progress. No identity, moderation or scientific verification roles in this slice.
