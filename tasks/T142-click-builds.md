# T142: A map click builds a field only when needed

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T142-click-builds`
- **Depends on / feeds:** T138 (click = analysis region, Codex), T141

## Goal
Keep T138's rule (a click analyses the clicked place: a field of the chosen size centred on it, old results cleared,
camera kept, automatic tile fields paused, the selection in the URL) without building a field per click:
1. A click well inside (within a quarter of the side of its centre) the full field shown now reuses it: only the
   point spectrum opens. One-band automatic tile fields (`…-d<n>`) don't count: spectra need every band.
2. A click well inside a field built or building for an earlier click this session selects that field again (same
   centre and size = same id = the server's cached field) instead of a new one a few arcsec away.
3. One click-built field at a time: a click while one builds waits (a newer one replaces it); the build that ends after
   the selection moved on stays cached, not shown; then the waiting one starts.

## Why T138 builds a field per click (kept)
Every analysis (Unusual spectra, chemistry, objects, motion) works on a built field; before T138 a click only gave the
point spectrum while all of them still described another field (often a one-band automatic tile field). Centred on
the click so the object sits in the best-covered part; old results cleared; camera kept; tile fields paused so they
can't replace the choice; URL = shareable selection. What it didn't weigh: a field per click on an 8 GB machine (four
nearly identical 14′ fields from four clicks near Barnard's Star), no limit on parallel builds locally, a build the
page stopped waiting for still runs (no cancel on the server).

## Plan
- [ ] `reusableField()` + `buildFocus()` queue in web/app.js; `loadField(..., {stillWanted})`.
- [ ] Node test with the real app.js (stubbed I/O); T138's browser test reasoned through (exact centring, 5 decimals,
      newest wins) — not run here (no browser runs on Mati's machine without asking).

## Findings

## Handoff
Pending.

## Notes from others
