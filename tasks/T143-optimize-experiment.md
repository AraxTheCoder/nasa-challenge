# T143: Optimization experiment (branch only)

- **Owner:** Mati  ·  **Status:** doing
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
- [ ] 2 sky.js, 1 explore.js (+ mapframes.js), 3 hips.py (+ chemistry cache), 5 build.py/photometry.py
- [ ] Launcher /home/mateu/nasa/viewer_experiment.py (outside the repo): this branch's code, --cache-gb, arenas
- [ ] Light tests only (unit, Node); Mati tries it in the viewer

## Findings

## Handoff
Pending.

## Notes from others
