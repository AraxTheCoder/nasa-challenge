# fixtures

Tiny committed samples for tests and frontend development. Layout as in `docs/CONTRACTS.md`.

- `targets/demo-synthetic/`: **fully synthetic** (random stars plus one fake mover, 4 frames, 96×96 px).
  It is not SPHEREx data and must never be shown as such. It exists so all three tracks can start
  before the pipeline produces a real target.

- `targets/demo-epochs/`: **fully synthetic** too, schema 0.2 with every optional field of the contract
  (T55): 9 frames in 3 epochs on 2 detectors, `bandwidth_um`, a corner without data (alpha 0),
  wavelength-matched `pairs`, `labels` (a proper-motion star, a variable, a star with an alias; source
  `synthetic`), two made-up known asteroids and three detections that `detect.classify` marks known /
  unknown / artifact. Use it to try every viewer feature offline
  (`web/?data=../fixtures/targets/&target=demo-epochs`) and as the example of a complete target.json.

Regenerate from the repo root: `python3 fixtures/make_demo_synthetic.py .` and
`python fixtures/make_demo_epochs.py` (deterministic: same bytes every run). Both are checked against the
schema by CI (`tests/test_contract.py`).
