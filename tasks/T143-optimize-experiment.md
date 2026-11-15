# T143: Optimization experiment (branch only)

- **Owner:** Mati  ·  **Status:** review (experiment branch, not merged)
- **Branch:** `mati/T143-optimize-experiment` (not merged to main until Mati has tried it)
- **Depends on / feeds:** T81/T124 (map layers, Jonathan), T41/T81 server/hips.py, T49/T66 photometry, T125 cache sweep

## Goal
Measured in Mati's server logs and code (2026-11-15), each tried here:
1. Frame layers (f000…f033): 73% of all map requests today (4091 tiles + 848 layer descriptions, 47% of the tiles
   404) were the field's single frames, prefetched as overlays though only the frame tools show them -> load a frame
   layer the first time the frame tools show it (as A − B layers already are).
2. `/api/hips/<field>` was fetched 399 times; each time sky.js `setOverlays` deleted every overlay's tiles and made
   new layers -> all tiles loaded again -> keep layers whose address didn't change.
3. server/hips.py image caches by entry count (256 frames, 64 epoch, …) as float32 though grey 0-255 -> 8-bit
   images, and one memory budget for them (instead of counts).
4. No disk cap on Mati's machine (launcher without --cache-gb; T125's free-space check sees WSL's ~900 GB, not C:)
   -> the experiment launcher runs with --cache-gb.
5. Point spectra: median 14 s, max 87 s, 37 of 39 measured from scratch; cutouts are cached by exact position -> a
   point reuses a stored cutout of the same exposure that covers it.
6. Experiment: MALLOC_ARENA_MAX=2 (glibc keeps per-thread arenas; RSS stayed at 3.8 GB with small fields).

## Plan
- [x] 2 sky.js, 1 explore.js (+ mapframes.js), 3 hips.py (+ chemistry cache), 5 build.py/photometry.py
- [x] Launcher /home/mateu/nasa/viewer_experiment.py (outside the repo): this branch's code, --cache-gb, arenas
- [x] Light tests only (unit, Node); Mati tries it in the viewer

## Findings
- Point spectra from a field's stored cutout vs their own small cutout, real data (Barnard's Star's field, its
  Unusual spectra cutouts): identical flux to the last digit, 6 points (0–6.5′ off the field centre) × 12 exposures.

## Handoff
Commit 695aa53 on `mati/T143-optimize-experiment` (pushed, NOT merged):
1. web/explore.js: `setFieldLayers` keeps the frames in `frameLayers` and gives only the epochs to the renderer;
   `showLayer("f003")` adds a frame the first time (like d-/x- layers). setEpochLayers/setPassLayers/hideEpochs forget them.
2. web/sky.js: `st.pool` (layers by address); `setOverlays` reuses a pooled layer (meta/label updated, a cube's
   slice set to the current band), frees layers that dropped out (`dropUnused`); `addOverlays` layers are pooled too.
   web/tests/blink_check.mjs (T134): the pass-metadata race now first clears the overlays as the page does
   (onBlinkSource -> hideEpochs); otherwise the reused pass layer fetched nothing to delay.
3. server/hips.py: `_BudgetCache` (LRU by bytes, cache_clear/cache_info): one 400 MB budget for frame / epoch /
   colour / A − B / chemistry images, 150 MB for finished tiles (was 8192 tiles); frame, epoch, colour and A − B
   images stored as uint8 (colour sums them as floats). pipeline/chemistry.py `_load_map` 32 -> 8 maps.
4./6. /home/mateu/nasa/viewer_experiment.py (outside the repo): runs this worktree's code with `--cache-gb 6` and
   `MALLOC_ARENA_MAX=2` (re-exec at start), 4 spectrum workers. The worktree's data/ folders link to the main
   checkout's data/ (old worktree copies in data/_worktree_old/). Run it INSTEAD of viewer_lowmem.py, never both.
5. pipeline/photometry.py: `_field_cutout` looks for a stored cutout of the same image made for a built field (field
   centres from the data/targets folder names) whose inscribed circle holds the point + measuring margin.
Tests: web/tests/overlay_pool_check.mjs, server/test_hips_cache.py, pipeline/test_photometry.py (+1); all 14 Node
files, 145 Python tests (server + touched pipeline) pass. No browser run.
**To try:** stop the normal server, start the experiment launcher; check that tiles no longer reload on band /
colour changes, frames still show in the frame tools (first time with a short load), memory (RSS) of the server
under the same use, and point spectra inside an analysed field. Back: stop it, start viewer_lowmem.py.


## Notes from others
