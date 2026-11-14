# T89: Band switching that works on the map + a false-colour layer

- **Owner:** Jonathan  ·  **Status:** doing
- **Branch:** `main` (like T55: `app/` + tilegen/server pieces)
- **Depends on / feeds:** T55 (`/app/`), T82 (pass layers), T32 (field epoch layers), T57 (cutouts)

## Goal
The band slider changes what blinks, for survey passes *and* field epochs, and changing it within one
detector is instant; a "false colour" option shows all bands combined (blue = short, red = long λ), also
while blinking. Field epoch builds get faster by fetching only what the shown band needs.

## Plan
- [ ] Live / pass tiles per detector: the image only depends on the detector (`slice // 17`), so ask for one
      canonical slice per detector; the 17 channels of a detector share one cached tile
- [ ] Field epochs per band: automatic builds only for the detector of the shown band (~6-8 instead of
      36-44 cutouts); another detector = another (cached) build of the same tile
- [ ] False colour for passes: RGB tiles composed from the 6 per-detector grey tiles (cached, reused when
      switching bands); blue D1+D2, green D3+D4, red D5+D6
- [ ] False colour for field epochs: all-detector build, RGB epoch layers from per-detector means
- [ ] Band control: slider + "false colour" switch; labels say which detector / λ range is shown

## Findings
- 2026-11-14: field epoch layers are the mean of all frames of an epoch over all 6 detectors
  (`server/hips.py`), so the band slider did nothing for them; pass tiles only change at detector
  boundaries (D1 0.75-1.09, D2 1.10-1.62, D3 1.63-2.41, D4 2.42-3.82, D5 3.83-4.41, D6 4.42-5.00 µm):
  SPHEREx's linear variable filter puts a λ gradient across each detector, so one image is not one channel.
- 2026-11-14: an 86′ tile field = 30-44 cutouts of ~5 MB (gz) from the VM, 101 s (77 s download).

## Questions / needs from others

## Handoff

## Notes from others
