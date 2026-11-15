# T142: A map click builds a field only when needed

- **Owner:** Mati  ·  **Status:** review
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
- [x] `reusableField()` + `buildFocus()` queue in web/app.js; `loadField(..., {stillWanted})`.
- [x] Node test with the real app.js (stubbed I/O); T138's browser test reasoned through (exact centring, 5 decimals,
      newest wins) — not run here (no browser runs on Mati's machine without asking).

## Findings
- Planned first: round a new field's centre to a grid (nearby clicks share an id). Dropped: T138's browser test (in CI)
  checks a new field is centred on the click within 1e-5 deg, with 5-decimal coordinates, and it also bends T138's
  intent (centre on what you clicked). Reusing a field built or building for an earlier click gives the same saving
  without moving any centre.
- T138's browser test reasoned through with its fake map (camera 150, 2.2, fov 0.5°): first click (150.125, 2.275) ->
  one request, exact; 151.1 / 151.2 clicks 6′ apart -> both outside a 15′ field's core (3.75′) -> two requests (the
  second waits for the first; the first, overtaken, isn't shown; markedField 151.2); 📍 after testMove at ~(152.03,
  2.35) and Go 153.25 -> far from every earlier field -> new requests. A reused earlier field still sends its request
  (the real server answers from its cache), so the request counts there hold. Not run here (browser).

## Handoff
- web/app.js: `reusableField(ra, dec, size)` -> "shown" (the full field shown has the click within FOCUS_CORE = 1/4 of
  its side of its centre, same size; one-band `…-d<n>` tile fields and synthetic ones don't count) / an earlier click
  field `{req, key}` (last FOCUS_KEEP = 12, same size, click in its core) / null. `focusAnalysis()`: "shown" -> return
  (the caller already opened the point spectrum; region and URL unchanged); an earlier field -> its req (same centre =
  same id); else T138's exact-centred req. `buildFocus(req, key)`: one at a time (`focusBuild.running` / `.next`), a
  waiting click is outlined at once (markField), `loadField(..., {stillWanted})` skips showing a build whose click was
  overtaken (cached on the server), then the waiting one starts if it is still the selection.
- Test: web/tests/click_build_check.mjs (real app.js, stubbed requestField): exact centre, a click 1′ away while
  building (no second field), two far clicks while building (newest next, the middle one never), well inside the
  shown field (no request), 5′ off-centre (new exact field), back near the first click (its field again, after the
  running build), one-band tile field (still builds). Fails with T138's per-click build (checked). All 13 Node files
  pass. T138's selection_browser_test.py not run (browser), reasoned through above; CI runs it.
- Viewer only: a page reload picks it up.
- **To look at:** click a star on a built field near its middle: only the spectrum opens, no "Building field". Click
  four stars around one spot quickly: one field builds, the last click's region next. Click near a spot you clicked
  before: its field comes back at once (cached).


## Notes from others
