# T34: Label priority: only the most important names always visible, the rest on hover

- **Owner:** Joerg  ·  **Status:** done
- **Branch:** `joerg/T34-label-priority`
- **Depends on / feeds:** T22/T23 (`web/paths.js` names and hover), T19 (`labels`), T13 (objects panel)
- **Requested by:** Mati, 2026-11-14, after seeing the real Barnard's Star field (271 labels): "labels
  are too crowded".

## Goal
At any zoom, the image shows only a few names: the ones that matter. Every other label stays a small
marker (or nothing) and shows its name only on hover. T23 already avoids overlapping names; this is a
stricter rule: importance first, space second.

## Plan (proposal, to be refined by whoever takes it)
- [x] Importance order, always shown: (1) the field's own object (the test field / object the user
      asked for, e.g. Barnard's Star), (2) unknown movers and detections, (3) known asteroids/comets,
      (4) named objects with a notable motion class (`proper motion`, `fast mover`, `distant body?`),
      (5) a small number of the brightest named stars. Everything else: name on hover only.
- [x] A cap (e.g. ≤ 8 names) plus a "show all names" toggle for the curious
- [x] Hover / focus on any marker shows its name (keyboard accessible); the inspector (T23) still opens on click
- [ ] Browser test checks: count of visible names ≤ cap on the real-like test target; hover reveals a hidden name

## Findings
- 2026-11-14 [Joerg] Checked the five real official fields: WISE 0855 itself is labelled but with
  `named: false` (its SIMBAD name `WISEA J085510.74-071442.5` looks like a catalogue number), so it is
  hidden by default: the main reason this task matters. Also: RW Aur, RW Aur A and RW Aur B sit on one
  spot; Barnard's Star is there twice (SIMBAD + its Gaia entry); some kinds show raw codes (`LM*`, `LSB`).

## Questions / needs from others

## Handoff
- Pipeline: `pipeline/labels.py` merges duplicates (`aliases`) and ranks `importance` (CONTRACTS v0.7);
  tests in `pipeline/test_labels_rank.py`. The five official fields: the target is rank 0 in each
  (Barnard's star, * eps Ind B, WISEA J085510.74-071442.5, RW Aur, R Dra). Labels per field went
  down by 1-25 through merging.
- Viewer: names only for movers and importance ≤ 2, at most 8, most important first; "All names"
  toggle; the field's object has a bigger ring; tooltip shows aliases; markers are focusable (Tab),
  focus shows the tooltip, Enter opens the inspector. Old targets without `importance` get it
  derived in the browser.
- Not done: browser test checks (Joerg's agent can't run Chromium). Note: `#overlay` is
  `aria-hidden` in index.html, so screen readers skip the focusable markers; changing that is Mati's file.

## Notes from others
(anyone may append here, dated and signed)
