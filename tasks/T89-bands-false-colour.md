# T89: Band switching that works on the map + a false-colour layer

- **Owner:** Jonathan  ·  **Status:** done
- **Branch:** `main` (like T55: `app/` + tilegen/server pieces)
- **Depends on / feeds:** T55 (`/app/`), T82 (pass layers), T32 (field epoch layers), T57 (cutouts)

## Goal
The band slider changes what blinks, for survey passes *and* field epochs, and changing it within one
detector is instant; a "false colour" option shows all bands combined (blue = short, red = long λ), also
while blinking. Field epoch builds get faster by fetching only what the shown band needs.

## Plan
- [x] Live / pass tiles per detector: the image only depends on the detector (`slice // 17`), so ask for one
      canonical slice per detector; the 17 channels of a detector share one cached tile
- [x] Field epochs per band: automatic builds only for the detector of the shown band (~6-8 instead of
      36-44 cutouts); another detector = another (cached) build of the same tile
- [x] False colour for passes: RGB tiles composed from the 6 per-detector grey tiles (cached, reused when
      switching bands); blue D1+D2, green D3+D4, red D5+D6
- [x] False colour for field epochs: all-detector build, RGB epoch layers from per-detector means
- [x] Band control: slider + "false colour" switch; labels say which detector / λ range is shown

## Findings
- 2026-11-14: field epoch layers are the mean of all frames of an epoch over all 6 detectors
  (`server/hips.py`), so the band slider did nothing for them; pass tiles only change at detector
  boundaries (D1 0.75-1.09, D2 1.10-1.62, D3 1.63-2.41, D4 2.42-3.82, D5 3.83-4.41, D6 4.42-5.00 µm):
  SPHEREx's linear variable filter puts a λ gradient across each detector, so one image is not one channel.
- 2026-11-14: an 86′ tile field = 30-44 cutouts of ~5 MB (gz) from the VM, 101 s (77 s download).
- 2026-11-14: one-detector field of the same size (RA 165.94 Dec +15.0, D2): 6 cutouts, 31 s.
- 2026-11-14: pass tile, 2nd channel of the same detector: 0.01 s (was a new 1-4 s render); false-colour tile
  first time 7.3 s (6 grey tiles side by side), then 0.04 s; switching back to any band of it is instant.

## Questions / needs from others

## Handoff
- `/app/`: band slider label says the detector and its range; "false colour" switch next to it.
- API: `GET /api/target?...&detector=3` (id `…-d3`), `/api/hips/<id>/e1d3`, `/api/hips/<id>/e1c`,
  `/api/sky/spherex-live-p2-rgb/...` (CONTRACTS v0.20).
- Gotcha: false-colour field epochs need the all-detector build (~100 s per tile); passes in false colour
  come in seconds.

## Notes from others
- 2026-11-14 [Joerg → Jonathan] Proposal for T89, to consider (nothing started, your call):
  your field false colour uses the per-detector means of the ~2 frames per epoch × detector that a field build
  keeps. T85 (`pipeline/fieldspectra.py`, CONTRACTS v0.15) already downloads a field-sized cutout of *every*
  exposure there (~240, ~40 per detector, cached under `data/raw/cutouts/`). I could add deep stacks from those:
  per detector (all epochs) and per detector × epoch, resampled to the field grid, flags masked, ~4–5× deeper
  than one frame (√40 vs √2). Offered as field layers through the existing `/api/hips/<id>/<layer>` route
  (server/hips.py, T81), e.g. `s<det>` and `s<det>-e<epoch>`, so your RGB layer and band slider could use them as
  input instead of the 2-frame means; nothing in `app/` or tilegen from my side. Why it matters for the pitch:
  faint red sources only show in deep stacks, e.g. WISE 0855 (official target) is invisible at 1 µm and should
  walk ~11″ (2 px) across a deep 4.5 µm blink of the three epochs. Tell me in this section (or TEAM.md) if you
  want it and which layer names / shape you'd like; until then I don't touch it and do T87 instead.
