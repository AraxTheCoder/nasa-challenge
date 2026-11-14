# T65: A/C: Auto target selection: propose interesting fields (high proper-motion stars, brown dwarfs, asteroids passing through, fields with unknown movers, "surprise me")

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T65-auto-targets`
- **Depends on / feeds:** T31, T51, T06

## Goal
Besides typed coordinates, the viewer proposes interesting fields as quick picks.

## Plan
- [x] Sources: SIMBAD high proper motion + brown dwarfs (done); known asteroids and T06 movers: not yet, see Findings
- [x] Rank by how much moves there; a "surprise me" pick
- [x] Viewer: list / quick picks next to the five official fields (T20/T25)

## Findings
- `web/discover.json` (built by `web/make_discover.py`, SIMBAD TAP Harvard mirror + local SPHEREx index, 2026-11-14):
  20 quick picks in two groups next to the five official fields; each with coverage (epochs, first/last date),
  expected shift in SPHEREx pixels and a plain-words reason shown under the header ("why this field").
- **SPHEREx's coverage spans only ~1 year per position (DR1)**, so proper motion is small in pixels: Kapteyn's
  star (8.6″/yr) 1.5 px, Groombridge 1830 / Lacaille 9352 1.2 px, Teegarden's Star 0.9 px; brown dwarfs only
  0.1–0.6 px. Checked live on Kapteyn's star (36 frames, 3 epochs): the saturated core and its label move,
  but subtly. So the stars group says "small: blink first against last epoch", and the brown-dwarf group is
  framed as "look at the spectrum" (T63), not motion.
- Bright fast stars are kept although saturated (K < 6): the moving no-data core is what you see, as for
  Barnard's Star. Brown dwarfs need K ≤ 13.5 for a measurable spectrum.
- Not done: known asteroids crossing fields (builds keep 2 images per epoch+detector and usually miss the
  asteroid's exposures, T09) and fields with unknown movers (needs T06 / the survey T73–T77, then T76).
From idea I10 in TEAM.md (moved to the Board by Mati, 2026-11-14). From Joerg's idea.

## Questions / needs from others

## Handoff
- Viewer: the field dropdown has optgroups (official / fastest-moving stars / brown dwarfs); "Surprise me" picks
  a random non-official field; `#pick-why` shows the reason while the form holds that field.
- Regenerate: `python web/make_discover.py` from the repo root (needs `data/mirror/index.npz`); CI checks the
  file's shape (`tests/test_contract.py::test_discover`). Jonathan: port the dropdown groups, "Surprise me" and
  the reason line to `app/` (T55).

## Notes from others
