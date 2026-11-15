# T102: A broken image index repairs itself

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T102-index-atomic`
- **Depends on / feeds:** T31 (local SPHEREx image index), T71 (data set up by itself)

## Goal
A cut-off `data/mirror/index.npz` can no longer exist after a normal build, and one that does exist (older
checkout, full disk) is noticed, put aside and built again, instead of failing every request for good.

## Plan
- [x] `build()`: write to a temporary file, then rename (one step)
- [x] `available()`: the file must be a complete zip; a broken one is renamed to `index.npz.broken`
- [x] Tests

## Findings
2026-11-15 ~02:40 UTC, Mati's machine: `index.npz` 45 MB, starts with `PK` but has no zip directory at its end
(`zipfile.BadZipFile: File is not a zip file`). `np.savez_compressed` writes straight to the final name, so a
server stopped during the write (here: a restart while the first-start data setup was still running) leaves a
partial file. After that: `/api/pass-dates` 500 on every call (46 in the log), the dates of the survey passes
missing on the map, the startup line still says "SPHEREx image index ok".

## Questions / needs from others

## Handoff

## Notes from others
(anyone may append here, dated and signed)
