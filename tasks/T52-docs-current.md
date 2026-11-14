# T52: Docs match the code (idea I2)

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T52-docs-current`
- **Depends on / feeds:** T15 (submission text reads the README), T14 (deploy docs)

## Goal
Someone new (judge, teammate, the submission text) can trust README, CONTRACTS and the fixtures:
nothing describes a state the live-data decision (v0.3) or later tasks made obsolete.

## Plan
- [ ] README: status (real data, not "every field synthetic"), how it works, run options, entry points
- [ ] CONTRACTS: drop pre-baked `web/targets/`, its size budget and `pipeline.publish`; entry points as they
      are; document the API routes the viewer uses but CONTRACTS doesn't list (Decisions line)
- [ ] `web/README.md`, `server/README.md`: same check
- [ ] A second committed fixture, schema 0.2: several epochs, pairs, labels, known / unknown / artifact
      detections (from the generator the browser test uses), validated by `tests/test_contract.py`
- [ ] Tests green (pytest + browser test), merge, Log line

## Findings

## Questions / needs from others

## Handoff

## Notes from others
