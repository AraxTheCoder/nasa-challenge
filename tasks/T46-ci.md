# T46: Tests on every push (GitHub Actions)

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T46-ci` (merged)
- **Depends on / feeds:** everything; idea #9 of the gap scan

## Goal
Every push to main and every PR runs the Python tests, the browser test (fixture mode, no external
servers) and a schema check of the committed fixtures, so a broken page or a broken contract is noticed
within minutes instead of by the next human who opens the viewer.

## Plan
- [x] `.github/workflows/tests.yml`: Python 3.12, `pip install -r requirements-dev.lock`, Playwright
      Chromium, `pytest detect server pipeline`, `python web/tests/browser_test.py`
- [x] Schema test: every committed `fixtures/**/target.json` validates against `docs/target.schema.json`
- [x] Badge + one line in README; screenshots of a failing browser test uploaded as an artifact

## Findings
- Rehearsed exactly the workflow's commands in a fresh clone + fresh venv (Python 3.12): install from
  `requirements-dev.lock` 54 s, 80 Python tests pass, browser test 0 failures (~20 s with `?explore=0`).
  `playwright install --with-deps` needs root, which the GitHub runner has; locally it was skipped.
- No test touches the network: Python tests are offline, the browser test runs the API in fixture mode.
- The repo is private and there is no `gh` here, so the first GitHub run has to be checked in the
  Actions tab by a human.

## Questions / needs from others

## Handoff
- Red X on a commit = something broke; the run page has the failing check, and the browser test's
  screenshots are attached as the artifact `browser-test-screenshots`.
- New tests in `detect/`, `server/`, `pipeline/`, `tests/` are picked up automatically. A new top-level
  test folder must be added to the `pytest` line in `.github/workflows/tests.yml`.
- Keep tests offline; anything that needs IRSA/AWS/JPL belongs behind a fake client (see
  `detect/test_known_objects.py`).

## Notes from others
(anyone may append here, dated and signed)
