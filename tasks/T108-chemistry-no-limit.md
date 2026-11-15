# T108: C/A: Chemistry: no limit of 3 features in one picture

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T108-chemistry-no-limit`
- **Depends on / feeds:** T96 (combined maps), T107 (presets)

## Goal
Asked by Mati (2026-11-15): tick any number of chemistry features (all 10) for one colour picture. Why there was
a limit: three colours (blue, green, red) are independent, so every mix can be read back (yellow = green + red).
From four on, each feature gets its own hue by wavelength (blue → cyan → green → yellow → red); mixes can then no
longer be read back uniquely, and the legend says so.

## Plan
- [ ] pipeline/chemistry.py: COMBINE_MAX = all features; colours for any count (2 and 3 unchanged)
- [ ] server/hips.py layer pattern; CONTRACTS + Decision
- [ ] viewer: texts without "up to 3", the note warns about mixes from 4 on
- [ ] tests

## Findings

## Questions / needs from others

## Handoff

## Notes from others
