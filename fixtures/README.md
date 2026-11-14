# fixtures

Tiny committed samples for tests and frontend development. Layout as in `docs/CONTRACTS.md`.

- `targets/demo-synthetic/`: **fully synthetic** (random stars plus one fake mover, 4 frames, 96×96 px).
  It is not SPHEREx data and must never be shown as such. It exists so all three tracks can start
  before the pipeline produces a real target.

Regenerate with `python3 fixtures/make_demo_synthetic.py .` from the repo root.
