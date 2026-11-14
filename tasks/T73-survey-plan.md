# T73: A: Discovery survey pass 0 + pilot: catalogue targets and a sparse exposure set per sky tile (~2 per epoch × detector, matched λ) as a manifest for pass 1; pilot regions chosen

- **Owner:** Joerg (assigned by Mati, 2026-11-14)  ·  **Status:** open
- **Branch:** –
- **Depends on / feeds:** T31, T51, T52

## Goal
A manifest per sky tile (HEALPix) listing the catalogue targets there and the few exposures pass 1 reads, for the pilot regions first.

## Plan
- [ ] Tiling (HEALPix order ~6) and the pilot regions (official fields, ecliptic strip, high-latitude region)
- [ ] Catalogue targets per tile: Gaia DR3 + CatWISE2020 high proper motion and brown-dwarf colours, VSX variables, MPC asteroid tracks (T51)
- [ ] Exposure selection from the local index (T31): ~2 per epoch × detector per tile, matched wavelength where possible; fix outdated paths (T09 saw IRSA 404s)
- [ ] Manifest format (JSON/Parquet) + numbers: images, TB, estimated hours; Decisions line

## The survey in one page (shared by T73–T76)

Goal: suggest new / interesting findings from (eventually) all SPHEREx data, without moving 107 TB.

Why not lower-resolution images: SPHEREx pixels are already 6.15″. Asteroids move hundreds of ″ between visits
(fine at any resolution), but the interesting slow movers don't: WISE 0855 moves ~4″ in 6 months (0.65 px),
a typical nearby brown dwarf ~0.5″ (0.1 px): only full-resolution centroids see that. And the cost is
reading, not computing: a binned image still needs the full image read from the bucket (no server-side
downsampling of single exposures; the all-sky HiPS maps combine the epochs, so they have no time axis).

So coarse-to-fine **in time and wavelength**, not in pixels, and the first pass **next to the data**:

| Pass | What | Data | Where |
|---|---|---|---|
| 0 | where to look + which exposures: catalogue targets (Gaia/CatWISE high proper motion + brown dwarfs, VSX variables, MPC asteroid tracks) and a sparse exposure set per sky tile (~2 per epoch × detector, matched wavelength) | catalogues + the local image index (T31) | anywhere |
| 1 | per selected exposure: IMAGE + FLAGS only, source extraction (T06), keep the detection list, drop the pixels | ~120k of 1.6M images ≈ 4 TB instead of 107 TB (one image ≈ 12 deg², ~3,400 per full-sky pass per detector and epoch × 6 × 3 × 2) | next to the bucket: us-east4 VM (T47, 38–95 MB/s; ~10 workers ≈ 2–3 h for 4 TB). Only detection lists (few GB) leave AWS |
| 2 | zoom in: tiles where something moved, appeared/vanished, changed brightness at matched λ, or has an odd spectrum → all exposures there, full resolution, forced photometry, spectra (T63), recovery check (T09), injection test | flagged tiles only | university HPC |
| index | candidates per tile with class, score, plain-words reason → Live API → viewer "show me something interesting" + candidate list | few MB | Live API / viewer |

Candidate classes, most interesting first: (1) cold brown dwarf candidates: move between epochs, no Gaia
counterpart, faint at 1–2 µm, methane dip at 3.3 µm, bright at 4–5 µm (WISE 0855 / Eps Ind B as validation);
(2) infrared variables / transients at matched wavelength, not in VSX; (3) spectral outliers (IR excess, ices);
(4) movers within an epoch vs. MPC (mainly recovery statistics: single exposures reach ~V 14–15, T09, so
bright unknown asteroids are suspicious by default).

Pilot before all-sky: the five official fields (built-in validation), one strip across the ecliptic
(asteroid statistics), one high-latitude region (clean brown-dwarf search); a few hundred deg².

Open questions (humans): the HPC's link to AWS (≥ 10 Gbit/s: HPC can do pass 1 too; ≤ 1 Gbit/s: pass 1 on
the VM); which candidate class leads (suggestion: brown dwarfs); who runs the HPC side.

## Findings

## Questions / needs from others
- [to Mati / humans] HPC link to AWS, lead candidate class, who runs the HPC side (see above).

## Handoff

## Notes from others
