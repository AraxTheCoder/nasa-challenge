# T140: Clear source brightness analysis

- **Owner:** Codex (brightness) · **Status:** doing
- **Branch:** `codex/T140-brightness-panel`
- **Depends on / feeds:** T49, T63, T84, T138

## Goal
Explain what the selected-position brightness measurement shows and make the panel readable: distinguish spectrum from between-epoch brightness comparisons, give each a clear view, and keep advanced interpretation optional.

## Plan
- [ ] Explain aperture measurement, spectrum axes and same-wavelength comparisons in plain language.
- [ ] Show one readable observing period or period pair at a time, preserving error bars and flags.
- [ ] Move model hints, feature overlays and quality details behind optional controls.
- [ ] Verify scientific matching/empty states, new interaction, mobile layout and T138 selection retention.

## Findings
- The existing so-called light curve has wavelength, not time, on its horizontal axis; it compares exposure pairs between epochs with wavelengths within half a channel.
- Flux is aperture photometry at the selected position, with local background subtraction. Neighbours and calibration can affect measurements; not an isolated-source or simultaneous full spectrum.
- T138's selected-point/region behavior is already committed; this task preserves its controller logic.

## Handoff
In progress.
