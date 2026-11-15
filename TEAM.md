# TEAM

Shared state for all three humans and their agents. Editing rules are in `CLAUDE.md`:
only edit your own Board rows, everything else is append-only, keep both sides on conflicts.

## Pitch

**DRAFT, not agreed yet.** SPHEREx re-images the whole sky about every six months in 102
near-infrared colours. We turn that into a blink comparator anyone can open in a browser: pick a
patch of sky, flip between epochs, and see what moved. Known asteroids and comets are labelled from
JPL data, so whatever moves and is *not* labelled stands out. A "Planet X mode" shows how a slow,
distant body would look across epochs, demonstrated on a real dwarf planet.

## Members & roles

| Track | Area | Folder | Human |
|---|---|---|---|
| A | Data pipeline | `pipeline/` | Joerg |
| B | Detection & science | `detect/` | Jonathan |
| C | Frontend & submission | `web/` | Mati, Jonathan |

## Timeline

Exact times TBD (see Questions / Blockers).

1. **Sat Nov 14, morning**: kickoff, scaffolding, contracts agreed.
2. **Sat Nov 14, evening**: working end-to-end demo with one real target
   (pipeline → detection → viewer).
3. **Sun Nov 15, noon**: feature freeze. After this only fixes, more baked targets, submission.
4. **Sun Nov 15, deadline TBD**: submission (text, demo video, slides, repo link).

## Board

Status is one of `open / doing / review / done / blocked`. Tasks are ≤2h each. Order within a
track is the suggested order; T01, T06 and T11 can start in parallel right now against
`fixtures/targets/demo-synthetic/`.

Active tasks first; finished ones under **Done**, set-aside ones under **Parked** (layout: Decision 2026-11-14,
Mati). When you finish a task, move its row to Done in the same commit.

### Active

| ID | Task | Owner | Status | Branch | Notes |
|---|---|---|---|---|---|
| T94 | C: Missing tiles on the map: failed tiles never asked again (holes until reload), false-colour field epochs 422, holes near the poles when zooming in | Jonathan | doing | `main` | [tasks/T94](tasks/T94-missing-tiles.md) |
| T89 | C/A: Band switching that works on the map (passes per detector, instant within a detector; field epochs per band, builds only the shown detector) + a false-colour layer of all bands (passes and field epochs) | Jonathan | done | `main` | [tasks/T89](tasks/T89-bands-false-colour.md). Reopened: faster false colour (LRGB). `app/` + tilegen/server; per-detector builds touch the build filter |
| T06 | B: Mover detection v0 on the fixture: source extraction per frame, match across frames, keep what moves | Jonathan | doing | `jonathan/T06-mover-detection` | Start on `fixtures/`, switch to real data after T04 |
| T10 | B: "Planet X mode": pick a slow distant body (dwarf planet), check it's detectable across epochs, propose the demo target list | Jonathan | doing | `jonathan/T10-test-targets` | Reworded 2026-11-14 for the official text: check SPHEREx multi-epoch coverage of the five official test fields (Barnard, Eps Indi B, WISE 0855, RW Aur, R Dra) + maybe one dwarf planet; feeds T05 warm-up |
| T14 | C: Deploy: static viewer (e.g. GitHub Pages) + Live API on a host that runs Python, viewer pointed at it (contracts v0.3) | | open | | Needs T11, T18, T20. Reworded 2026-11-14 for live data (was: pre-baked targets, no live API calls) |
| T15 | C: Submission text, data credits and AI-use disclosure | Mati | doing | `mati/T15-submission` | [tasks/T15](tasks/T15-submission.md). Draft in `docs/SUBMISSION.md` |
| T16 | C: Demo video and slides | | open | | After feature freeze |
| T35 | C: Tracing over the stitched sky: paths, per-epoch markers and names of moving / important objects drawn on the explore map (T30/T32), following the epoch blink | Joerg | review | `joerg/T35-sky-traces` | [task file](tasks/T35-sky-traces.md). From Joerg's idea |
| T42 | A/C: Live deep zoom everywhere: order 6-7 SPHEREx tiles computed on demand from AWS level-2 images (band's detector, 3 images, cached row chunks, noise-normalised stretch); IRSA cube up to order 5; S3 404 -> resolve real path, not IRSA cutouts | Jonathan | doing | `jonathan/T42-live-zoom` | Red box = orientation only |
| T60 | A/C: Contamination flags in the viewer: per-frame FLAGS bits exported with the frame, overlay toggle, flag names at the inspected pixel (idea I5) | Joerg | doing | `joerg/T60-flags` | [tasks/T60](tasks/T60-contamination-flags.md). A ~1.5 h + C ~1 h. |
| T61 | B: Appear / disappear / brightness change between epochs, not only motion: sources present in one epoch and not another, or much brighter / fainter (idea I6a) | | open | | [tasks/T61](tasks/T61-appear-vanish-brighten.md). Needs T06 source extraction. |
| T62 | B/C: Candidate ranking + a dedicated candidate list in the viewer: motion significance, consistency across frames, catalogue match, artifact probability from FLAGS (idea I6c) | | open | | [tasks/T62](tasks/T62-candidate-list.md). Partly done: score + reason per detection (T08), unknown first in the objects panel (T13). |
| T67 | B: "Follows the detector, not the sky" artifact rule: a detection fixed in detector pixels while its sky position jumps (ghost, persistence, hot pixel) is an artifact (idea I12) | | open | | [tasks/T67](tasks/T67-detector-artifacts.md). B, `detect/classify.py`. ~1 h. |
| T68 | C: Split the big web files: filter / pairs / playback out of `viewer.js`, sky-map wiring out of `app.js` (pure refactor, browser test guards it) (idea I13) | | blocked | | [tasks/T68](tasks/T68-split-web-files.md). Blocked by T55: refactoring `web/` now would make porting to `app/` harder. |
| T70 | B/C: Motion classes for real detections: asteroid-like / nearby star / distant body from rate, direction and shape, checked on T06 output (idea I15) | | open | | [tasks/T70](tasks/T70-detection-motion-classes.md). Partly done: classes for labels (T23), status + reason incl. class for detections (T08). |
| T87 | B: What it is, from the bands: temperature, IR excess, ices (3.0 / 4.27 / 4.67 µm), CH4 3.3 and H2O 1.4 / 1.9 µm (brown dwarfs), CO 2.3 µm, PAH 3.3, Pa-α / Br-α, galaxy 1.6 µm bump; per source a class or hint | Joerg | open | | [tasks/T87](tasks/T87-band-features.md). Needs T85; after T86 |

### Parked

| ID | Task | Owner | Status | Branch | Notes |
|---|---|---|---|---|---|
| T73 | A: Discovery survey pass 0 + pilot: catalogue targets and a sparse exposure set per sky tile (~2 per epoch × detector, matched λ) as a manifest for pass 1; pilot regions chosen | Mati | blocked | `mati/T73-survey-pilot` | [tasks/T73](tasks/T73-survey-plan.md). Contains the survey design for T73–T76. Suggested owner: Joerg (catalogues, labels). **Parked (Decision 2026-11-14, Mati: visualization only).** |
| T74 | A/B: Discovery survey pass 1 next to the bucket: per manifest exposure read IMAGE + FLAGS, extract sources (T06), keep detection lists per tile, drop pixels; runs on the us-east4 VM | Mati | blocked | `mati/T73-survey-pilot` | [tasks/T74](tasks/T74-survey-pass1.md). Suggested owner: Jonathan (T06 extractor, VM). **Parked (Decision 2026-11-14, Mati: visualization only).** |
| T75 | B: Discovery survey pass 2 (HPC): flag tiles from the pass-1 lists (moved / appeared / changed at matched λ / odd spectrum), then all exposures there at full resolution, forced photometry, spectra, candidates with class + score + reason | Mati | blocked | `mati/T73-survey-pilot` | [tasks/T75](tasks/T75-survey-pass2.md). Suggested owner: whoever runs the HPC (Joerg or Jonathan). **Parked (Decision 2026-11-14, Mati: visualization only).** |

### Done

| ID | Task | Owner | Status | Branch | Notes |
|---|---|---|---|---|---|
| T96 | C/A: Chemistry maps combined: tick up to 3 features at once; one = the grey map as before, two or three = a colour picture (shortest wavelength blue, longest red; emission for the lines and PAH, absorption depth for the ices and water), with false colour and the automatic blink | Mati | done | `mati/T96-chemistry-combine` | [tasks/T96](tasks/T96-chemistry-combine.md). Follows T93 |
| T55 | C: UI redesign under `/app/` (copy of `web/`); `web/` and `/web/` stay as they are for all other work | Jonathan | done | `main` | [tasks/T55](tasks/T55-app-ui.md). UI work only; everyone else keeps working in `web/` Merged into `/web/` (T90); `app/` deleted. |
| T01 | A: IRSA query: list all SPHEREx exposures covering an RA/Dec (SIA/TAP), with time, detector, access URL | Joerg | done | `joerg/T01-irsa-query` | `python -m pipeline.query --ra .. --dec ..`; COSMOS: 214 images, 3 epochs |
| T02 | A: Download cutouts for one target into `data/`, with a cache so re-runs don't re-download | Jonathan | done | `jonathan/T02-T04-build` | Needs T01 |
| T03 | A: Align cutouts to one common WCS grid (north up) and get the wavelength at the target position per frame | Jonathan | done | `jonathan/T02-T04-build` | Needs T02. Wavelength varies across a SPHEREx image |
| T04 | A: Render frames to PNG/WebP and write `target.json` per CONTRACTS, validated against the schema | Jonathan | done | `jonathan/T02-T04-build` | Needs T03. First real target = end-to-end milestone |
| T05 | A: Pre-build (warm) the five official test fields in the Live API cache so the demo opens them instantly (was: publish to `web/targets/`; changed by the live-data decision) | Mati | done | `mati/T05-warm` | [tasks/T05](tasks/T05-warm-demo-fields.md). `python web/warm.py` (or `dev.py --warm`) on the demo machine |
| T07 | B: JPL SB Identification cross-match: known small bodies in the field per frame time → `known_objects` | Mati | done | `mati/T07-jpl-known` | [tasks/T07](tasks/T07-jpl-known-objects.md). `python -m detect.known_objects <dir>`; not yet called by builds (needs detect.run, T06) |
| T08 | B: Classify detections as known / unknown / artifact and write them into `target.json` | Mati | done | `mati/T08-classify` | [tasks/T08](tasks/T08-classify-detections.md). `python -m detect.classify <dir>`; waits for T06 detections; CONTRACTS v0.9 `reason` |
| T09 | B: Sanity check on a known bright asteroid in real SPHEREx data: do we recover it at the JPL position? | Mati | done | `mati/T09-known-check` | [tasks/T09](tasks/T09-known-check.md). Needs T04, T08 (detections replaced by a direct check at the predicted positions until T06) |
| T11 | C: Static viewer skeleton: load `index.json` + `target.json` from the fixture, show frames, blink between two | Mati | done | `mati/T11-viewer-skeleton` | [tasks/T11](tasks/T11-viewer-skeleton.md). Vanilla JS, no build. Reads static target folders; not yet wired to the Live API (v0.3). Run: see `web/README.md` |
| T12 | C: Epoch timeline and band/wavelength filter | Mati | done | `mati/T12-timeline-filter` | [tasks/T12](tasks/T12-timeline-filter.md). Timeline per epoch (y = λ), λ/detector filter, v0.2 pairs, `M` = match B to A's λ |
| T13 | C: Overlay detections and known objects, with a clear "synthetic" badge where it applies | Mati | done | `mati/T13-objects-panel` | [tasks/T13](tasks/T13-objects-panel.md). Objects panel + headline count; paths on the image are T22 |
| T17 | A: Compute wavelength-matched `pairs` across epochs (+ `bandwidth_um`) in `target.json` (contracts v0.2) | Joerg | done | `joerg/T17-pairs` | Taken back: the viewer (T12) reads `pairs` but `pipeline.build` writes none. `pipeline/pairs.py` + one call in build.py |
| T18 | C: Live API service: `GET /api/target?ra=&dec=&size=` builds (pipeline + detect) or serves from cache, progress while building, CORS (contracts v0.3) | Jonathan | done | `jonathan/T18-live-api` | `python -m server [--fixture]`, see `server/README.md`. Live mode works once `pipeline.build` (T02–T04) exists; until then `--fixture` |
| T19 | A: Labels on the images: catalogue names/positions (SIMBAD, Gaia DR3 with proper motion) into `target.json` | Joerg | done | `joerg/T19-labels` | [task file](tasks/T19-labels.md). `pipeline/labels.py`; viewer side is T13 |
| T20 | C: Viewer ↔ Live API: RA/Dec/size input, `?ra=&dec=&size=` in the page URL, request + poll with progress, load from `target_url`, quick picks for the official test fields (contracts v0.3) | Mati | done | `mati/T20-live-api-client` | [tasks/T20](tasks/T20-live-api-client.md). Run: `web/README.md` (API :8000, viewer :8080). Test fields in `web/presets.json` |
| T21 | C: Everyone can run the viewer locally: one-command launcher (API + viewer), README run steps for Linux/macOS/Windows | Mati | done | `mati/T21-run-kit` | [tasks/T21](tasks/T21-run-kit.md). `python web/dev.py`, setup in README "How to run" |
| T22 | C: Movement paths in the viewer: line + tick per frame, early→late colour, current position + name, labelled exaggerated arrow for slow movers | Joerg | done | `joerg/T22-movement-paths` | [task file](tasks/T22-movement-paths.md). From the "Draw paths" idea. Hover/click info on labels |
| T23 | A: Labelling over time: labels that follow moving objects, motion summary + motion class per object, trail image, shift-and-stack | Joerg | done | `joerg/T23-labels-over-time` | [task file](tasks/T23-labels-over-time.md). Umbrella for T19 (done) + T22; from 4 Ideas. Closed 2026-11-14: labels already follow every object in every frame of every epoch; the last step was dropped |
| T24 | All: Pin exact dependency versions so everyone runs the same | Joerg | done | `joerg/T24-pin-deps` | Lock files at root; README "Dependencies". Python 3.12+ |
| T25 | C: Default field in the form (Barnard's Star) + hint that RA/Dec/field of view can be changed | Mati | done | `mati/T25-form-defaults` | [tasks/T25](tasks/T25-form-defaults.md). Default = `"default": true` in `web/presets.json` |
| T26 | A: Builds survive IRSA throttling: retry 503/timeouts with backoff, one shared download limit across concurrent builds (no frames dropped) | Jonathan | done | `jonathan/T26-T28-speed` | Measured: IRSA answers `503 Server busy`, frames were silently dropped |
| T27 | A: Cache the IRSA exposure list per position (disk, TTL) and drop the server's duplicate query, so FOV changes skip TAP | Jonathan | done | `jonathan/T26-T28-speed` | TAP took 19 s for a trivial query today |
| T28 | A: Reuse cached cutouts across FOV changes (a larger cached cutout serves a smaller FOV; minimum size bucket) | Jonathan | done | `jonathan/T26-T28-speed` | 82% of each 4.6 MB cutout is the EPSF table, independent of FOV |
| T29 | C: RA/Dec help as a popup bubble under the form (built, switched off for now; on for the demo) | Mati | done | `mati/T29-form-tip` | [tasks/T29](tasks/T29-form-tip.md). Off: `FORM_TIP_ENABLED` in `web/app.js`; preview `?tip=1`; switch on for T16 |
| T30 | C: Explore mode (R1): Aladin Lite v3 in the viewer with the CDS SPHEREx HiPS (`CDS/P/SPHEREx/QR2/D1`..`D6`, all-sky, combined epochs) + Gaia/WISE overlays; click a spot → per-epoch blink via the Live API | Jonathan | done | `jonathan/T30-explore` | Instant pan/zoom today; HiPS is not split by epoch |
| T31 | A: Local mirror of the SPHEREx image index (1.6 M ObsCore rows: footprint, time, detector, wavelength, FITS URL) in SQLite with a HEALPix index, refreshed per data release (R4) | Jonathan | done | `jonathan/T31-index-mirror` | TAP: 9-19 s per search today, 136 s for a COUNT(*) |
| T32 | A: Per-epoch HiPS tiles (R2/R3): build HEALPix tiles per epoch x detector from full images for chosen regions (warm the 5 official fields first), served by `server/` as extra Aladin layers, epoch switch = blink | Jonathan | done | `jonathan/T32-epoch-hips` | Full images cover ~12 deg2 each, far less waste than 36 cutouts per 15' |
| T33 | A: Read SPHEREx images from the AWS Open Data bucket (`nasa-irsa-spherex`, same paths as IRSA) with HTTP Range: only headers + the rows around the field of IMAGE/FLAGS + WCS-WAVE, no EPSF; IRSA cutouts as fallback | Jonathan | done | `jonathan/T33-s3-range` | Measured S3 5-7 MB/s, 0 errors vs IRSA 0.31 MB/s, >50% 503 |
| T34 | C: Label priority: always show only the most important names (field's object, movers, known asteroids, notable motion), the rest on hover; cap + "show all" toggle | Joerg | done | `joerg/T34-label-priority` | [tasks/T34](tasks/T34-label-priority.md). Mati: labels too crowded on real fields. Builds on T23 `paths.js` |
| T36 | C: Own sky map as the main view (no Aladin, no dependency): WebGL HiPS renderer (HEALPix tiles, SIN projection), drag/zoom/pinch like Google Earth, SPHEREx epochs as layers, blink in the map; frame viewer stays below as detail | Jonathan | done | `jonathan/T36-sky-map` | Replaces the T30 Aladin panel |
| T37 | A/C: Catalogue labels only on request: builds skip labels; `GET /api/targets/<id>/labels` computes them in the background; viewer has a Labels switch | Jonathan | done | `jonathan/T36-sky-map` | SIMBAD labels cost 30 s in deep fields (labels.py untouched) |
| T38 | A: Fast labels: vectorised tracks (all objects x frames at once), ranked cap of 400 SIMBAD + 400 Gaia per field, grid-based duplicate merge, SIMBAD + Gaia in parallel, 15 s per mirror | Joerg | done | (merged as e715788) | Deep field (COSMOS, 30,785 SIMBAD objects): 23 s -> 5.5 s, labels 50+ MB -> 1.2 MB. Official fields: same important labels |
| T39 | A: Wide per-epoch stitch test (reference): full 3.5° images from AWS, one mosaic per epoch over ~6°, HiPS, page with region-wide labels + traces | Joerg | done | `joerg/T39-wide-stitch` | `pipeline/reference/wide_stitch/` (README, `run.sh`). Input for T32/T36 (Jonathan) |
| T40 | C: Labels on by default + switch everywhere: default ON (remembered per browser), works in live/offline/`?explore=0`, second Labels switch next to the path controls | Joerg | done | `joerg/T40-labels-on` | Without labels the paths, names, inspector and sky-map traces had nothing to draw |
| T41 | C: Faster map images: server-side HiPS tile cache + prefetch (neighbours, children, Allsky), browser skips stale tiles and loads the centre first, epoch tiles cached and pre-rendered | Jonathan | done | `jonathan/T41-fast-tiles` | IRSA tiles 0.7 s first byte, Allsky 4.3 s, HTTP/1.1 (6 per browser) |
| T43 | C: Difference view A − B in the viewer (challenge: "subtract images taken at different times"): stars cancel for matched pairs, movers show as white/black pairs | Mati | done | `mati/T43-difference` | [tasks/T43](tasks/T43-difference-view.md). Button "A − B" / key `D`; best with a matched pair |
| T45 | C: Play the series like a video (core Objective): Play/Pause through all frames in the filter or one per epoch at matched wavelength, speed + loop | Mati | done | `mati/T45-play` | [tasks/T45](tasks/T45-play-series.md). "▶ Play all" / key `P`; modes: all frames in the filter, 1 per epoch at A's λ |
| T46 | All: tests on every push (GitHub Actions): pytest + browser test (fixture mode) + fixture schema check | Mati | done | `mati/T46-ci` | [tasks/T46](tasks/T46-ci.md). `.github/workflows/tests.yml`; first run: check the Actions tab |
| T47 | All: Live tile generator (`tilegen/`) on Google Cloud `us-east4` next to the AWS SPHEREx bucket; viewer/API/builds stay local (EU); Tiles switch local/US VM | Jonathan | done | `jonathan/T47-gcp` | From Jonathan's idea. Measure S3 throughput on the VM first |
| T48 | C: Cached Allsky fallback at deep zoom so pending/failed live tiles never erase available overview imagery | Joerg | done | `joerg/T48-map-overview-fallback` | [tasks/T48](tasks/T48-map-overview-fallback.md). User approved implementation + push; investigate repeated tile errors |
| T49 | A/C: Light curves + spectra on the fly at any position: aperture photometry on the cached SPHEREx FITS (pipeline + `/api/targets/<id>/photometry` + viewer charts); for the variable test stars RW Aur / R Dra | Mati | done | `mati/T49-photometry` | [tasks/T49](tasks/T49-photometry.md). `/api/targets/<id>/photometry`; panel under the timeline; CONTRACTS v0.10 |
| T50 | All: `web/dev.py --host ADDR`: serve viewer + Live API on one address only (e.g. WireGuard 10.0.0.2) instead of all interfaces (`--lan`) | Joerg | done | `joerg/T50-dev-host` | [tasks/T50](tasks/T50-dev-host.md). Joerg's new host serves the team over WireGuard 10.0.0.0/24 |
| T51 | B: `detect/run.py` so builds get known asteroids/comets now: JPL lookup (T07) + classify (T08) after every build; mover detection (T06) plugs into the same function later | Joerg | done | `joerg/T51-detect-run` | [tasks/T51](tasks/T51-detect-run.md). Builds call `detect.run.detect()` but the module never existed, so every field had 0 objects. Jonathan: T06 adds tracks here |
| T52 | A: More labels (idea I4 + more): VSX variable stars (type, period, range), CatWISE2020 brown dwarfs / high proper motion (moved to frame time), planets + bright moons (seen from SPHEREx) | Joerg | done | `joerg/T52-more-labels` | [tasks/T52](tasks/T52-more-labels.md). New label `source` values + optional `note` (CONTRACTS v0.11) |
| T53 | B: Comets in the local orbit catalogue (MPC CometEls.txt), like the asteroids in T51 | Joerg | done | `joerg/T52-more-labels` | [tasks/T53](tasks/T53-local-comets.md). SkyBoT fallback had comets, the local path not yet |
| T54 | A/C: Known objects + labels start while the images download (they need only frame times + field geometry), so a new field is complete when its frames are | Joerg | done | `joerg/T52-more-labels` | [tasks/T54](tasks/T54-early-objects-labels.md). New field: frames 11 s, objects +2.5 s, labels +2-3 s today |
| T56 | All: Docs match the code (idea I2): README status/run/how-it-works, CONTRACTS without pre-baked `web/targets/` + `pipeline.publish`, undocumented API routes, a schema-0.2 fixture with pairs/labels/varied detections | Mati | done | `mati/T52-docs-current` | [tasks/T56](tasks/T56-docs-current.md). Was claimed as T52, then T55 (ID clashes with Joerg's T52, Jonathan's T55). Also: classify fix for SkyBoT/MPC, tilegen tests in CI |
| T57 | A: Faster "Show": the US VM (tilegen, `us-east4`) reads + cuts the SPHEREx images next to the bucket and sends only the small cutout FITS (gzip); build/photometry/caches stay local; fallback S3, then IRSA | Jonathan | done | `jonathan/T57-vm-cutouts` | [tasks/T57](tasks/T57-vm-cutouts.md). Fresh 15' field: 52.8 s → 19.9 s. Default on; `--cutouts-remote none` turns it off |
| T58 | All: Limits before a public deploy: rate limit per IP, cap on concurrent builds, `refresh=1` only with a token, cache size cap with eviction (idea I1) | Joerg | done | `joerg/T58-public-limits` | [tasks/T58](tasks/T58-public-limits.md). Server side, ~1 h. Suggested owner: Jonathan (server). |
| T59 | A/C: Per-detector co-adds per epoch: mean/median of the aligned frames per detector and epoch as extra frames, for faint red sources (idea I3) | Mati | done | `mati/T59-stacks` | [tasks/T59](tasks/T59-coadds.md). A ~2 h + C ~0.5 h. Works best together with T66 (more frames per field). |
| T63 | C/A: Spectrum context: what a normal source looks like, and why a deviation is interesting (expected baseline + feature markers on the T49 chart) (idea I8) | Mati | done | `mati/T63-spectrum-context` | [tasks/T63](tasks/T63-spectrum-context.md). Rephrased from idea I8 (feature markers) by Mati: know what normal looks like, then explain anomalies. C `web/photometry.js` + maybe a small fit in `pipeline/photometry.py`. |
| T64 | A/C: Data release in the UI: release per frame (DR1 / QR3) in target.json, shown in frame info, "newer data available: rebuild" when a cached field is older (idea I9) | Mati | done | `mati/T64-data-release` | [tasks/T64](tasks/T64-data-release.md). |
| T65 | A/C: Auto target selection: propose interesting fields (high proper-motion stars, brown dwarfs, asteroids passing through, fields with unknown movers, "surprise me") (idea I10) | Mati | done | `mati/T65-auto-targets` | [tasks/T65](tasks/T65-auto-targets.md). From Joerg's idea. |
| T66 | A: Fuller spectra from all exposures: photometry on every exposure covering a position (not only the 36 frames kept for blinking), cached per position (idea I11) | Joerg | done | `joerg/T66-fuller-spectra` | [tasks/T66](tasks/T66-fuller-spectra.md). ~2 h. Suggested owner: Jonathan (index + S3). |
| T69 | C: Shift-and-stack in the viewer: stack the frames along an object's motion (or a guessed one), faint movers sharpen, stars smear (idea I14) | Mati | done | `mati/T69-shift-stack` | [tasks/T69](tasks/T69-stack-in-viewer.md). Partly done: `pipeline.stack` (T23). |
| T71 | All: the Live API sets up its own data on start, in the background: MPC orbit catalogue (T51/T53, refreshed weekly) and the SPHEREx image index (T31) when missing; builds use the fallbacks until ready | Joerg | done | `joerg/T71-auto-data` | [tasks/T71](tasks/T71-auto-data.md). Teammates no longer need the one-time setup commands |
| T72 | C: Catalogue names anywhere on the explore map (not only the shown field's movers): `GET /api/sky-labels` (SIMBAD, VSX, CatWISE, cached per 0.25 deg cell), drawn when zoomed in to 2 deg, names where they fit, dots + hover for the rest | Joerg | done | `joerg/T72-map-labels` | [tasks/T72](tasks/T72-map-labels.md). Joerg: "why can't I see the labels in the explorer?" |
| T76 | C: Discovery index in the viewer: candidates per tile from the survey served by the Live API; "Show me something interesting" + candidate list, each opening its field with blink, spectrum and reason | Mati | done | `mati/T76-discovery-index` | [tasks/T76](tasks/T76-discovery-index.md). Suggested owner: Mati. Can start on a synthetic sample index. **Removed again (Decision 2026-11-14, Mati: visualization only).** |
| T77 | B: (merged into T74/T75, the same survey; measured scope + per-band plan moved to tasks/T74 Notes) | Joerg | done | | [tasks/T77](tasks/T77-sky-survey-hpc.md) |
| T78 | C: Type an exact wavelength: a µm input next to the sky map's band slider (snaps to the nearest of the 102 channels, shows its exact centre) and "frames at λ" in the blink viewer (A/B = the frames nearest that wavelength in two epochs) | Mati | done | `mati/T78-wavelength-input` | [tasks/T78](tasks/T78-wavelength-input.md). Mati's request; needs porting to `app/` (T55) |
| T79 | C: Click to measure: a plain click on the frame image measures that star (no "Measure a star" mode needed); a click anywhere on the explore map gives the spectrum + light curve of that sky point from all exposures, field or not (`GET /api/photometry?ra=&dec=`) | Joerg | done | `joerg/T79-click-spectrum` | [tasks/T79](tasks/T79-click-spectrum.md). Joerg: "nothing happens if I click on a pixel". `/app/` (T55): note for Jonathan |
| T80 | C: Map only in `/web/`: the explore map is the one view of the sky; frame image, blink controls, wavelength filter, timeline and frame panels hidden (still in the code: `?frames=1`, offline `?data=`, `?explore=0`); spectra via map clicks (T79) | Joerg | done | `joerg/T80-map-only` | Joerg: "why are there two maps, let's only have the navigator". `/app/` migration later (Jonathan, T55) |
| T81 | C: Frame viewer features in the map: single frames and A − B as field layers (`/api/hips/<id>/f<frame>`, `/d<a>-<b>`), the viewer's A/B, blink, play, λ filter and timeline drive the map | Joerg | done | `joerg/T81-map-frames` | [tasks/T81](tasks/T81-map-frames.md). Touches server/hips.py + web/explore.js (Jonathan's map) |
| T82 | A/C: Blink survey passes anywhere on the map: live tiles per 6-month pass (`spherex-live-p<n>`), "Blink passes" when zoomed in, not only inside a built field | Joerg | done | `joerg/T81-map-frames` | [tasks/T82](tasks/T82-blink-passes.md). Touches tilegen + skycache (Jonathan); the US VM needs a redeploy for pass tiles, local until then |
| T83 | A: Faster spectra (T66): 7 dependent S3 range requests per image (~2 s, all latency from Europe), CPU under the GIL: 16 worker processes x 8 threads, S3 directly (VM answered 502), bucket listing instead of IRSA cutouts for moved images | Joerg | done | `joerg/T83-fast-spectra` | [tasks/T83](tasks/T83-fast-spectra.md). Fresh point 20-65 s -> 5.5-6 s (10 s right after a server start) |
| T84 | B: Spectral anomalies: a point that jumps out of its epoch's smooth spectrum (passing asteroid? artefact?), a jump at the same wavelength between epochs, a change of shape; checked against known asteroids at that time; highlighted in the spectrum with a plain-words reason | Joerg | done | `joerg/T84-spectral-anomalies` | [tasks/T84](tasks/T84-spectral-anomalies.md). Same code later on the HPC (T75) |
| T85 | A: Spectra for a whole field: one pass over every exposure covering a field, photometry at every catalogue source at once (cost = reading the exposures, not the number of stars), cached per field | Joerg | done | `joerg/T85-field-spectra` | [tasks/T85](tasks/T85-field-spectra.md). Feeds T86, T87, T75 |
| T86 | B: Spectral outliers: sources whose spectral shape is out of distribution for their field (field's own model of an ordinary star, calibrated scatter, only consistent deviations), ranked with a plain-words reason; second opinion from the catalogue prediction (idea I23) | Joerg | done | `joerg/T85-field-spectra` | [tasks/T86](tasks/T86-spectral-outliers.md). Needs T85 |
| T88 | C: Unusual spectra on the map: "Unusual spectra" toggle in the map bar (measures the field if needed), rings + rank on the outliers, click → card with the reason, spectrum and charts; linked to the T86 panel | Joerg | done | `joerg/T88-outliers-map` | [tasks/T88](tasks/T88-outliers-map.md). Uses explore.js's public draw hook only, no change to the map code |
| T91 | A: Measured motion of the official targets: each star's position fitted in every epoch (deep per-epoch stacks of its own exposures), proper motion with error from SPHEREx alone, compared with Gaia / the catalogue ("SPHEREx says 10.3″/yr, Gaia 10.4") | Joerg | done | `joerg/T91-measured-motion` | [tasks/T91](tasks/T91-measured-motion.md). Barnard, Eps Indi B, WISE 0855 |
| T92 | C: Guided tour of the five official targets: one click per stop opens the field, sets the layer, starts the blink and shows one sentence of what to watch | Joerg | done | `joerg/T92-tour` | [tasks/T92](tasks/T92-guided-tour.md). After T90 (web/ layout) lands |
| T90 | C: Merge `/app/` (T55 redesign) back into `/web/`: first screen = the app/ map (automatic blink, floating panels), scroll down for every web/ widget (frame viewer, analysis, spectra, outliers…); nothing dropped from either | Jonathan | done | `jonathan/T90-merge-app-web` | [tasks/T90](tasks/T90-merge-app-into-web.md). Touches all of web/ |
| T95 | C: T90 follow-ups not covered by T94: browser test red since T90 (coordinate form moved: `input[name=ra]`), the viewer's field object without its labels | Joerg | done | `joerg/T95-t90-followups` | [tasks/T95](tasks/T95-t90-followups.md). Asked by Joerg; Jonathan informed |
| T97 | All: Cache cap for team servers too: `SPHEREX_CACHE_GB` / `--cache-gb` keeps the caches under a size without `--public`, tile row chunks (`data/raw/s3chunks`) included; this host's disk ran full on 2026-11-15 | Joerg | done | `joerg/T97-cache-cap` | [tasks/T97](tasks/T97-cache-cap.md) |
| T93 | C/A: Chemistry maps: continuum-subtracted feature images for the shown field (water / CO₂ / CO ice, PAH, hydrogen lines): the image at the feature minus the continuum from neighbouring wavelengths, as a map layer + in the frame viewer | Mati | done | `mati/T93-chemistry-maps` | [tasks/T93](tasks/T93-chemistry-maps.md). From the cached FITS cutouts (real fluxes, per-pixel wavelength); visualization only |

## Decisions

Dated, one line each, with why.

- 2026-11-14 **PROPOSED** (not agreed yet): Architecture is a Python pipeline (astropy,
  astroquery/pyvo) that writes static frames + one `target.json` per target → detection step adds
  `known_objects` and `detections` to that JSON → static frontend reads only that JSON.
  Why: three tracks can work in parallel against a fixture, and the demo doesn't depend on live APIs.
- 2026-11-14 **PROPOSED** (not agreed yet): `docs/CONTRACTS.md` v0.1 (per-target JSON schema,
  folder layout, entry points). Why: gives all tracks a fixed interface from the first hour.
- 2026-11-14 Tracks for now: Joerg = A (pipeline), Jonathan = B (detection), Mati = C (frontend
  & submission). Why: agreed at kickoff; may change later.
- 2026-11-14 **PROPOSED** (not agreed yet): CONTRACTS v0.2 adds optional `pairs`
  (wavelength-matched frames across epochs), per-frame `bandwidth_um`, and alpha 0 for no-data
  pixels. Why: no two SPHEREx frames share a wavelength (LVF stepping), so star brightness changes
  between arbitrary frames; only matched pairs compare like with like. Alpha answers Mati's
  no-data question. Additive only, v0.1 readers keep working; schema accepts "0.1" and "0.2".
- 2026-11-14 **PROPOSED**: v0.2 pair tolerance is 0.5 x bandwidth, not 0.25. Why: on COSMOS D2,
  0.25 gives 7 pairs, 0.5 gives 21, 0.75 adds none; the remaining offsets are ~1/3 channel and the
  pair differences still cancel stars cleanly (checked by eye on 5 pairs).
- 2026-11-14 Jonathan also works on track C (alongside B). Why: people claim tasks, not tracks;
  the track only says which folder a task lives in.
- 2026-11-14 [Jonathan] **DECIDED by Jonathan, Joerg + Mati please ack:** the tool serves *live*
  SPHEREx data for any RA/Dec the user enters, fetched from IRSA on request and cached, not
  pre-baked targets. Why: the official Objectives say users enter coordinates and get that patch
  as a video; pre-baked only would miss the core requirement. Replaces "no live API calls" in the
  PROPOSED architecture; CONTRACTS needs a v0.3 (request API + cache) before code depends on it.
- 2026-11-14 [Jonathan] Live data is **final**, no ack needed. CONTRACTS v0.3 adds the Live API
  (`server/`, T18): `GET /api/target?ra=&dec=&size=` → build or cache hit, `/api/jobs/<id>`
  progress, `/api/targets/<id>/...` serves the unchanged target folder. Why: official Objectives
  require user-entered coordinates; target folder format stays as-is so A/B code is unaffected.
  Impact: T05 becomes cache warm-up of the five named test fields, T14 needs a host that runs Python.
- 2026-11-14 [Joerg] Decisions no longer need acks: whoever decides writes a dated line here and
  it holds. Agents keep the repo consistent with every decision (rules in CLAUDE.md). So CONTRACTS
  v0.2 (pairs, bandwidth, alpha no-data) and v0.3 (live API) are both in effect.
- 2026-11-14 [Joerg] Every task gets a file `tasks/T<id>-<slug>.md` for details and communication;
  the Board stays the one-line index. Why: Board rows are too short for findings and requests.
- 2026-11-14 [Mati] Agrees with the architecture and CONTRACTS v0.1 (closes the Questions item).
  Why: Mati's answer; per Joerg's line above no ack is needed, v0.2 + v0.3 are in effect.
- 2026-11-14 [Joerg] CONTRACTS v0.4: optional `labels` in `target.json` (SIMBAD names + Gaia DR3
  stars, position per frame with proper motion), written by `pipeline.labels`. `schema_version`
  stays "0.2" so existing readers keep working. Why: official targets are fast-moving stars;
  labels that follow them make motion visible. Details: tasks/T19-labels.md.
- 2026-11-14 [Joerg] All Python dependencies pinned exactly (`==`); install from `requirements.lock`
  (app) or `requirements-dev.lock` (tests). Minimum Python is now **3.12** (was 3.11). Why: same
  versions for everyone; numpy 2.5 needs 3.12. Checked: fresh 3.14 venv installs from the lock with
  plain pip, `pytest server` 11 passed, `web/dev.py` serves API + viewer. Updating: README "Dependencies".
- 2026-11-14 [Joerg] Ideas "Draw paths", "Motion classification", "Trail image" and
  "Shift-and-stack" are on the Board now: T22 (paths) and T23 (the rest).
- 2026-11-14 [Jonathan] **REQUIREMENT: Google-Earth-style exploring.** Users pan/zoom freely over the
  sky and blink epochs anywhere. Targets: (R1) after a pan/zoom, visible tiles in <= 0.5 s anywhere on
  the sky; (R2) switching epoch <= 0.1 s (preloaded); (R3) per-epoch SPHEREx detail at a new spot:
  first frames <= 10 s, complete <= 60 s, FOV change <= 2 s; (R4) image search <= 0.2 s.
  Why/maths: a 1600x1000 px view at native 6.15"/px is 2.7 x 1.7 deg = 4.7 deg2, i.e. ~75x a 15'
  field. Cutouts today: 166 MB per 15' field, 434 s cold (IRSA throttles to ~0.4 MB/s), so one
  full view live would take hours: ~10^4x too slow. Pan/zoom must come from pre-tiled HiPS
  (12-30 tiles of 512 px, ~150 KB each per view, ~5 MB/s while panning); live cutouts only for
  the per-epoch detail. Plan: T30-T32.
- 2026-11-14 [Joerg] CONTRACTS v0.5: labels carry an optional `motion` summary (shift, reach, rate,
  direction, class `still` / `proper motion` / `fast mover` / `distant body?`, plain-words note) from
  the new `pipeline/motion.py`. Why: the viewer can say *how* something moves, not just where it is
  (T23). `summarize()` takes any per-frame positions, so B can reuse it for detections.
- 2026-11-14 [Jonathan] CONTRACTS v0.6: Live API serves per-epoch HiPS tiles (`/api/hips/...`, T32) so
  Aladin Lite can blink epochs in the map. Why: requirement R2 (epoch switch <= 0.1 s) in the
  explore view; additive, nothing existing changes.
- 2026-11-14 [Joerg] CONTRACTS v0.7: labels carry `importance` (0 field object … 4 Gaia-only) and
  `aliases` (duplicates within 3" merged). Why: real fields had 40-270 labels; the official target
  WISE 0855 was hidden because its SIMBAD name looks like a catalogue number (T34).
- 2026-11-14 [Joerg] T38: `pipeline/labels.py` keeps at most 400 SIMBAD objects (ranked: notable motion
  + the field's object always, then notable types, classic names, other names, catalogue numbers,
  nearest the centre first) and the 400 brightest Gaia stars (G < 16). Why: deep fields returned
  ~30,000 objects; labelling took 23-30 s and wrote 50+ MB of labels. Now 1-7 s, mostly network.
- 2026-11-14 [Jonathan] CONTRACTS v0.8: catalogue labels only on request (Labels switch → `GET
  /api/targets/<id>/labels`, `labels_requested` in target.json); builds write `labels: []`. Why: Jonathan
  wants the work to happen only when labels are switched on; SIMBAD labels took 30 s in deep fields.
  Also T36: the sky map is our own WebGL HiPS renderer (`web/sky.js`, `web/healpix.js`), Aladin Lite is
  gone. Joerg: `web/traces.js` now paints via a sky.js draw hook (only `draw()` changed, selection kept).
- 2026-11-14 [Joerg] T40: catalogue labels are ON by default again (was OFF since T37). Why: T38 made
  labelling 1-7 s and T37 already fetches them in the background without blocking the field; with
  labels off the paths, names, inspector and sky-map traces (T22/T23/T35) showed nothing, so the
  tracking looked missing. The choice is remembered per browser (localStorage `spherex.labels`).
- 2026-11-14 [Mati] CONTRACTS v0.9: optional `detections[].reason`, one plain-words sentence why a detection
  is known / unknown / artifact, written by `detect.classify` (T08) and shown in the objects panel. Why: an
  "artifact" or "unknown" label alone can't be checked by a human; the reason makes it checkable.
  Additive, `schema_version` stays "0.2".
- 2026-11-14 [Mati] CONTRACTS v0.10: `GET /api/targets/<id>/photometry` (T49), aperture photometry at a position in
  every frame (flux in µJy, wavelength/bandwidth at the star, masked flag). Why: the official test targets include
  two variable stars and "spectra on the fly" is the extra-kudos item; both need calibrated fluxes, not PNGs.
  New endpoint only; target.json unchanged; synthetic targets answer 200 `no_data`.
- 2026-11-14 Jonathan: The UI redesign happens in a new folder `app/` (URL `/app/`, served by
  `web/dev.py`), a copy of the viewer in `web/`. **This is only for UI work (T55).** All other work
  (features, fixes, API wiring, tests) stays in `web/` and `/web/` exactly as before; `/web/` stays
  the default URL and the working demo. Why: the UI can be reworked without blocking the others.
- 2026-11-14 Mati: CONTRACTS v0.11 (T56): the file now matches the code. Removed pre-baked `web/targets/`, its size budget and `pipeline.publish` (obsolete since v0.3 live data); documented the Live API routes the viewer already uses (`/objects`, `/sky/…`, `/settings`, `/health`), `labels_requested` / `objects_requested`, the real `build_target` / `detect` signatures; label `source` may be `"synthetic"` (fixtures only, viewer marks it not real); second fixture `fixtures/targets/demo-epochs/` (schema 0.2, every optional field). Additive, no code has to change.

- 2026-11-14 [Joerg] CONTRACTS v0.12: label sources `vsx`, `catwise2020`, `horizons` + optional `note`,
  `mag_band`; `known_objects[].source` `mpcorb`; the server starts `/objects` (known objects) itself
  after each build. Why: name variables, brown dwarfs and planets (official targets include two
  of each kind), and known asteroids no longer hold up builds (T51, T52). Additive.
- 2026-11-14 Jonathan: The team VM (`us-east4`) now also cuts the SPHEREx images for builds (T57,
  `GET /cutout`), not only map tiles; build, detection, photometry and all caches stay local. Default on
  for `python -m server` / `web/dev.py`. Why: a new field took ~45-53 s, ~35 s of it pulling whole
  detector rows over the Atlantic; via the VM 19.9 s. Supersedes "only tiles run on the VM" (T47).

- 2026-11-14 [Joerg] `/web/` shows only the explore map by default (T80); the frame viewer stays behind
  `?frames=1` (also offline `?data=` and `?explore=0`, which the CI browser test uses). Why: two images of the
  same sky confused; the map has the field's epochs, traces, names and click-for-spectrum. Jonathan moves
  this to `/app/` later.
- 2026-11-14 Jonathan: Field size limit of the Live API raised from 60′ to 210′ (CONTRACTS `size`).
  Why: the 60′ had no stated reason (set in T18 when cutouts came from IRSA's slow cutout service);
  210′ is the real bound, one SPHEREx detector image (2040 px × 6.15″ = 3.49°). Larger fields build
  slower. The team VM's /cutout accepts up to 6° cutouts. `web/` keeps its own 60′ form limit.
- 2026-11-14 [Mati] CONTRACTS v0.13 (T76): discovery index = `data/survey/discoveries.json` (schema `docs/discoveries.schema.json`: candidates with class, score 0–1, plain-words reason, known, lam_um, tile) served by `GET /api/discoveries` (filters class / position / score, `random=1`). Until the survey (T75) writes one, the API serves the hand-made sample `fixtures/discoveries-sample.json` (`synthetic: true`, labelled in the viewer). Why: the viewer side (T76) can be built and tested now, and pass 2 has a fixed target format.
- 2026-11-14 [Jonathan] CONTRACTS v0.14: `GET /api/pass-dates` + `x_survey_passes` in the live properties + `spherex-live-p<n>` documented. Why: `/app/` labels the blinked survey passes with when they were taken (month/year) instead of P1/P2/P3. New fields only.
- 2026-11-14 [Jonathan] `/app/` blinks by itself at level 7 (no Blink button, no red outline); default source = survey passes; "field epochs" builds the view's field once the map rests. Why: below level 7 no motion between epochs is visible, and pass tiles on the map's own grid load far faster than a build.
- 2026-11-14 [Joerg] CONTRACTS v0.15: new endpoint `GET /api/targets/<id>/spectral-outliers` (T85/T86): field-wide spectra and spectral outliers. Why: spectral analysis per field needs every source measured at once; new endpoint only, nothing existing changes.
- 2026-11-14 [Joerg] CONTRACTS v0.17: the spectral-outliers answer gains chart data (`points`, `envelope`, `bands_um`, `colours`; `version` 2). Why: the T86 charts; new fields only.
- 2026-11-14 [Jonathan] CONTRACTS v0.16: tiles mode `balanced` (default with a remote) + `balance` stats in `/api/settings`. Why: measured on fresh spots (18 pass tiles, 12 at once): balanced 9.1 s, local only 13.2 s, VM only 13.8 s; neither side alone is fastest all the time.
- 2026-11-14 [Jonathan] `/app/` chooses what blinks by itself: survey passes; resting on one HiPS order-6 tile builds its field in the background (no progress popup) and blinks its epochs while the view stays on that tile; leaving the tile or zooming out goes back to passes. A text indicator shows which. Why: no buttons, and fields on the tile grid are built once and reused.
- 2026-11-14 [Mati] CONTRACTS v0.18 (T64): frames carry `collection` (SPHEREx release), target.json `source_exposures` (images known at build time), new `GET /api/targets/<id>/updates` (newer images / new release → the viewer offers Rebuild). Image searches no longer use a fixed list of four collections: `pipeline/releases.py` lists the bucket's release folders (cached a day) and adds new ones (`spherex_<rel>`, `_deep`), duplicates across releases dedupe to the newest. Why: the challenge asks for a tool that is easy to update with the latest data releases; with the fixed list a QR4 / DR2 would never have appeared.
- 2026-11-14 [Jonathan] CONTRACTS v0.19: `visits` per pass in `/api/pass-dates`. Why: near a pass boundary a pass holds two visits half a year apart (Epsilon Indi B: Apr & Oct 2025); the map labels them separately.
- 2026-11-14 [Jonathan] CONTRACTS v0.20 (T89): `&detector=` on `/api/target`, epoch layers `e<n>d<det>` / `e<n>c`, sky layers `spherex-live-p<n>-rgb`, live-order slices rounded to the detector. Why: the band slider did nothing for field epochs (mean of all detectors) and re-rendered identical pass tiles for each of a detector's 17 channels; a one-detector field builds in 31 s instead of ~100 s.
- 2026-11-14 [Jonathan] CONTRACTS v0.21 (T89): `spherex-live-rgb` (false-colour map at every zoom) and IRSA's blank cube slices 50/51 served from 49/52. Why: false colour did nothing zoomed out, and the band 2.399 µm (slice 50) left the zoomed-out map black.
- 2026-11-14 [Jonathan] T90: `/web/` is now one page: first screen = the T55 map (automatic blink, floating panels), scroll down for every web/ feature (map tools, field form, frame viewer, analysis, spectra, objects, frames, provenance). Nothing of web/ or app/ dropped. `/app/` stays as it is until we decide to remove it. Why: one viewer for the demo, and the others keep all their widgets.
- 2026-11-14 [Joerg] CONTRACTS v0.22 (T58): limits for a public Live API behind `--public`: 429 / 503 busy with Retry-After, admin token for refresh and settings, cache cap. Why: a public server must not download unlimited data or fill its disk; off by default, so nothing changes for the team.
- 2026-11-14 [Mati] **Scope: the tool shows the data beautifully, citizen scientists do the finding.** We build
  visualization (blink, bands, stacks, differences, spectra, overlays, map) and no automatic discovery: no
  precomputed survey (T73–T75 parked, code kept on branch `mati/T73-survey-pilot`, unmerged), no new
  classification layers. Why: the challenge asks for "a public-facing web tool to display images of the sky ...
  making it easy for anyone to quickly see how they change over time" (WiseView as the model: the volunteers
  made the discoveries); with the deadline on Nov 15 the work goes into the tool, deploy (T14) and submission
  (T15/T16). Existing on-demand analysis panels stay as they are unless their owner decides otherwise.
- 2026-11-14 [Mati] CONTRACTS v0.23: `GET /api/discoveries` and the discovery index format (v0.13, T76) removed, with the Candidates panel. Why: the scope Decision above (visualization only); nothing else used them.
- 2026-11-14 [Mati] Board layout: three tables under "Board": **Active** (open / doing / review / blocked), **Parked** (set aside by a Decision), **Done**. Rows themselves unchanged; each owner moves their row to Done when finishing. Why: 70 of 91 rows were done, the open work was hard to find.
- 2026-11-14 [Joerg] CONTRACTS v0.24 (T91): `GET /api/targets/<id>/motion?name=` (a star's motion, and distance when reliable, measured from SPHEREx alone). Why: the official targets' motion as a result, not only the catalogue path; new endpoint only.
- 2026-11-14 [Jonathan] CONTRACTS v0.25 (T89): false colour at orders 6-7 is LRGB (detail from the chosen band, colour from the all-band cube at order 5); colour layers keep their band slices. Why: one render per colour tile instead of six; switching to false colour took ~25 s for 12 pass tiles, now 2.6 s (and a cold colour tile costs about what a grey one does). Trade-off: the colour is coarser (13″) and from all passes together; the detail (what moves) stays sharp and per pass.
- 2026-11-14 [Mati] CONTRACTS v0.26 (T93): chemistry maps: `GET /api/targets/<id>/chemistry`, `/api/chemistry/features`, map layer `x-<feature>` (server/hips.py: `LAYER_RE` + `chemistry_image`). Why: show the 102 bands as chemistry (feature minus continuum) for citizen scientists to look at; visualization only.
- 2026-11-14 [Jonathan] `app/` deleted: the T55 redesign is merged into `/web/` (T90), which keeps every web/ feature. CLAUDE.md's `app/` rule removed, `web/dev.py` no longer serves `/app/`. Why: one viewer; everyone works in `web/` again.
- 2026-11-15 [Mati] CONTRACTS v0.27 (T96): chemistry maps combined. `/api/chemistry/features` adds `shows` and `combine`; 2-3 maps as one colour picture (`.../chemistry/<a>-<b>[-<c>].png`, map layer `x-<a>-<b>[-<c>]`, features in wavelength order, shortest blue, longest red). Additive; asked by Mati so several filters can be on at once.

## Ideas

Format: `[name] idea — status: new`. Agents don't act on an idea until a human moves it to the Board.
Ordered by importance for the submission and demo, most important first; done ones at the bottom (Mati, 2026-11-14).
Ideas moved to the Board or done are deleted from this list (Mati, 2026-11-14); the Log says which task each became.
Ideas are numbered (I1, I2, …) to refer to them; numbers stay fixed, a new idea takes the next free number.
- I7 [Mati] **Embed + share** (consideration: "easily embed it in other websites"): `?embed=1` compact layout
  (stage + blink only, for iframes), and export the current frame / difference / series as PNG or GIF.
  C ~1.5 h.
  (gap scan vs. the official text, 2026-11-14) — status: new
- I21 [Mati] **Periods of variable stars (Lomb–Scargle periodogram)**, for later: on light curves at matched
  wavelength (T49 photometry, T12 pairs; brightness corrected for wavelength first, since SPHEREx's LVF puts
  every exposure at a different λ), find periods of hours to days from the ~150–190 exposure times per spot
  (Joerg's numbers, T77). Watch for false periods from the 98-minute orbit and the burst cadence (aliasing).
  Fits the challenge's variable-star test targets (RW Aur, R Dra) and the survey's variability score.
  (from the Fourier-analysis discussion, 2026-11-14) — status: new
- I22 [Mati → Joerg, Jonathan] **Fourier-based image comparison**, for later: (a) sub-pixel shifts by phase
  correlation between epochs, for slow movers (brown dwarfs move only 0.1–0.6 px over SPHEREx's ~1 year, T65);
  (b) PSF-matched difference images (ZOGY, Fourier-based optimal subtraction) instead of the plain A − B, so
  fewer star residuals and false detections. For T06 / the survey (T73–T77) and the difference view (T43).
  (from the Fourier-analysis discussion, 2026-11-14) — status: new
- I23 [Mati] **Expected vs. measured spectrum, one-field pilot** (Mati's outlier method, see T75 notes): for every
  catalogue star in one field (RW Aur or Eps Ind B), predict its 0.75–5 µm spectrum from Gaia + 2MASS + WISE,
  measure it (T49), score how far peaks, dips and the overall level deviate (rules: calibrated boundaries,
  consistent outliers only), colour each star by its score in the viewer, list the top outliers. RW Aur should
  come out red (disk excess), nearly everything else blue. Proves the method before the survey (T75/T76) uses it
  per tile. C + a bit of A, ~2 h.
  (from the outlier-heatmap discussion, 2026-11-14) — status: new
- I24 [Mati] **Dimming: is the whole curve lower than expected?** A star fainter at all wavelengths in one visit
  than in its other visits can mean something passed in front of it: a planet (transit), a companion star
  (eclipse) or a dust cloud. Compare with the star's *own* other visits, not the catalogue (calibration ~10 %).
  The colour of the dip tells the cause: a planet dims all wavelengths about equally, dust dims short
  wavelengths more. Realistic: deep eclipses (binaries, giant planets around small stars, a few %+); Earth-like
  transits (0.01 %) are far too shallow. Validation: known transiting planets / eclipsing binaries with
  ephemerides (NASA Exoplanet Archive, VSX): predict which SPHEREx exposures fall in transit (a hot Jupiter is
  in transit ~3–4 % of the time, so ~5 of the ~170 exposure times per spot) and check the dip is there.
  **Note (Mati): best first step is validation, not discovery.** Take known transiting planets and eclipsing
  binaries whose transit times are published (NASA Exoplanet Archive, VSX), predict which SPHEREx exposures fell
  during a transit, and check that the dip is there and has the right depth. If it works, that's a strong demo
  ("we see a known planet passing in front of its star in SPHEREx data"), and it sets the depth limit for any
  real search later.
  (from the outlier-heatmap discussion, 2026-11-14) — status: new

## Questions / Blockers

Things waiting on a human.

- 2026-11-14 Who takes track A, B and C? (names for the Members table and branch prefixes)
- 2026-11-14 What is our exact submission deadline (local time)?
- 2026-11-14 `docs/CHALLENGE.md` is a placeholder: someone please paste the official challenge
  text, resources and judging criteria.
- 2026-11-14 Do we all agree on the PROPOSED architecture and CONTRACTS v0.1? If yes, append a
  Decisions line "AGREED".
- 2026-11-14 RESOLVED: tracks assigned, see Members & roles (A = Joerg, B = Jonathan, C = Mati).
- 2026-11-14 [Mati → A/Joerg] For T04: can no-data pixels (grid corners outside a rotated frame)
  be written as fully transparent (alpha 0) in the PNG/WebP? The viewer shows transparent pixels
  as hatched "no data"; black would look like empty sky.
- 2026-11-14 [Joerg → Mati] Yes: T04 writes no-data pixels with alpha 0 (now in CONTRACTS v0.2,
  PROPOSED). Masked bad pixels inside the frame get alpha 0 too.
- 2026-11-14 [Jonathan] Official text is now in `docs/CHALLENGE.md`. It differs from our plan:
  (1) users *enter RA/Dec* and get a video of that patch, but CONTRACTS says pre-baked targets,
  no live API calls (live IRSA cutouts from the browser, or a small backend?);
  (2) the named test targets are Barnard's Star, Epsilon Indi B, WISE 0855, RW Aur, R Dra:
  proper-motion stars, brown dwarfs and variables, not asteroids. Bake these as demo targets?
  (3) nice-to-haves: coordinates in the URL, add/subtract epochs, choosable FOV, Gaia/WISE
  overlay, spectra, flag display. Resources tab and judging criteria still missing.
- 2026-11-14 [Joerg → Mati] `labels` is in CONTRACTS v0.4 for T13 (overlay). Drawing suggestion
  and a working reference are in tasks/T19-labels.md, "Questions / needs from others".
- 2026-11-14 [Joerg → Jonathan] Since you build T02-T04: (1) T17 (matched pairs + `bandwidth_um`)
  is yours if you want it, it falls out of T03/T04; I released it. (2) Working exploration code for
  cutouts, alignment, flags, wavelength/bandwidth, alpha PNGs and pairs is in `pipeline/reference/`
  (README there). (3) After `target.json` is written, call `pipeline.labels.add_labels(target)`
  (T19). (4) CLAUDE.md asks for a task file per task: T02-T04, T06, T10 don't have one yet.
- 2026-11-14 [Joerg → Mati] `web/dev.py` line 145 still says `pip install -r server/requirements.txt`.
  That still works (direct deps are pinned), but `requirements.lock` is now the documented install.
  Your file, so I left it.
- 2026-11-14 [Joerg → Jonathan] For T04 / the server: please call `pipeline.labels.add_labels(target)`
  before writing `target.json` (in `build_target` or `server/builder.py`, your call), so live-built
  fields get labels. Meanwhile `pipeline/reference/bake_target.py` bakes REAL fields straight into
  `data/targets/<live-api-id>/` (cache hit for the viewer's quick picks), clearly marked in
  provenance as a reference-code stopgap. It is overwritten as soon as your build runs with refresh.
- 2026-11-14 [Mati → Jonathan, T30] `web/` changed a lot today (T12, T20, T25, T29): please merge main
  before building on it. Structure: `app.js` = form/URL/Live API, `viewer.js` = frame state (one
  `refreshMarks()` repaints A/B/shown/filter everywhere), `timeline.js` = epoch timeline view,
  `paths.js` (T22) via `viewer:*` events. Suggestion: make explore mode its own module + panel and
  hand a clicked position to the existing form (`fillForm` + `loadField` in `app.js`) so the per-epoch
  blink, progress, URL and history keep working. Run `python web/tests/browser_test.py` before merging.
- 2026-11-14 [Mati → Jonathan, server] Fixture mode (`python -m server --fixture`) writes its synthetic
  copies into the same cache (`data/targets/<id>`) as live builds. After switching to live mode those
  ids are "ready" and serve the synthetic field until `refresh=1`. Suggest a separate cache dir for
  fixture mode, or live mode treating `"synthetic": true` entries as a cache miss.
- 2026-11-14 [Mati → Jonathan, T30] Explore mode is broken in every browser: `web/explore.js` loads
  `aladin-lite@3.8.2/dist/aladin.js` with a classic `<script>`, but that file is an ES module (ends with
  `export`) → "Unexpected token 'export'", no map; the exception also broke two other browser checks
  ("stop waiting", phone scroll). Tested fix (one line, in `initExplore`): replace `await loadScript(...)`
  + `A = window.A` with `A = (await import(ALADIN_JS)).default;` → `web/tests/browser_test.py` back to
  1 failure. That one is external: today Aladin resolves `CDS/P/SPHEREx/QR2/D1` via `alasky.unistra.fr`
  (DNS does not resolve) and `alaskybis` (aborted); its DSS fallback 404s. Until CDS is back, the map
  stays empty unless you use direct HiPS URLs on a host that is up (e.g. IRSA's SPHEREx HiPS).
- 2026-11-14 [Mati → Jonathan, T06] T07 is in: `detect.known_objects.add_known_objects(target)` fills
  `known_objects` (JPL sb_ident + Horizons from SPHEREx). Please call it from `detect.run.detect()` (or after
  `add_labels` in `pipeline.build`) so live builds get known asteroids; cost is a few minutes near the
  ecliptic (JPL rate limits), less elsewhere. Details in tasks/T07.
- 2026-11-14 [Mati → Jonathan, T06] T08 is in too. Suggested `detect.run.detect()`: find tracks →
  `detect.known_objects.add_known_objects(target)` → `detect.classify.classify_detections(target)`. Tracks need
  per-frame `frame_id, ra_deg, dec_deg, x, y`; `status` may be left out. Details in tasks/T08.

- 2026-11-14 [Joerg + Codex → Jonathan, T42] Tile queue stall diagnosed on current main
  (`35ed3ad`): browser aborts off-screen fetches, but synchronous `/api/sky` handlers continue S3
  work; `SkyCache.prefetch_around` also submits 8 neighbours + 4 children for each completed live
  tile, sharing the six `_live_slots` with visible requests, without viewport cancellation or
  submission deduplication. Offline captured-executor reproduction: one order-6 request schedules
  12 live jobs (8 order 6, 4 order 7); repeated before caching schedules 24. Health and cached
  properties still respond in 16 ms / 1 ms, so that is not evidence of a frozen API. Suggested first
  fix in your active T42 area: disable speculative prefetch into live orders (including order-5
  children), then prioritize visible live requests and stop disconnected jobs before acquiring a
  live slot. Consider single-flight protection for shared S3Image metadata/chunks too: current
  `.part` paths can collide across tile workers. No production code changed by Joerg's session.
- 2026-11-14 [Mati → Jonathan, T49] Heads-up: T49 (light curves + spectra) adds `server/photometry.py` (an
  APIRouter, `GET /api/targets/<id>/photometry`) and one `app.include_router(...)` line in `server/app.py`;
  it reads the cached cutouts via `pipeline.build.cached_cutout` / `wavelength_at`. Shout in tasks/T49 if
  you'd rather wire it differently.
- 2026-11-14 [Mati → Joerg, Jonathan] Please look at the four task proposals (a)–(d) under Ideas
  ("Four task proposals from a cross-check …") and answer here: include yes/no, and owner. Suggested:
  (a) Mati, (b) Joerg (labels), (c) Jonathan (index + S3), (d) with T06. Once a human says yes, they go
  onto the Board with task files.
- 2026-11-14 Jonathan (Claude): two Board rows use the ID T52 (Joerg: more labels; Mati: docs match
  the code). One of them should take a new ID (next free: T56).
- 2026-11-14 Mati (Claude): resolved, no answer needed any more: the four proposals (a)–(d) are on the Board: (a) → T63 (done), (b) → Joerg's T52 (done), (c) → T66, (d) → T67. The ID question is answered too (docs task = T56).
- 2026-11-14 Mati (Claude) [→ Joerg]: T77 (your sky survey on the HPC, 17:34) and T73–T75 (discovery survey, created 17:31 and assigned to you by Mati) describe the same thing. Please merge them as you like (e.g. keep T77 as the plan with your measurements, fold T73–T75 into it or use them as its steps) and close the rest. Two points from T73 worth keeping: (1) slow movers need full resolution (brown dwarfs move 0.1–0.6 px between epochs), so coarse-to-fine should cut along time/wavelength (a sparse exposure set first), not pixels; (2) T76 (Mati) is the viewer side either way.
- 2026-11-14 [Jonathan → Mati] `server/test_discoveries.py::test_sample_served_until_the_survey_delivers` fails on Windows: `/api/discoveries` returns `source` with a backslash (`fixtures\discoveries-sample.json`); use `.as_posix()`.

- 2026-11-14 Mati (Claude) [→ Jonathan, T06]: **Mati: T06 (blind mover detection + linking) is low priority.** Please
  copy this into tasks/T06 when you make the file. Why:
  1. Stars hardly move within SPHEREx's data (2025-04 to 2026-10, ~1.4 years at 6.15″/px): Barnard's Star, the
     fastest, ~1.8 px; Kapteyn ~1.5 px; WISE 0855 ~1.3 px; typical nearby brown dwarfs 0.1–0.6 px (measured
     on the local image index, T65/T76). Visible in a blink only for a handful of stars, and every star bright
     enough for a SPHEREx centroid (~0.1 px, T09) already has a better proper motion in Gaia / CatWISE.
  2. Asteroids move plenty (~37 px between bursts, T77) but a single exposure only reaches V ≈ 14–15 (T09:
     Amphitrite V 10.7 recovered 19/19, V 18–20 asteroids 0/17); everything that bright is long known. Movers
     from single exposures would be recoveries, not discoveries.
  3. SPHEREx's strength is the 102-band 0.75–5 µm spectrum per epoch. The discovery survey (T73–T75, now Mati's)
     therefore measures at catalogue positions with the existing photometry (T49/T66/T83) and looks for odd
     spectra (expected from catalogue colours vs measured: infrared excess, ices, emission, brown-dwarf shape),
     brightness changes at the same wavelength between epochs, and 4–5 µm sources without a Gaia counterpart.
     None of that needs T06's extractor or linking.
  Still useful later for slow distant bodies (T10 Planet X mode) with shift-and-stack (T69), and for the
  "follows the detector" artifact rule (T67).
- 2026-11-14 [Joerg → Jonathan] T89: proposal to feed your false colour / band layers with deep per-detector (and per-epoch) stacks from the T85 cutouts (~40 exposures per detector instead of 2); details in tasks/T89 "Notes from others". Your call; I won't touch it unless you say so.
- 2026-11-14 [Jonathan → all] After T90, CLAUDE.md's rule "`app/` is Jonathan's UI redesign, everyone else works in `web/`" is out of date: the redesign lives in `web/` now. Proposal: everyone works in `web/` again, `app/` gets deleted once you've looked at `/web/`. Say so here (or just delete it).
- 2026-11-14 [Joerg → all] T14 public deploy: which host? Options: the us-east4 VM (already serves tiles, next to the data), a new small VM, or this host behind a tunnel. Needs a decision before Sunday noon; T58 limits are being added now.
- 2026-11-14 Mati (Claude) [→ Joerg, Jonathan]: see the new Decision "the tool shows the data, citizen scientists
  do the finding". [→ Joerg] T84/T86 panels stay (on demand, the user judges); T87 (classes from the bands) is
  against the new scope: please decide with Mati whether it still goes ahead. Survey pilot results (7 fields,
  for reference): Eps Ind B came out as a brown dwarf by itself, the Barnard field's RR Lyrae and eclipsing
  binary as variables (scatter within an epoch); notes in tasks/T73–T75.

## Log

Append-only, newest at the bottom. Format: `date time [name] done / next / gotchas`.

- 2026-11-14 [joerg + Claude] Done: team scaffolding (CLAUDE.md, TEAM.md, contracts v0.1, schema,
  synthetic fixture, folders, SessionStart hook). Next: assign tracks, paste official challenge
  text, agree on contracts, claim T01/T06/T11. Gotchas: the fixture is fully synthetic, never show
  it as SPHEREx data; the SPHEREx data DOI in README is still a TODO.
- 2026-11-14 [joerg + Claude] Done: T01 merged (`pipeline/query.py`). Looked at real data for COSMOS
  (RA 150.1, Dec +2.2), detector 2: 39 cutouts aligned and blinked, private page shared by Joerg on
  request. Next (Joerg): T02 cutout download + cache. Findings and gotchas for everyone:
  - Data: `spherex_dr1` (Apr 2025 - May 2026) + `spherex_qr3` (May 2026 on), plus `*_deep` near the
    ecliptic poles. One row per detector image (D1-D6), 2040x2040 px, 6.15"/px, ~3.5 deg FOV.
    COSMOS has 3 epochs: Apr-May 2025, Nov 2025, May 2026.
  - Every visit sees the target at a different wavelength (LVF, ~0.03 um steps between consecutive
    exposures). Stars change brightness with wavelength, so plain median differencing leaves star
    residuals. B: compare frames at similar wavelength or normalise per star.
  - Visits come in bursts of 2-4 exposures 2 min apart, bursts hours/days apart. A main-belt
    asteroid crosses a 13' cutout in < 1 day, so it appears in one burst only.
  - FITS FLAGS plane names are in the header (MSKNnnnn). Bit 21 SOURCE = on a catalogued source
    (~35% of pixels, not bad data). Bit 19 OUTLIER may include real movers, don't mask blindly.
    Hardware mask used: bits 0,1,2,6,9,10,11,14,17,25,26,27,28.
  - Wavelength at a pixel: `WCS-WAVE` table, an n x n grid (9 or 11) of (wavelength, bandwidth)
    on 1-based detector pixels; cutout -> detector offset via CRPIX1A/CRPIX2A.
  - Cutouts: append `?center=ra,dec&size=0.25deg` to the FITS URL. 10-25 s and ~4 MB each (mostly
    the EPSF table), so fetch in parallel (8 threads: 39 cutouts in ~2 min).
  - C: frames rotate between visits, so corners of the common grid have no data; show as "no data".
- 2026-11-14 [Mati + Claude] Done: T11 merged. `web/` is plain HTML/CSS/ES-module JS, no build:
  loads `index.json` + `target.json` (`web/targets/`, falls back to `fixtures/targets/`; `?data=`
  and `?target=` URL params), stacks all frames, A/B blink with speed, keys Space/X/arrows,
  frame info incl. A-B time and wavelength gap, provenance, synthetic badge + image watermark,
  transparent pixels shown hatched as no data, empty SVG overlay layer in CONTRACTS pixel coords
  for T13. Accepts schema 0.1 and 0.2. Next: wire the viewer to the Live API (v0.3), then
  T12/T13. Gotchas: viewer does not call the Live API yet; T14's note "no live API calls" is
  outdated since v0.3.
- 2026-11-14 [Jonathan + Claude] Done: official challenge text + Resources in `docs/CHALLENGE.md`;
  decided live data (CONTRACTS v0.3 Live API); T18 merged (`server/`, FastAPI, 11 tests pass,
  fixture output validates against the schema). Next: frontend needs RA/Dec input + `?ra=&dec=`
  + polling (C), `pipeline.build` with optional `progress=` callback (A). Gotchas: ids round to
  1e-4 deg (WISE 0855 → `c1337951-m072451-s15`); T14 GitHub Pages alone can't run the API, a
  Python host is needed; Space Apps general judging criteria still not pasted.
- 2026-11-14 [joerg + Claude] Done: T19 labels (pipeline side). `pipeline/labels.py` adds SIMBAD
  names + Gaia DR3 stars to `target.json`, moved to each frame time; 0.4" accuracy on real frames
  (Barnard's Star field). CONTRACTS v0.4 + schema. Also: CLAUDE.md rules for task files and
  "agents keep everything consistent". Next (Joerg): T02-T04 so `build_target` exists for T18.
  Gotchas: main SIMBAD host down today (mirror used); Barnard's Star saturates in D1.
- 2026-11-14 [Mati + Claude] Done: T20 merged. The viewer talks to the Live API: RA/Dec/size form,
  `?ra=&dec=&size=` links (back/forward work), progress panel while building, Rebuild, Copy link,
  quick picks for the five official test fields. `?data=<folder>` keeps an offline mode. Code split:
  `web/api.js`, `viewer.js`, `app.js`, `util.js`; browser test `web/tests/browser_test.py` (27 checks).
  Gotchas: serve the viewer on :8080, the API owns :8000. `web/presets.json` has SIMBAD positions
  moved to epoch 2026.0 (Barnard's Star moved 4.5' since J2000; WISE 0855's position in the challenge
  text is its ~2010 one); T05 should warm the cache with exactly those. Fast stars move < 1 px
  (6.15"/px) per 6-month pass. Requests for Jonathan (fixture `center`) and T14 (https) in tasks/T20.
- 2026-11-14 [Mati + Claude] Done: T21 merged. Everyone can run it: README "How to run" (venv, install,
  `python web/dev.py`), checked from a fresh clone. `web/dev.py` starts API + viewer, opens the browser
  (WSL-aware), serves only `web/` + `fixtures/`, stops both on Ctrl+C/SIGTERM, `--lan` for demos in the
  room. The viewer now looks for the API on port 8000 of the page's host. Gotchas: plain
  `python -m http.server` shares the whole repo with your network, use `--bind 127.0.0.1`; `pytest`/
  `httpx` (server tests) are not in any requirements file (question for Jonathan in tasks/T21).
- 2026-11-14 [Mati + Claude] Fix merged: blinking no longer scrolls the page down to the frame table
  on narrow screens (Mati's report); arrow keys step after clicking A/B/Blink. Branch
  `mati/T11-fix-blink-scroll`, details in tasks/T11. Merges cleanly with T22.
- 2026-11-14 [Mati + Claude] Done: T25 merged. The form opens with Barnard's Star filled in (from
  `"default": true` in `web/presets.json`), a hint says what can be changed, nothing loads until Show.
  Gotcha for T05: presets.json entries gained a `default` flag (additive).
- 2026-11-14 [Mati + Claude] Done: T29 merged. RA/Dec help is now a popup bubble under the form instead
  of a permanent line, switched OFF for now (`FORM_TIP_ENABLED` in `web/app.js`); `?tip=1` previews it.
  Gotcha for T16 (demo): switch it on before recording.
- 2026-11-14 [Jonathan + Claude] Done: T02-T04 (`pipeline/build.py`: query → cutouts with cache →
  align on the CONTRACTS grid + wavelength from WCS-WAVE → PNG with alpha → target.json + labels),
  server live mode, T26-T28 speed-ups. Measured on Barnard's Star 15': cold build 434 s (IRSA
  throttles with `503 Server busy`, now retried), FOV change 5-17 s, rebuild with new TAP query 30 s.
  Bottleneck = cutout downloads (4.6 MB each, 82% EPSF table), not the query (9 s). Found: CDS has
  SPHEREx HiPS per detector (`CDS/P/SPHEREx/QR2/D1`..`D6`, order 7) and IRSA a DR1 cube HiPS:
  usable for Google-Earth-style pan/zoom (Aladin Lite), but not split by epoch. T10 WIP merged
  (`detect/test_fields.py`): all 5 official fields have 2-4 epochs, fast movers shift 1-1.7 px.
- 2026-11-14 [joerg + Claude] Jonathan's `pipeline.build` is in and already calls `add_labels`, so
  `pipeline/reference/bake_target.py` is superseded (marked so). My local stopgap bakes were replaced
  by real builds via `?refresh=1`. Still missing in builds: `pairs` (T17, open). T22 movement paths +
  hover info are merged; the viewer draws `labels`, `known_objects` and `detections` tracks.
- 2026-11-14 [Mati + Claude] Done: T12 merged. Epoch timeline under the image (one panel per epoch,
  height = wavelength, click to view), wavelength range + detector filter, v0.2 pairs picker, default
  A/B = pair with the longest baseline, `M` matches B to A's wavelength. Frame info says whether A/B
  are wavelength-matched. Merged with T22 (paths) on top. Gotchas: not tried on a real live target
  yet; T17 (pairs in target.json) is still open, without it the viewer falls back to closest λ.
- 2026-11-14 [Mati + Claude] Done: T13 merged. Objects panel in the side bar: unknown movers first, known
  (matched), "known · not detected", artifacts behind a toggle; synthetic badge per object; headline next
  to the target name ("2 moving objects: 1 unknown", or "detection has not run" on real builds today).
  Click a row → ring on the image + jump to a frame with the object. Added browser checks for T22's
  overlay. Gotcha (server, Jonathan): a fixture-mode run caches synthetic copies under the same ids as
  live builds, so live mode then serves them until `refresh=1`; see Questions.
- 2026-11-14 [Joerg → Jonathan] T17: `pipeline/build.py` now calls `pipeline.pairs.add_pairs(target)`
  right before writing `target.json` (2 lines, next to your `add_labels`). Rule per CONTRACTS "Pair",
  tests in `pipeline/test_pairs.py`. Fields built before this have no `pairs`: `?refresh=1` adds them.
- 2026-11-14 [Joerg → Jonathan, for T32] Local feel-test of per-epoch HiPS (nothing committed, your
  task): Barnard's Star, D1, 5 images per epoch as 1 deg IBE cutouts -> `reproject_and_coadd` (mean,
  zodi subtracted, hardware flags masked) onto a 1.2 deg TAN grid -> `reproject.hips.reproject_to_hips`
  (FITS tiles, 256 px). Per epoch: stitch 1 s, tiling < 1 s, ~26 tiles, ~7 MB, HiPS order 7 =
  ~6.4"/px (native 6.15"). Coverage 70% (rotated 1 deg cutouts leave corners; use more images or
  full frames). Aladin Lite v3 shows them as overlay layers above `CDS/P/SPHEREx/QR2/color`;
  epoch switch = toggle layer opacity (no tile reload). Bottleneck is IRSA downloads, not tiling:
  15 x 1 deg cutouts took ~40 min while 5 live builds ran. Scripts: Joerg's scratchpad, ask if useful.
- 2026-11-14 [joerg + Claude] T23 progress: label motion summary + class (contracts v0.5), trail view,
  object inspector, overlap-free names, shift-and-stack (`python -m pipeline.stack`). T17 pairs now in
  `pipeline.build`. All merged.
- 2026-11-14 [Mati + Claude] Fixes merged: (1) frame URLs carry a build stamp (`?v=` newest provenance
  time), because the API caches frames for a day and a rebuild (Rebuild / refresh=1 / fixture → live)
  reuses the names: Mati saw 4 old synthetic frames among 36 real ones. (2) Objects headline no longer
  claims "no moving objects found" when detection never ran. First real field checked in the viewer:
  Barnard's Star, 36 frames / 3 epochs / 6 detectors, all images load, no errors. T30 report in Questions.
- 2026-11-14 [Jonathan + Claude] Done: T30 explore map (Aladin Lite 3.8.2 from jsDelivr; CDS SPHEREx
  HiPS D1-D6 + IRSA DR1 cube + 2MASS/AllWISE/unWISE/DSS, Gaia DR3 + SIMBAD layers, "Blink this spot"),
  T31 local index mirror (`python -m pipeline.mirror harvest|build`, 1.63 M images, 45 MB, search
  8-33 ms vs 9-19 s via TAP; first search in an unseen week resolves paths via TAP once), T32
  per-epoch HiPS (`/api/hips/...`, epoch buttons + blink in the map). Measured: more parallel
  cutout downloads make it slower (8 threads 0.31 MB/s, 16: 0.24, 32: 0.20; >50% `503 busy`), so
  8 stays. Gotchas: alasky.cds.unistra.fr down today (CDS SPHEREx HiPS may not load; IRSA-hosted
  layers still work); mirror uses a 1.74 deg circle around image centres (corners skipped, ~17%
  fewer images than TAP); ~1% of images are `l2b_retry` paths, fixed by a TAP lookup on 404.
- 2026-11-14 [Joerg → Jonathan] T35 adds two things to `web/explore.js`: `export const getAladin()`
  and an `explore:epoch` event at the end of `showEpoch(i)`. `web/traces.js` uses them to draw traces,
  per-epoch markers and names on the explore map. Shout in tasks/T35-sky-traces.md if that clashes.
- 2026-11-14 [Jonathan + Claude] Done: T33. `pipeline/s3.py` reads level-2 images from the AWS Open
  Data bucket `nasa-irsa-spherex` (dr1/qr2/qr3, same paths as IRSA) with HTTP Range: headers, rows
  of IMAGE + RICE tiles of FLAGS around the field, WCS-WAVE; ~0.5 MB per image instead of 4.6 MB.
  Checked against an IRSA cutout of the same image: same wavelength, same mask, correlation 1.0
  (ZODI is not read; the per-frame stretch absorbs it). Cold 15' builds now 32-63 s (was 434 s);
  FOV change 7.8 s. IRSA cutouts remain the fallback. Labels get a 5 s budget and are finished in
  the background. Found: `labels.simbad_labels` takes 30 s in deep fields (COSMOS: 29,328 SIMBAD
  rows x 30 frames = 1.4 M scalar WCS calls in `_track`), the TAP calls themselves take < 1 s.
- 2026-11-14 [Joerg → Jonathan] Your T37 finding (30 s labels in deep fields) was my `_track`: one WCS
  call per object per frame. T38 (commit e715788) vectorises it, caps labels at ~800 per field and runs
  SIMBAD + Gaia in parallel: COSMOS-like field 23 s -> 5.5 s, official fields 1-7 s (network-bound),
  same important labels. Your 5 s budget + late labels still make sense for slow catalogue servers;
  whether T37 still needs labels-on-request is your call.
- 2026-11-14 [Jonathan + Claude] Done: T36 own sky map (no Aladin): `web/sky.js` WebGL HiPS renderer
  (SIN projection, drag/wheel/pinch/dblclick/keys, parent-tile fallback while loading, 200-texture
  LRU), `web/healpix.js` (matches astropy_healpix on 1848 cases: `node web/tests/healpix_check.mjs`).
  Default map = IRSA SPHEREx DR1 cube with a 102-band slider; CDS D1-D6 + 2MASS/AllWISE selectable.
  T37 labels on request (Labels switch). Not seen in a browser by Claude; Jonathan tests visually.
- 2026-11-14 [Joerg → Jonathan, for T32/T36] Wide per-epoch stitching works as a reference
  (`pipeline/reference/wide_stitch/`): 2 full D1 images per epoch from the AWS mirror (~3 min for 6),
  stitched onto one 5.5 x 6.8 deg grid in 3 s per epoch, HiPS in 6 s, 22 deg² per epoch. Per-field
  epoch tiles (T32) only cover the built 15' field, so the map shows no per-epoch sky around it;
  full images (or Range reads of their region, T33) would give real stitching. Numbers in its README.
- 2026-11-14 [Mati + Claude] Done: T07 (JPL known objects as seen from SPHEREx; live check found 6779
  Perrine at the exact predicted pixel; offline tests) and T05 (`web/warm.py`; all five official fields
  warmed with pairs on Mati's machine in ~9.5 min). Also: `?explore=0` skips the sky map (the browser
  test uses it, so it no longer depends on external tile servers; runs in ~20 s). Gotchas: run the
  browser test with the project venv + `requirements-dev.lock` (server now imports numpy); the demo
  machine's cache must be warmed there. Mati's checkout stays on main; Claude works in a git worktree.
- 2026-11-14 [Joerg → Jonathan, Mati] T40 touches `web/app.js`: the Labels switch is wired in `main()`
  (was inside `startExplore`, so offline mode and `?explore=0` had no working switch), `setLabels`
  remembers the choice and fires `labels:changed`; `labels:set` flips it from elsewhere (paths.js
  has a second switch). Default is ON, see Decisions.
- 2026-11-14 [Jonathan + Claude] Done: T41. `/api/sky/<survey>/...` caches IRSA/CDS HiPS tiles under
  `data/hips_cache/` and prefetches 8 neighbours + 4 children per tile; the SPHEREx cube's Allsky is
  warmed at server start. Measured: Allsky 4.3 s -> 12 ms, cached tile 0.7-1.0 s -> ~10 ms. The
  browser now loads the most central wanted tiles first and drops tiles that left the screen. Epoch
  tiles are kept in memory and pre-rendered when the viewer asks for a field's layers.
- 2026-11-14 [Mati + Claude] Done: T08 (`detect/classify.py`: known via JPL tracks or moving catalogued
  stars; artifacts with reasons; unknown otherwise; score + motion; CONTRACTS v0.9 `reason`; objects panel
  shows it). 15 offline tests; all 73 Python tests + browser test green. Waits for real detections (T06).
  Gotcha: `pipeline.motion.summarize` ignores frame pairs < 0.05 h, SPHEREx visits are ~2 min apart.
- 2026-11-14 [Joerg → Mati] Thanks for the motion threshold catch: `pipeline.motion.summarize` now counts
  frame pairs >= 36 s apart if the shift is >= 3" (noise floor), plus first-to-last per epoch, so a fast
  mover seen in one ~2 min burst is a `fast mover`. 2 new tests (10" in 2 min -> fast; 1" jitter -> still).
- 2026-11-14 [Mati + Claude] Done: T43 difference view ("A − B" / `D`): grey = unchanged, white/black =
  brighter in A/B, blue = no data; B fitted to A first; exclusive with the trail view. On the real
  Barnard's Star matched pair (371 d) stars cancel and Barnard's proper motion shows as a white/dark pair.
  Also: offline mode hides the empty sky-map box. Covers the challenge's "subtract images" consideration.
- 2026-11-14 [Mati + Claude] Done: T46 CI. Every push to main / PR runs `pytest detect server pipeline tests`
  (new `tests/test_contract.py`: fixtures validate against the schema, frame files exist, presets sane) and
  `web/tests/browser_test.py` (fixture mode, `?explore=0`, no external servers). Rehearsed in a fresh clone +
  venv: 80 tests + browser test green. For everyone: run the same two commands before pushing; keep tests
  offline. Repo is private and no `gh` here, so the first GitHub run needs a human look at the Actions tab.
- 2026-11-14 [Mati + Claude] Done: T45 "▶ Play all" (`P`): the series as a little film (core Objective), all
  frames in the filter or 1 per epoch at A's λ, loops, shares the Interval slider; ends blink / difference /
  trail view. 7 browser checks; all tests green. Idea added: split `viewer.js` / `app.js` (size check).

- 2026-11-14 [Joerg + Codex] T48: cached overview now stays beneath deep-zoom tiles, using the
  detailed mesh to sample the correct Allsky atlas region. Offline renderer regression, 80 Python
  tests, projection and HEALPix checks pass; browser suite cannot launch Chromium (macOS Mach-port
  permission denial). Reload the viewer to use it. Repeated live-tile HTTP 502 responses on Joerg's
  machine are missing `data/mirror/index.npz`, not measured S3 failures: initialize the local mirror
  before expecting sharp live imagery. Queue contention diagnosis above remains a separate issue.

- 2026-11-14 [Joerg + Codex] Local mirror initialized on Joerg's machine: `pipeline.mirror harvest`
  completed all six detector CSVs + URI sample (one dropped response recovered), then
  `pipeline.mirror build` produced 1,628,230 rows / 43.2 MiB with six query/timestamp provenance
  records and 20 known processing-week paths. Barnard lookup: 299 images in 2.5 ms (index load
  0.287 s). Running API now generates live tile Norder6/Npix31792_1: HTTP 200, 291,326 bytes,
  99.8% coverage, 45.1 s cold / 17.2 ms cached. No restart required; reload the browser to retry
  previously failed tiles. Catalogue and cache files stay gitignored under data/.
- 2026-11-14 [Jonathan + Claude] Done: T47. `tilegen/` is its own subcomponent (render.py, service app.py,
  client.py). It runs on GCP VM `instance-20261114-132040` (us-east4-a) behind Caddy at
  https://136-107-125-170.sslip.io (only /health and /tiles/live/...). Everything else stays local:
  `python -m server --tiles-remote https://136-107-125-170.sslip.io [--use-remote]`, viewer has a
  "Tiles: local / US VM" switch (`/api/settings`). Deploy: `deploy/deploy.sh` (git archive, no GitHub
  creds on the VM). Measured: S3 on the VM 38-95 MB/s; new live tile 2-5.5 s (3 images), cached 0.9 s;
  before 20-60 s. Also applied Joerg's queue diagnosis: no live prefetch, slot wait stops when the
  browser hangs up, single-flight S3 chunks. The mirror now learns every week folder's processing
  version (tiles waited ~10 s per TAP lookup before). Stop the VM when not needed (costs credits).
- 2026-11-14 [Jonathan + Claude → Joerg] Fixed: `data/mirror/index.npz` (gitignored) missing on a fresh
  checkout made local live tiles fail with 502. Now the index is built by itself in the background on
  first use (~3 min); meanwhile the team tile VM stands in (it is now the default `--tiles-remote`;
  `--tiles-remote none` to disable), else the API answers 503 + Retry-After and the map retries.
- 2026-11-14 [Mati + Claude] Done: T49 light curves + spectra on the fly. Click any star (default: field centre):
  spectrum per epoch + brightness change at matched wavelengths. Real data: RW Aur measurable at short λ (rising
  IR spectrum, ~150 mJy at 1 µm → ~1 Jy at 4–5 µm); Barnard's Star and R Dra saturated in every frame (UI says
  so). Calibration vs Gaia within ~20 %. 89 Python tests + browser test green. Gotcha: the API machine needs the
  cached cutouts (`data/raw/`), i.e. photometry works where the field was built.
- 2026-11-14 [Mati + Claude] T46 follow-up: CI now also runs `web/tests/*.mjs` (Node 22): healpix_check,
  overview_check, projection_check all pass (they weren't in CI before). New Node tests in web/tests/ are
  picked up automatically. No Node here? Playwright ships one: `.venv/lib/python3.12/site-packages/playwright/driver/node`.
- 2026-11-14 [Mati + Claude] Ideas section re-ordered by importance (Mati's request): open ideas first, done ones at
  the bottom; Mati's bundled entries (gap scan, four proposals) split into single entries; Joerg's and Jonathan's
  entries moved only, text unchanged; the separate ranked overview removed. If you append an idea, put it where it
  ranks, or at the end and say so.
- 2026-11-14 Mati (Claude): Ideas numbered I1–I20 (sub-items I6a–d) so humans can refer to them; numbers are fixed, new ideas take the next free number. The proposals under Questions map as (a) = I8, (b) = I4, (c) = I11, (d) = I12. Only prefixes added, no content changed.
- 2026-11-14 Jonathan (Claude): T55 started. `app/` = copy of the viewer files in `web/` for the UI
  redesign, open at `http://localhost:8080/app/` via `python web/dev.py` (which now also serves
  `/app/`). **Other agents: `app/` is UI work only; keep your work in `web/` as before**, don't
  edit `app/`. Changes in `web/` are ported to `app/` by T55. Gotcha: Board has two rows named T52
  (Joerg more labels, Mati docs), see Questions.
- 2026-11-14 Mati (Claude): T56 done (idea I2; claimed as T52, then T55; renumbered twice because Joerg's T52 and Jonathan's T55 were claimed in parallel, theirs stay). README, CONTRACTS v0.11, TECH-STACK (rewritten), web/server/fixtures READMEs match the code. New fixture `fixtures/targets/demo-epochs/` (regenerate: `python fixtures/make_demo_epochs.py`), try it with `web/?data=../fixtures/targets/&target=demo-epochs`. Bug fixed on the way (Mati OK'd): since T51, `detect.classify` didn't recognise SkyBoT or the MPC catalogue as a known-object lookup, so unknown detections were capped at 0.6 with a wrong "not looked up" note. Joerg: if T51/T53 add another lookup service, add its provenance name to `LOOKUP_SERVICES` in detect/classify.py. CI now also runs `tilegen` tests. Still open: data credits + team names in README (T15).
- 2026-11-14 Mati (Claude): answer to Jonathan's ID question: the docs task is now T56 (T52 = Joerg's more labels, T55 = Jonathan's UI redesign). Commits before this say T52/T55 for it. Tip for all agents: `git fetch` right before choosing a new ID.
- 2026-11-14 Mati (Claude): Ideas → Board on Mati's request: I1 → T58, I3 → T59, I5 → T60, I6a → T61, I6c → T62, I8 → T63 (rephrased by Mati: know what normal looks like, then explain why a deviation is interesting), I9 → T64, I10 → T65, I11 → T66, I12 → T67, I13 → T68 (blocked: wait for Jonathan's T55 UI redesign before refactoring `web/`), I14 → T69, I15 → T70. All open, no owner yet (suggested owners in the task files). Not new tasks: I2 deleted (done as T56), I4 done by T52, I6b done by T08, I6d is part of T06, I16 = T35, I17–I20 already done. I7 (embed + share) stays an idea.

- 2026-11-14 [Joerg + Claude] T51-T54 done, all on main. Known objects: local MPC orbit catalogue
  (`detect/mpcorb.py`, 1.58 M asteroids + 973 comets, Sun + planets n-body, matches JPL Horizons to
  0.05" for asteroids, <= 4" for comets), ~2-3 s per field instead of minutes (JPL sb_ident allows 20
  requests / 5 min). One-time setup per machine: `python -m detect.mpcorb fetch && python -m detect.mpcorb
  build` (else SkyBoT, ~25 s). Labels (T52, CONTRACTS v0.12): VSX variables (type, period, range),
  CatWISE2020 red movers (brown dwarf candidates; strict cuts, no fakes left in the five official fields),
  planets + bright moons from Horizons seen from SPHEREx. T54: labels + known objects run during the
  download, a new field is complete in ~12 s. Gotchas: VizieR CDS host down today (CfA mirror used);
  CatWISE on the CfA mirror needs `-out.all` (column lists return no rows).
  [to Jonathan] `/app/` (T55) is a copy of `web/` from before these: port `sourceName`/`note`/`mag_band`
  (web/util.js, paths.js, inspector.js) and `loadObjects` (web/app.js) when you sync it.
- 2026-11-14 Mati (Claude): T63 done: under the spectrum, a "what a plain star would give" baseline per epoch (blackbody fitted below 2.5 µm), rings on points that leave it, plain-words hints (warm dust / cool atmosphere / ices / hydrogen lines), feature markers toggle. Client-side only (`web/spectrum.js`), no API change, no effect on sky tiles. On real data: RW Aur 15× above the baseline at 4–5 µm (its disk), Eps Ind B no star shape + bright at 4 µm (brown dwarf). Jonathan: port to `app/` (T55), see tasks/T63.
- 2026-11-14 Mati (Claude): Ideas cleaned up on Mati's request: everything moved to the Board or done is deleted (I1, I3–I6, I8–I20; mapping in the Log line "Ideas → Board" above). Only I7 (embed + share) is left; numbers stay fixed, the next new idea is I21.
- 2026-11-14 Jonathan (Claude): T57 done. "Show" gets its cutouts from the US VM: fresh 15' field
  52.8 s (direct S3) → 19.9 s, measured on the same PC. Also: images are aligned while the rest download;
  a wrong derived path (l2b_retry) is found by listing the bucket (1.3 s, was 38 s via TAP) and no longer
  pauses the VM; VM `data/` now survives deploys (was rebuilt each time because of `data/.gitkeep`).
  Nothing to do on your side: pull + restart the API. Gotcha: the line to the PC (~3 MB/s) is the limit now.
- 2026-11-14 Jonathan (Claude): T57 follow-up: unknown week folders in the image index are learnt from a
  bucket listing (0.7 s per week) instead of TAP (up to 145 s per build in a fresh checkout); TAP stays the
  fallback. Re-measured: fresh 15' field 22.4 s.
- 2026-11-14 Jonathan (Claude): T55 now works directly on main (no worktree/branch). `app/` refreshed to the
  current `web/` (07974ed: T52/T63/T72, skylabels.js, spectrum.js) before any redesign edit. `/app/` (UI redesign)
  and `/web/` (everyone's viewer) are both served by `python web/dev.py`. Others: keep working in `web/`.
- 2026-11-14 Mati (Claude): T09 done. `python -m detect.known_check`: is a known asteroid at its predicted position (vs. the same sky in other epochs), how far off, with control positions. (29) Amphitrite V=10.7: 19/19 exposures recovered, S/N 56–215, median offset 0.7″, 0/40 controls; flux rises 3.8→4.6 µm (thermal emission?). The 11 asteroids in our cached fields are V 18–20 and correctly not seen: single exposures reach ~V 14–15. Numbers for T15 in tasks/T09.
- 2026-11-14 Jonathan (Claude): T55 step 1 in `app/` only (`web/` unchanged): the sky map is the whole page,
  only map = SPHEREx 102 bands live deep zoom, no north-up button/key, nothing below the map (frame viewer,
  blink controls, timeline, analysis, side panel, footer) and no `?data=` mode; Show still builds the field
  and its epochs/traces/names show in the map. Unused modules deleted from `app/`.
- 2026-11-14 Mati (Claude): new tasks T73–T76, a discovery survey over SPHEREx without moving 107 TB (Mati's idea, refined): coarse-to-fine in time/wavelength (a sparse exposure set, ~4 TB) instead of pixels (slow movers like brown dwarfs need full resolution), pass 1 next to the bucket on the us-east4 VM, pass 2 zoom-in on flagged tiles on the university HPC, a discovery index in the viewer. Design + open questions in tasks/T73. Suggested owners: T73 Joerg, T74 Jonathan, T75 HPC person, T76 Mati.
- 2026-11-14 Mati (Claude): Mati assigns the discovery survey to Joerg: T73, T74 and T75 have Owner Joerg (status open until he claims them with `doing` + a branch). Joerg: design, data volumes and the open questions (HPC link to AWS, lead candidate class) are in tasks/T73; T74 needs Jonathan's T06 extractor per image and the us-east4 VM (T47). T76 (the viewer side: discovery index + "show me something interesting") stays open for Mati.
- 2026-11-14 Jonathan (Claude): T55 step 2 (`app/` only): the map fills the whole window, controls float over it
  in panels around the edges. `web/` unchanged.
- 2026-11-14 Jonathan (Claude): T55 step 3 (`app/` only): the panels over the map can be dragged anywhere
  (grip ⠿ or empty panel area), remembered per browser, double-click ⠿ resets. `web/` unchanged.
- 2026-11-14 Jonathan (Claude): T55 step 4 (`app/` only): Jonathan's panel arrangement is the default layout
  (two docks on the left edge). `web/` unchanged.
- 2026-11-14 Mati (Claude): new task T78 (Mati's request): type an exact wavelength instead of dragging the band slider / guessing A/B; sky map + blink viewer, also in Jonathan's `app/` (T55). Flagged the T77 / T73–T75 overlap to Joerg under Questions.
- 2026-11-14 Mati (Claude): T65 done: 20 more quick picks in the field dropdown (web/discover.json, from SIMBAD + the local SPHEREx index): 10 fastest-moving stars (Kapteyn's star, Groombridge 1830, Lacaille 9352, …) and 10 brown dwarfs bright enough for a spectrum; "Surprise me" button; a reason line under the header. Finding: SPHEREx covers each position for only ~1 year (DR1), so even Kapteyn's star moves just 1.5 px and brown dwarfs 0.1–0.6 px: brown dwarfs are framed as "look at the spectrum". Asteroid fields and unknown movers wait for T06/the survey. Jonathan: port to `app/` (tasks/T65).
- 2026-11-14 Jonathan (Claude): T55 step 5 (`app/` only): fewer captions (no title, ? help, map/epochs captions),
  button "Blink"; defaults Debug on, Traces + Labels off. `web/` unchanged.
- 2026-11-14 Mati (Claude): ideas I21 (periodograms for variable stars) and I22 (Fourier-based image comparison: sub-pixel shifts, ZOGY difference images) added for later, on Mati's request. Fourier analysis of the spectra themselves was ruled out (R ≈ 35–130, few uneven points, time mixed into wavelength).
- 2026-11-14 Jonathan (Claude): T55 step 6 (`app/` only): "Go" jumps to RA/Dec and pins it (no build, Blink builds);
  position + Blink on one line, band + switches below it. `web/` unchanged.
- 2026-11-14 Mati (Claude): T78 done: type a wavelength instead of dragging/guessing. Map bar: a µm box next to the Band slider jumps to the closest of the 102 channels. Blink viewer: "Frames at λ" sets A/B to the closest frames in the earliest and latest epoch (same detector) and says how far off each is. Feature wavelengths (Br-γ, H₂O ice, …) as suggestions; `?lam=2.17` in links. Jonathan: port the map box to `app/` (tasks/T78). FYI Mati: web/app.js is at 703 lines; T68 (split the big web files) is waiting on T55.
- 2026-11-14 Jonathan (Claude): T55 step 7 (`app/` only): 📍 + RA/Dec pill follow the mouse; Go puts the typed
  position under the mouse; Field input removed (Blink builds 1/3 of the view). `web/` unchanged.
- 2026-11-14 Jonathan (Claude): T55 step 8 (`app/` only): pin held at its head, RA/Dec in two lines beside it;
  Go centres + zooms to order 7; epochs merged into the band panel. `web/` unchanged.
- 2026-11-14 Mati (Claude): Mati's outlier method (expected spectral profile per source → measured vs expected → heatmap of outliers) written into T75 (Notes from others) with two rules: boundaries calibrated per tile from the data, and only consistent outliers count. Pointer in T76. Joerg: please read before the scoring step.
- 2026-11-14 Jonathan (Claude): T55 step 9 (`app/` only): 📍 after Go stays on the position and fades after 5 s;
  📍 button picks a spot on the map (sets form + URL). `web/` unchanged.
- 2026-11-14 Mati (Claude): ideas I23 (one-field pilot of the expected-vs-measured spectrum method) and I24 (dimming: transits, eclipses, dust; validate on known transiting planets) added on Mati's request.
- 2026-11-14 Mati (Claude): note added to idea I24: validation on known transiting planets / eclipsing binaries comes first (demo + depth limit), discovery later.
- 2026-11-14 Jonathan (Claude): T55 step 10 (`app/` only): standing 📍 = tip on the point, RA/Dec centred below. `web/` unchanged.
- 2026-11-14 Jonathan (Claude): T55 step 11 (`app/` only): 📍 looks the same when following the mouse (tip on the point, RA/Dec below). `web/` unchanged.
- 2026-11-14 Mati (Claude): T59 done, in the viewer instead of the pipeline (builds keep only 2 frames per epoch+detector, so a server co-add would gain √2): a "Stack" select next to A − B adds the shown frame's epoch (all 6 detectors, ~3.5× deeper) or its detector (all epochs, ~2.4×), with each frame's background removed; blink and Play all show the stack of each frame's group. Covers the challenge considerations "add together the data of each detector" and "add together images taken at different times". Display only, no API/contract change.
- 2026-11-14 Jonathan (Claude): T55 step 12 (`app/` only): Blink builds the visible view (square over it, ≤ 60′ = API
  limit) instead of a third of it; the red outline marks that view; no jump when the field is ready. `web/` unchanged.

- 2026-11-14 [Joerg + Claude] T81 + T82 done. The map does what the frame viewer did: A/B, blink, play,
  λ filter, timeline and A − B act on the map (frames and differences are field layers,
  `/api/hips/<id>/f003`, `/d-f003-f017`). Survey passes blink anywhere when zoomed in to 2° (P1/P2/P3,
  `/api/sky/spherex-live-p<n>`). [to Jonathan] tilegen/skycache/sky.js/explore.js touched (pass_ parameter,
  pass layers, addOverlays, overlays follow the band); the VM needs a redeploy before it can render pass tiles,
  until then the Live API renders them locally. `/app/`: same events (`viewer:frame`, `viewer:diff`) if you port it.
- 2026-11-14 Jonathan (Claude): API field size limit 60′ → 210′ (one SPHEREx detector), CONTRACTS + Decision;
  VM /cutout up to 6°; `app/` Blink can build the whole visible view up to 210′. `web/` unchanged (form max 60).
- 2026-11-14 Mati (Claude): T69 done: two more Stack options in the viewer: "along the selected object" (click an object; every frame shifted so it stays put: it adds up sharp, stars smear) and "along a guessed motion" (rate ″/h + direction, over the shown epoch: shift-and-stack for movers too faint for one frame). Built fields have frames days to weeks apart within an epoch, so guessed motions only work for slow movers (< ~0.5″/h, distant bodies); default 0.25″/h. Jonathan: viewer side for T10 Planet X mode.

- 2026-11-14 [Joerg + Claude] T83 + T84 done. Spectra of a clicked point from all exposures in ~6 s (was
  20-65 s; the cutout VM answered 502s, so spectra read S3 directly). T84: each spectrum is checked for
  non-continuous changes: spikes/dips per burst (named when a known asteroid passed: 244 Sita and 262 Valda
  recovered), level and shape changes between epochs; saturated sources say "can't judge". [to whoever owns
  T09] known asteroids are recovered at their predicted positions (T84 findings). [to Mati] see T84 handoff.
- 2026-11-14 Mati (Claude): T76 done: "Candidates" panel under the map (filter by class, sort, rings + names on the map, "Show me something interesting"); a click opens the field like a quick pick with the reason line and the map band at the candidate's wavelength. Served by `GET /api/discoveries` (CONTRACTS v0.13, schema `docs/discoveries.schema.json`). Until the survey delivers it serves a hand-made sample of 7 real, known objects (WISE 0855, Eps Ind B, RW Aur, R Dra, Barnard, Kapteyn, a brown dwarf), labelled "Sample · hand-made". [→ Joerg, T75] pass 2 writes `data/survey/discoveries.json` in that format; mark recovered catalogue objects with `known`. [→ Jonathan] new APIRouter `server/discoveries.py` + one include line in `server/app.py` (like T49); `/app/` port optional (needs only the route).
- 2026-11-14 Jonathan (Claude): T55 step 13 (`app/` + tilegen/skycache): survey passes blink by themselves
  once the map is at level 7 (no Blink click, no build; T82 pass layers on the map's tile grid, loaded from
  level 6 on, only fully loaded passes blink). Switch "Blink: survey passes / field epochs" next to Debug;
  epochs = the old Blink build, now only enabled at level 7. The US VM renders pass tiles now
  (`/tiles/live-p<n>/`, redeployed); the Live API asks it in "US VM" mode, an old VM falls back to local.
  `web/` unchanged. [to Mati] `server/test_discoveries.py` fails on Windows: `source` is
  `fixtures\discoveries-sample.json` (backslash), the test expects `/`.
- 2026-11-14 [Joerg] T23 closed (done). Labels have a position in every frame of every epoch (checked: 134/134 labels, 36 frames, epochs 1–3); the open step "try on official test targets" was dropped. T14–T16 (deploy, submission, demo) stay open until the project is close to final.
- 2026-11-14 Jonathan (Claude): T55 step 14 (`app/` + tilegen/skycache/deploy): no Blink button, red outline or
  play button: the map blinks by itself at level 7; labels are month/year ("Aug–Sep 2025") instead of P1 / Ep. 1
  (new `GET /api/pass-dates`, CONTRACTS v0.14). Faster pass loading: base map capped at order 6 under the passes,
  the Live API renders a tile's other passes in the background, VM tuned (12 slots, more S3 threads), redeployed.
- 2026-11-14 [Joerg] Claimed T85 (spectra for a whole field) and T86 (spectral outliers); T87 (features per band) added, open. Idea I23 (Mati: expected vs. measured spectrum) is folded into T86 as its second opinion; [to Mati] if you want to do the catalogue prediction part yourself, say so in tasks/T86 "Notes from others" and I leave it.
- 2026-11-14 Jonathan (Claude): faster pass tiles: VM 2 worker processes (it was GIL/CPU-bound), 1 image per pass
  tile, overflow pass tiles render on the local PC. 18 new pass tiles 20-24 s -> 12-13 s. VM redeployed.
- 2026-11-14 [Joerg] T85 + T86 done (CONTRACTS v0.15). A field's catalogue sources measured in every exposure at once (~20 s, cached; their spectra then open instantly), ranked by how far their spectral shape is from the field's ordinary sources, with plain-words reasons and caveats. Panel "Unusual spectra in this field" under the map in `/web/` (button, progress, list, click = spectrum). Checked against Gaia colours and WISE W1−W2 (findings in tasks/T86). RW Aur itself is saturated and listed as not judged. Gotcha: X-ray/radio catalogue positions are skipped (ROSAT 1RXS offsets faked an outlier). Next: T87 (features per band + I23 catalogue prediction).
- 2026-11-14 [Joerg] T86 reopened for a visualisation: field colour–colour diagram (outliers highlighted, click to select) + the selected source's shape vs. the field's ordinary sources, in the "Unusual spectra" panel.
- 2026-11-14 [Joerg] T86 done again: the "Unusual spectra" panel now shows the field as a colour–colour diagram (ordinary sequence grey, outliers orange, click to select) and the selected source's bands against an ordinary source of its kind and the field's spread. API answer has chart data (CONTRACTS v0.17, `version` 2).
- 2026-11-14 Jonathan (Claude): T55 step 15: `/app/` switches by itself between survey passes and the field epochs
  of the order-6 tile the view rests on (built in the background, ~40 s for one tile, no "Downloading cutouts"
  popup; indicator text "Blink: survey passes · field epochs: downloading cutouts 12/36…" / "Blink: field
  epochs"); Blink-source switch removed. Tiles: new default `balanced` (local + VM, by measured throughput;
  CONTRACTS v0.16). Fixed a Windows rename race in `pipeline/s3.py` (S3Image header cache, my code from T42).
- 2026-11-14 Mati (Claude): T64 done (CONTRACTS v0.18). The field line shows the SPHEREx releases ("· SPHEREx DR1 + QR3", also for fields built before, from `source_url`), the frame info the release per frame; a line under the field offers "Rebuild now" when newer images or a new release exist (`GET /api/targets/<id>/updates`). Image searches no longer use a fixed list of four collections: `pipeline/releases.py` lists the bucket's release folders (dr1, qr2, qr3 today, cached a day) and searches new ones automatically. [→ Joerg] pipeline: `releases.py` new; `query.find_exposures` collections default + dedupe; `mirror.jobs()` replaces the `JOBS` constant; `build.py` writes `collection` + `source_exposures`. [→ Jonathan] `server/updates.py` = new APIRouter + one include line. Also: in a checkout without `data/mirror/index.npz` (CI!), a tile test triggers `mirror.ensure_background`, which starts a real IRSA harvest; pytest passes but then waits minutes for it at exit (the harvest's ThreadPoolExecutor). Worth stubbing in the tests.
- 2026-11-14 Mati (Claude) [→ Joerg]: Mati moved T73–T75 (discovery survey) from Joerg to Mati (they were assigned to you but not started). They now build on your T85/T86: pass 0 = pilot manifest (5 official + 20 quick-pick fields), pass 1 = per field build + labels + T85 field spectra through the Live API, pass 2 = T86 outliers + brightness change between epochs at the same wavelength → `data/survey/discoveries.json` (T76 format). Blind mover linking (T06) is out, see Questions / Blockers. T87 (classes from bands) stays yours; the survey will take its classes when it lands.
- 2026-11-14 Jonathan (Claude): T55 step 16: survey passes blink from level 6 (their first live order; field
  epochs stay at level 7); base map under the passes capped at order 5 (IRSA cube, no competing live renders);
  pass labels list each visit ("Apr & Oct 2025": near a pass boundary one pass holds two visits;
  `/api/pass-dates` gains `visits`, CONTRACTS v0.19); stale highlight on the pass labels fixed.
- 2026-11-14 [Joerg] Board: removed a blank line between T47 and T48 that split the table (GitHub showed every row after T47 as plain text).
- 2026-11-14 [Joerg] Claimed T88: T86 results on the map (toggle in the map bar, rings, click card). [to Jonathan] done from `web/outliers.js` through `explore.addDrawHook` / pointer events on `#sky`; no edit to explore.js. `/app/` would need its own version if you want it there.
- 2026-11-14 Jonathan (Claude): T55: the map's Debug overlay describes the layer on top (the blinking survey pass or
  field epoch), not the capped base map under it ("map order 6 · MAX ZOOM" while the passes drew order 7).
- 2026-11-14 [Joerg] T88 done: "Unusual spectra" toggle in the map bar of `/web/`: rings the open field's spectral outliers on the map (measures the field first if needed), click a ring for a card with the reason and band chart; panel, colour diagram and map share one selection.
- 2026-11-14 Jonathan (Claude): T89 (band switching + false colour) in `/app/` + server: pass tiles one per detector
  (the 17 channels of a detector share a tile: switch within a detector in 0.01 s instead of a new render); field
  epochs per band (auto builds only the band's detector, 31 s instead of ~100 s; another detector = another
  cached build); "false colour" switch next to the band: passes from `spherex-live-p<n>-rgb`, field epochs from
  `e<n>c` (all-detector build). `pipeline/build.py` gained `detectors=` (my T02-T04 code; [FYI Joerg]).
- 2026-11-14 Jonathan (Claude): T89 follow-up: false colour now at every zoom (base map `spherex-live-rgb`: IRSA cube
  one channel per detector to order 5, live tiles above); cube slices 50/51 (blank at IRSA) from 49/52; Debug says
  "NO DATA" instead of "SHARP" when no visible tile has data.
- 2026-11-14 Jonathan (Claude): T90 done: `/app/` merged into `/web/`. First screen = the T55 map (Go, 📍, panels,
  automatic blink of survey passes / tile field epochs, band per detector, false colour, balanced tiles); scroll
  down for everything web/ had: map tools (base map, N↑, T82 pass buttons, Blink this spot), the field
  form (Show), frame viewer, analysis, spectra, objects, frames, provenance. The frame viewer / pass buttons take the
  map over until the view moves to another tile. [to everyone] pull and look at `/web/` before building on it;
  `web/tests/browser_test.py` not run by me (please run it). `overview_check.mjs` adapted to T89 (Joerg's T48 test).
- 2026-11-14 [Joerg] Claimed T58 (limits before a public deploy) and T91 (measured motion of the official targets); added T92 (guided tour), starts after T90 lands. T14 (deploy) needs a host decision from the humans: under Questions.
- 2026-11-14 [Joerg] T58 done: `python -m server --public` adds per-IP rate limits, a per-IP and server-wide cap on new expensive jobs (429 / 503 busy), admin token for refresh and settings, and an LRU cache cap. Off by default. Next for T14: a host (question under Questions / Blockers).
- 2026-11-14 Mati (Claude): Mati's Decision: visualization only, citizen scientists find things. T73–T75 parked (branch `mati/T73-survey-pilot` pushed, not merged: survey runner, `pipeline/variability.py`, pilot on 7 of 25 fields). Next: deploy (T14) and submission (T15/T16), timing with the team.
- 2026-11-14 Mati (Claude): T76 Candidates panel removed (Mati): panel, `/api/discoveries`, sample, schema, tests; CONTRACTS v0.23. Quick picks + Surprise me stay as the way to start. [→ Joerg] `web/outliers.js` placed its panel after `#discoveries`; it falls back to `#explore` now, no change needed.
- 2026-11-14 Mati (Claude): Board split into Active / Parked / Done (Mati's Decision; rows unchanged, only moved). **Joerg, Jonathan: pull before editing your Board rows**; on a TEAM.md conflict keep the moved layout and re-apply your change. New task T93 (Mati): chemistry maps, continuum-subtracted feature images (ices, PAH, hydrogen lines) for the shown field, visualization only.
- 2026-11-14 [Joerg] T91 done (CONTRACTS v0.24): a moving star's motion measured from SPHEREx alone, on demand from the spectrum panel. Barnard's Star 10.46 ± 0.19″/yr (catalogue 10.39); eps Ind B 4.60 ± 0.26″/yr and a parallax of 0.286 ± 0.022″ = 3.49 pc (Gaia 3.64 pc); WISE 0855 too faint in single exposures (says so). Fits the visualization-only Decision: on demand, for the star the user clicks.
- 2026-11-14 Jonathan (Claude): T89 faster false colour (LRGB): colour tiles = grey tile of the band x colour of the
  cube; field epochs in colour from the fast one-detector build (`e<n>c` via `hips.CHROMA`); the band slider stays
  active in false colour and picks the detail band. 12 pass tiles after grey: 25.5 s -> 2.6 s; cold ≈ grey.
  Old colour tiles in data/hips_cache (6-detector composites) deleted. CONTRACTS v0.25.
- 2026-11-14 Mati (Claude): T93 done: **Chemistry** in the map's view panel: for the shown field, a chemical feature (water / CO₂ / CO / methanol ice, PAH, water bands, Pa-β, Br-γ, Br-α) minus its continuum as a map layer + a plain-words note; from the field's own SPHEREx exposures, a few seconds. Orion: Br-α shows M42 + M43, PAH the cloud filaments. CONTRACTS v0.26. [→ Jonathan] `server/hips.py`: layer key `x-<feature>` (LAYER_RE, `chemistry_image`, tile cache keyed on the map file); `web/app.js`: `map:take` event → `setManual(true)` and `map:manual` fired from `setManual`. **The browser test fails on main since T90** (also without T93): `?explore=0` hides `#explore`, which now holds the RA/Dec form, so step 2's `page.fill` times out after 11 checks; CI is red until that is fixed. Separately, `/api/hips/<id>/e1d1/properties` answers 422 (the `e{ep}` route takes it before the layer route; T89 per-detector epochs).
- 2026-11-14 Jonathan (Claude): `app/` deleted (Jonathan). Everything it had is in `/web/` since T90 (checked file by
  file: what was only in app/ were older versions of the same lines). CLAUDE.md + web/dev.py updated, T55 done.
  Old `/app/` links now 404: use `/web/`. Answers my Question about the `app/` rule.
- 2026-11-14 [Joerg] T92 done: "▶ Tour" on the map (or `?tour=1`): intro, the five official targets, "Your turn"; each stop opens its field and says what to watch; Barnard / eps Ind B measure their motion with SPHEREx from the card. T91 follow-up: motion cached per star (the map's automatic tile fields share it), star-centred cutouts in big fields.
- 2026-11-14 [Joerg] Claimed T95: the two T90 problems not in Jonathan's T94 (browser test red; viewer field without labels). [to Jonathan] touches web/ files of T90; I keep changes small and leave the tile / 422 work (T94) to you.
- 2026-11-15 [Mati] T96 done (merged): Chemistry in the map's view panel is now a list of checkboxes, up to 3. One = the T93 grey map; two or three = one colour picture (emission for lines/PAH, absorption depth for ices/water). The picture stays when false colour is switched (app.js marks its own epoch picks `auto`); unticking all gives the map back to the automatic blink (`map:give`). Checked on Orion (H₂O ice + PAH + Br-α). Also: T94 note (tile fetches without a time limit; two OOM kills of the Live API tonight on an 8 GB machine: 16 spectrum workers + auto-started outliers per tile, details to follow with Mati's OK).
- 2026-11-15 [Joerg] T95 done: browser test green again. With the map off (`?explore=0`, offline) the panels T90 put on the map screen were hidden with it (build progress, error messages, synthetic badge, Labels switch): `panelsOffMap()` in app.js moves them under the field form in those modes. Test selectors point at `#field-form`. [to Jonathan] small change in your app.js, map mode untouched. Also: this host's disk was full (0 free) around 01:00; 11 GB of least-recently-used cutouts / tile row chunks evicted (built fields kept).
- 2026-11-15 [Joerg] Claimed T97 (cache cap for team servers; found when this host's disk ran full) and T60 (contamination flags in the viewer: named in the challenge text, visualization, fits the scope Decision).
- 2026-11-15 [Joerg] T97 done: `SPHEREX_CACHE_GB=<n>` (or `--cache-gb`) keeps a team server's caches under n GB without `--public`, tile row chunks included; off unless set. [to all] worth setting on any machine that serves for days: `SPHEREX_CACHE_GB=12 python web/dev.py`.
- 2026-11-15 [Mati] Claimed T15 (submission text, data credits, AI-use disclosure). Draft goes to `docs/SUBMISSION.md`; data credits in README get the exact data set names / DOIs / acknowledgement texts. [to Joerg, Jonathan] I need from each human: the name to print under Team, and a yes/no on the project title (README still says "working title"). Answers in tasks/T15 "Notes from others".
