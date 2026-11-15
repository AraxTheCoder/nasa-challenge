# T98: Live API memory: spectrum worker pool sized to the machine, released when idle

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T98-spectrum-pool-memory`
- **Depends on / feeds:** follows T83 (16 worker processes for spectra), T85 (field spectra); feeds T14 (how much RAM the host needs)

## Goal
The Live API no longer gets OOM-killed on an 8 GB machine: the spectrum worker processes are sized to the
machine's memory and CPUs, and their memory is given back when nobody has asked for a spectrum for a while.
Spectra on a big machine stay as fast as today.

## Plan
- [x] Measure where the memory goes (below)
- [ ] `pipeline/photometry.py`: number of worker processes from RAM and CPU count, override with
      `SPHEREX_SPECTRUM_PROCESSES` (0 = threads only)
- [ ] Shut the pool down after some minutes without use; the next request starts a new one
- [ ] Tests; measure again; note for T14

## Findings
Measured 2026-11-15 ~00:50 UTC on Mati's machine (WSL2, 16 cores, 31 GB), `python web/dev.py`, RSS of the
API process and all its children, sampled once a second:

| State | Memory |
|---|---|
| after the first spectrum (pool started, idle) | 3.5 GB = server 1.45 GB + 16 workers × 129 MB |
| during one field-spectra run (`/api/targets/c2678906-p047802-s86-d1/spectral-outliers?start=1`, 86′ tile field, 406 exposures, 85 s) | peak 5.3 GB |
| after it, idle | 5.2 GB = server 1.6 GB + 16 workers × ~235 MB (≈205 MB private each, `smaps_rollup`) |

- The workers never exit and never shrink, so the API keeps ~3.3 GB for good after the first spectrum.
- The pool is always 16 processes, whatever the machine (`SPECTRUM_PROCESSES = 16`).
- With the map on, opening a field measures its outliers automatically (`web/outliers.js`, `load(st.mapOn)`),
  so the pool starts without anyone asking for a spectrum.
- Not looked at: what the 1.5 GB of the server process itself is (orbit catalogue? image index? tile caches).

## Questions / needs from others
- [to Joerg] `_pool()` and `SPECTRUM_PROCESSES` are yours (T83). I change only those; shout if that collides
  with T60.

## Handoff

## Notes from others
(anyone may append here, dated and signed)
