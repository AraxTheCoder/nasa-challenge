# T56: Docs match the code (idea I2)

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T52-docs-current` (claimed as T52; renumbered to T56 after ID clashes with Joerg's T52 and Jonathan's T55)
- **Depends on / feeds:** T15 (submission text reads the README), T14 (deploy docs)

## Goal
Someone new (judge, teammate, the submission text) can trust README, CONTRACTS and the fixtures:
nothing describes a state the live-data decision (v0.3) or later tasks made obsolete.

## Plan
- [x] README: status (real data, not "every field synthetic"), how it works, run options, entry points
- [x] CONTRACTS: drop pre-baked `web/targets/`, its size budget and `pipeline.publish`; entry points as they
      are; document the API routes the viewer uses but CONTRACTS doesn't list (Decisions line)
- [x] `web/README.md`, `server/README.md`: same check
- [x] A second committed fixture, schema 0.2: several epochs, pairs, labels, known / unknown / artifact
      detections (from the generator the browser test uses), validated by `tests/test_contract.py`
- [x] Tests green (pytest + browser test), merge, Log line

## Findings
- Stale beyond the idea's list: `TECH-STACK.md` (whole file described the pre-baked plan: rewritten),
  `web/README.md` (half the modules, keys and URL options missing), `server/README.md` (fixture-only
  wording, detect after build), an Aladin comment in `index.html`, README "planned" commands.
- CONTRACTS lacked 5 routes the viewer uses (`/objects`, `/sky/…`, `GET`/`POST /settings`, `/health`),
  `labels_requested` / `objects_requested`, the real `build_target` / `detect` signatures (`detect` returns
  a Path, not a dict). Now v0.11. Built targets are not schema-validated at build time (noted in CONTRACTS).
- Bug found on the way (Mati OK'd fixing it here, separate commit): since T51 the known-object
  candidates come from SkyBoT, but `detect.classify` only recognised "SB Identification" in provenance,
  so every unknown detection was capped at score 0.6 with a wrong "not looked up" note.
- Also OK'd: CI now runs `tilegen` tests (5, ~1 s; never ran in CI); `paths.js` marks labels with
  `source: "synthetic"` as not real.

## Questions / needs from others

## Handoff
- New fixture: `fixtures/targets/demo-epochs/` (96 KB), regenerate with `python fixtures/make_demo_epochs.py`
  (deterministic; uses `pipeline.motion` + `detect.classify`, so rerun it when those change their output).
  Try it: `web/?data=../fixtures/targets/&target=demo-epochs`. Long label names don't fit the 96-px image
  and are hidden by the label placement (hover still works).
- Still TODO elsewhere: data credits (DOIs, acknowledgement texts) and team names in README: T15.

## Notes from others
