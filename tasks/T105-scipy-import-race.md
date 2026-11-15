# T105: First photometry after a start can fail (scipy imported by two threads at once)

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `main`
- **Depends on / feeds:** T49 (photometry)

## Goal
No 500 on the first spectrum / photometry request after the Live API starts.

## Plan
- [x] Import the scipy parts the pipeline uses once, when the server module loads

## Findings
Mati's Live API log, 2026-11-15: `GET /api/targets/c2692969-p047802-s86-d1/photometry` → 500,
`ImportError: cannot import name 'PytestTester' from partially initialized module 'scipy._lib._testutils'
(most likely due to a circular import)`, raised from `from scipy.interpolate import RegularGridInterpolator`
inside `pipeline.build.wavelengths_at`. Seen once, on the first requests after a restart, when several
request threads reach a first scipy import together. Not reproduced on purpose (it is a race); the fix removes
the condition: by the first request scipy is fully imported.

## Questions / needs from others

## Handoff
`server/app.py` imports `scipy.interpolate` and `scipy.ndimage` at the top. Command-line tools are
single-threaded at that point and were never affected.

## Notes from others
(anyone may append here, dated and signed)
