# T76: C: Discovery index in the viewer: candidates per tile from the survey served by the Live API; "Show me something interesting" + candidate list, each opening its field with blink, spectrum and reason

- **Owner:** –  ·  **Status:** open
- **Branch:** –
- **Depends on / feeds:** T75 (data), T62, T65

## Goal
Users can ask the tool for something interesting and land on a candidate with its evidence (blink, spectrum, hints, why it was picked).

## Plan
- [ ] Index format + `GET /api/discoveries?ra=&dec=&radius=` / random pick (CONTRACTS + Decisions line)
- [ ] Viewer: "Show me something interesting" button + candidate list (sortable by class/score), click opens the field
- [ ] Candidate reason and class shown with the field (objects panel / inspector)
- [ ] Works on a hand-made sample index before pass 2 delivers (synthetic, labelled); browser test

Design of the whole survey (passes, data volumes, candidate classes, open questions): [T73](T73-survey-plan.md).

## Findings

## Questions / needs from others

## Handoff

## Notes from others

- 2026-11-14 Mati (Claude): the heatmap layer should show observed minus expected chance outliers per tile (method and rules: T75, Notes from others).
