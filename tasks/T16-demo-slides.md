# T16: Demo video and slides

- **Owner:** Jonathan  ·  **Status:** doing
- **Branch:** `main` (documents only, no code of the tool)
- **Depends on / feeds:** T15 (submission text), T120 (collaboration), T93/T107/T127 (chemistry), T124 (UI)

## Goal
A pitch deck for the local judging: PowerPoint, at most 10 slides, English, with marked placeholders where
Jonathan inserts his screen recordings. Separately (still open): the demo for the project page (video of 30 s
or less, or a deck of up to 7 slides, on a public link).

## Plan
- [x] Local judging deck `docs/pitch/local-judging-pitch.pptx`, built by `docs/pitch/build_pitch.js`
- [ ] Jonathan records the videos and drops them into the placeholders
- [ ] Demo for the project page (30 s video or 7 slides), public link into `docs/SUBMISSION.md`

## Findings
- Deck (2026-11-15): 10 slides, 16:9, English, speaker notes on every slide. Story: every telescope generation
  delivers more data (IRAS 1983, WISE 2010, SPHEREx 2025) -> more gets past the algorithms -> volunteers are needed
  -> our tool: navigation, chemistry filters (H2O etc.), computer assistance, collaboration (view counts per tile,
  "look here" + discussion, share by link) -> checks on real data.
- Five dashed boxes "Video placeholder 1-5" (slides 5-9) say what to record and how long.
- Numbers on the slides come from `docs/CHALLENGE.md`, `docs/SUBMISSION.md` and `README.md`, except slide 2: IRAS
  (~350 thousand sources) and WISE (~750 million objects, AllWISE) are written from memory, not looked up.
- Checked: file validation passes; all 10 slides rendered with PowerPoint and looked at (no overflow, no overlap).

## Questions / needs from others

## Handoff
- Rebuild after text changes: `npm install pptxgenjs jszip` somewhere, then
  `NODE_PATH=<that>/node_modules node docs/pitch/build_pitch.js`. A rebuild overwrites the .pptx, so videos
  inserted by hand are lost: edit text in PowerPoint once the videos are in.
- Still to fill in by hand: `[live URL]` on slide 10 (T14); project name "SPHEREx Blink" is the working name
  (Mati picks, `docs/SUBMISSION.md`); team names as each member wants them.
- The project page allows a deck of at most 7 slides: this one has 10 and is for the local judging only.

## Notes from others
(anyone may append here, dated and signed)
