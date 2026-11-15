# T118: C: Bug: the tour's "Measure its speed with SPHEREx" can leave the motion box on its button although the server measures

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `main` (web/motion.js, one flag)
- **Depends on / feeds:** T91 (motion box), T92 (tour); found by the browser test (live_check round 2)

## Goal
The tour's action asks the next motion box to measure right away (`measureNext()`). The spectrum panel renders
several times while its spectrum loads (field frames, then all exposures), and every render makes a new motion
box; only the first got the flag (start=1), a later one asked with start=0 before the job was registered, got
`not_started`, showed the button and stopped polling, while the server measured in the background. Now every box
for the next ~60 s asks with start=1 until one sees the job (building / ready).

## Plan
- [x] motion.js: `autoStart` = a deadline, cleared once a box gets building / ready from a start request
- [x] browser check on a star whose motion is not cached

## Findings
- Seen in the browser (live_check round 2): after the tour's "Measure its speed with SPHEREx" the box still showed
  "Measure it from SPHEREx (~15 s)" two minutes later, while the server had measured (the result was in the cache
  on the next run).
- Fix: `measureNext()` sets a 60 s deadline; every box made until then asks with start=1 (harmless when the job
  runs or is done), cleared once a start request answers building / ready.
- Check (Barnard's cached motion moved aside, restored by the run itself): two boxes asked start=1 → 202 building,
  polled 112 → 358 exposures, ready after 11 s: "10.43 ± 0.24″ per year, toward the north … SPHEREx agrees".

## Handoff
Done. [Joerg] your T91 file; one flag changed, nothing else.

## Notes from others
