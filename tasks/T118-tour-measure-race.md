# T118: C: Bug: the tour's "Measure its speed with SPHEREx" can leave the motion box on its button although the server measures

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `main` (web/motion.js, one flag)
- **Depends on / feeds:** T91 (motion box), T92 (tour); found by the browser test (live_check round 2)

## Goal
The tour's action asks the next motion box to measure right away (`measureNext()`). The spectrum panel renders
several times while its spectrum loads (field frames, then all exposures), and every render makes a new motion
box; only the first got the flag (start=1), a later one asked with start=0 before the job was registered, got
`not_started`, showed the button and stopped polling, while the server measured in the background. Now every box
for the next ~60 s asks with start=1 until one sees the job (building / ready).

## Plan
- [ ] motion.js: `autoStart` = a deadline, cleared once a box gets building / ready from a start request
- [ ] browser check on a star whose motion is not cached

## Findings

## Handoff

## Notes from others
