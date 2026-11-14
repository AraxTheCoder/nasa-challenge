# T19: Labels on the images

- **Owner:** Joerg  ·  **Status:** doing
- **Branch:** `joerg/T19-labels`
- **Depends on / feeds:** T04 (frames + `target.json`), T13 (overlay in the viewer), T07 (known
  small bodies, Jonathan)

## Goal
Find out which labels we can put on SPHEREx frames (names of stars, brown dwarfs, variables,
galaxies; catalogue positions; known small bodies), where they come from, how fast, and how they go
into `target.json` so the viewer (T13) can draw them. Then build the pipeline side.

## Plan
- [ ] Check catalogue sources for a field: SIMBAD (names, object types), Gaia DR3 (positions +
      proper motion), CatWISE / AllWISE at IRSA (infrared, brown dwarfs), timing per query
- [ ] Proper motion: propagate catalogue positions to each frame's time (Barnard's Star moves
      ~10"/yr, so a J2000 position is minutes of arc off)
- [ ] Try it on real frames (COSMOS exploration data, then one official target)
- [ ] Propose a `labels` field for `target.json` (contract change + Decisions line)
- [ ] Pipeline code: `pipeline/labels.py`

## Findings
(in progress)

## Questions / needs from others

## Handoff

## Notes from others
