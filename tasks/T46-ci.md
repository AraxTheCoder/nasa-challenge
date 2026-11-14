# T46: Tests on every push (GitHub Actions)

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T46-ci`
- **Depends on / feeds:** everything; idea #9 of the gap scan

## Goal
Every push to main and every PR runs the Python tests, the browser test (fixture mode, no external
servers) and a schema check of the committed fixtures, so a broken page or a broken contract is noticed
within minutes instead of by the next human who opens the viewer.

## Plan
- [ ] `.github/workflows/tests.yml`: Python 3.12, `pip install -r requirements-dev.lock`, Playwright
      Chromium, `pytest detect server pipeline`, `python web/tests/browser_test.py`
- [ ] Schema test: every committed `fixtures/**/target.json` validates against `docs/target.schema.json`
- [ ] Badge + one line in README; screenshots of a failing browser test uploaded as an artifact

## Findings

## Questions / needs from others

## Handoff

## Notes from others
(anyone may append here, dated and signed)
