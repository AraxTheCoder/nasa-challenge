# T06: Mover detection v0

- **Owner:** Mati (taken over from Jonathan, Decision 2026-11-15)  ·  **Status:** done (v0)
- **Branch:** `mati/T06-mover-detection`
- **Depends on / feeds:** T04 (built fields), T08 (classify), T51 (`detect.run`); feeds T61, T62, T67, T70

## Goal
`python -m detect.run <target_dir>` fills `detections` for a built real field: sources that are in the
SPHEREx images at one time and not at the same sky position at other times, with a track per CONTRACTS.
The viewer's objects panel then shows them (known / unknown / artifact from T08).

## Plan
- [x] `detect/movers.py`: sources per frame from the cached SPHEREx cutouts (IMAGE − ZODI, VARIANCE, FLAGS)
- [x] Reference = the same sky position in frames of the same detector at other times; keep what is not there
- [x] Confirmation = the two detectors that image the same sky at the same moment must both show it
- [x] Link sightings close in time into one track; plug into `detect/run.py`; provenance entry
- [x] Tests on made-up cutouts; run on the cached real fields; numbers here

## Findings
Run on the six fields cached on Mati's machine, 2026-11-15 ~02:20 UTC (`python -m detect.movers <dir>`, ~3 s each):

| Field | Images | Sightings | There at other times | One detector only | Detections |
|---|---|---|---|---|---|
| RW Aur `c0769566-p304013-s15` | 36 | 2792 | 2779 | 12 | 1 (S/N 7) |
| WISE 0855 `c1337598-m072422-s15` | 36 | 1845 | 1826 | 17 | 1 (S/N 14) |
| Barnard `c2694463-p047682-s15` | 36 | 3058 | 3047 | 10 | 1 (S/N 14) |
| Eps Ind `c3310966-m568007-s15` | 44 | 1618 | 1597 | 21 | 0 |
| two 86′ tile fields (6 images each) | 6 | 772 | 772 | 0 | 0 |

- All three detections are seen at one moment only (both simultaneous detectors), none matches a known asteroid
  or a catalogue star; T08 calls them `unknown`, score 0.4–0.5. **Not checked by eye yet.** The Barnard one
  (RA 269.46642, Dec +4.68765, frames f022/f023, 2026-05-05 02:00 UTC) is elongated over ~5 pixels in the
  4.9 µm image: a streak (satellite or a fast near-Earth object) is more likely than a point source.
- The known asteroids of these fields are V 18–20, far below the single-exposure limit (T09), so none is
  expected and none is found.
- Built fields have 2 images per survey pass and detector, days apart: no object is seen at two moments, so
  no motion is measured. Linking sightings hours apart exists and is tested on made-up data only.
- The first version took 11–38 s per field: a running median for the background (0.3 s per image). A block
  median, interpolated, gives the same detections in ~3 s.
- The reference test is strict: a 3σ noise peak within 1.5 px in any reference image drops a sighting, so a
  real one-moment source is lost maybe one time in ten. Chosen on purpose: few, clean marks.

## Questions / needs from others

## Handoff
- `detect/movers.py` (`find_movers(target)`), called first in `detect.run.detect_target`. Needs the field's
  cached cutouts under `data/raw/` (there after a build); without them it is skipped and says so in provenance.
- Each detection carries `evidence` {moments, images, absent_in, sn} (CONTRACTS v0.30); `detect/classify.py`
  rule 3b turns "one moment, both detectors, absent otherwise" into `unknown` with a low score.
- Existing fields get detections when detect runs again on them (rebuild, or `python -m detect.run <dir>`).
- For T67: "one detector only" is already rejected here (step 3). For T61: step 2 is the appear/vanish test for
  one moment; brightness changes are not looked at.
- Left: look at the three detections in the viewer; a streak test (elongation); deeper fields (all exposures,
  not 2 per group) so that motion can be measured.

## Notes from others
(anyone may append here, dated and signed)
