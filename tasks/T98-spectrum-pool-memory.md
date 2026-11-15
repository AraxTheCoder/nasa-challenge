# T98: Live API memory: spectrum worker pool sized to the machine, released when idle

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T98-spectrum-pool-memory`
- **Depends on / feeds:** follows T83 (16 worker processes for spectra), T85 (field spectra); feeds T14 (how much RAM the host needs)

## Goal
The Live API no longer gets OOM-killed on an 8 GB machine: the spectrum worker processes are sized to the
machine's memory and CPUs, and their memory is given back when nobody has asked for a spectrum for a while.
Spectra on a big machine stay as fast as today.

## Plan
- [x] Measure where the memory goes (below)
- [x] `pipeline/photometry.py`: number of worker processes from RAM and CPU count, override with
      `SPHEREX_SPECTRUM_PROCESSES` (0 = threads only)
- [x] Shut the pool down after some minutes without use; the next request starts a new one
- [x] Tests; measure again; note for T14

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
- `pipeline/photometry.py`: `spectrum_processes()` picks the worker count: at most 16, one per CPU, together
  at most a quarter of the RAM at 0.25 GB each (8 GB → 8, 4 GB → 4, ≥16 GB → 16 as before).
  `SPHEREX_SPECTRUM_PROCESSES=<n>` overrides it; `0` = threads only, no worker processes.
- The pool shuts down after `POOL_IDLE_S` = 5 min without work (`_retire_when_idle`); the next spectrum
  starts a new one. A pool with tasks waiting or running is never shut down.
- Checked with real processes (idle time set to 4 s): 16 workers start, results correct; after the idle
  time 16 of 19 child processes are gone (252 MB → 31 MB, the forkserver and resource tracker stay); the next
  request gets a new pool at once; a 7 s job outlives the idle time untouched. 225 Python tests pass.
- Not yet measured on the running API after this change (needs a server restart and 5 idle minutes).
- For T14: budget ~1.6 GB for the API process plus 0.25 GB per worker while spectra run.
- Left: the 1.5 GB of the server process itself is unexplained.

## Notes from others
(anyone may append here, dated and signed)
