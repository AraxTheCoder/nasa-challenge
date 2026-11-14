# T45: Play the series like a video

- **Owner:** Mati  ·  **Status:** done
- **Branch:** `mati/T45-play` (merged)
- **Depends on / feeds:** T11/T12 (viewer, timeline, wavelength filter); idea #1 of the gap scan
- **From:** core Objective: "Your tool will display a series of images of that patch like a little video".

## Goal
Besides the A/B blink, a Play button runs through the frames like a short film: all frames inside the
wavelength/detector filter in time order, or one frame per epoch at matched wavelength, with speed and
loop. The stage label, frame table and timeline follow the playing frame.

## Plan
- [x] Play/Pause for the whole series (key `P`), speed shared with the blink interval, loop
- [x] Modes: "all frames in the filter" and "one per epoch, closest to A's wavelength"
- [x] Exclusive with blink, difference view and trail view; stops on manual stepping
- [x] Browser test checks

## Findings
- Playback is one mechanism with two modes (`state.playMode`: blink or film); `stopBlink()` stops either,
  so every existing stop path (A/B buttons, stepping, flip, objects jump) also stops the film.
- The film sequence is recomputed on every tick, so the wavelength/detector filter and A (for the
  per-epoch mode) can change while it plays.
- Real Barnard's Star field, "1 per epoch, A's λ": three frames at ~0.75 µm, one per epoch, a clean
  "how did this patch change" film; "all frames" runs through all 36 (λ jumps between frames, so star
  brightness flickers: that is the wavelength stepping, not variability).

## Questions / needs from others

## Handoff
- Button "▶ Play all" / key `P`, mode picker next to it, speed = the Interval slider. Starting it ends
  the blink, the difference view (T43) and the trail view (T23); `viewer:blink` carries `mode: "film"`.
- `filmFrames()` in `web/viewer.js` decides the sequence; add modes there.

## Notes from others
(anyone may append here, dated and signed)
