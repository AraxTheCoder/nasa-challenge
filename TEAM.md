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

| ID | Task | Owner | Status | Branch | Notes |
|---|---|---|---|---|---|
| T01 | A: IRSA query: list all SPHEREx exposures covering an RA/Dec (SIA/TAP), with time, detector, access URL | Joerg | done | `joerg/T01-irsa-query` | `python -m pipeline.query --ra .. --dec ..`; COSMOS: 214 images, 3 epochs |
| T02 | A: Download cutouts for one target into `data/`, with a cache so re-runs don't re-download | Jonathan | done | `jonathan/T02-T04-build` | Needs T01 |
| T03 | A: Align cutouts to one common WCS grid (north up) and get the wavelength at the target position per frame | Jonathan | done | `jonathan/T02-T04-build` | Needs T02. Wavelength varies across a SPHEREx image |
| T04 | A: Render frames to PNG/WebP and write `target.json` per CONTRACTS, validated against the schema | Jonathan | done | `jonathan/T02-T04-build` | Needs T03. First real target = end-to-end milestone |
| T05 | A: Pre-build (warm) the five official test fields in the Live API cache so the demo opens them instantly (was: publish to `web/targets/`; changed by the live-data decision) | Mati | done | `mati/T05-warm` | [tasks/T05](tasks/T05-warm-demo-fields.md). `python web/warm.py` (or `dev.py --warm`) on the demo machine |
| T06 | B: Mover detection v0 on the fixture: source extraction per frame, match across frames, keep what moves | Jonathan | doing | `jonathan/T06-mover-detection` | Start on `fixtures/`, switch to real data after T04 |
| T07 | B: JPL SB Identification cross-match: known small bodies in the field per frame time → `known_objects` | Mati | done | `mati/T07-jpl-known` | [tasks/T07](tasks/T07-jpl-known-objects.md). `python -m detect.known_objects <dir>`; not yet called by builds (needs detect.run, T06) |
| T08 | B: Classify detections as known / unknown / artifact and write them into `target.json` | Mati | done | `mati/T08-classify` | [tasks/T08](tasks/T08-classify-detections.md). `python -m detect.classify <dir>`; waits for T06 detections; CONTRACTS v0.9 `reason` |
| T09 | B: Sanity check on a known bright asteroid in real SPHEREx data: do we recover it at the JPL position? | | open | | Needs T04, T08 |
| T10 | B: "Planet X mode": pick a slow distant body (dwarf planet), check it's detectable across epochs, propose the demo target list | Jonathan | doing | `jonathan/T10-test-targets` | Reworded 2026-11-14 for the official text: check SPHEREx multi-epoch coverage of the five official test fields (Barnard, Eps Indi B, WISE 0855, RW Aur, R Dra) + maybe one dwarf planet; feeds T05 warm-up |
| T11 | C: Static viewer skeleton: load `index.json` + `target.json` from the fixture, show frames, blink between two | Mati | done | `mati/T11-viewer-skeleton` | [tasks/T11](tasks/T11-viewer-skeleton.md). Vanilla JS, no build. Reads static target folders; not yet wired to the Live API (v0.3). Run: see `web/README.md` |
| T12 | C: Epoch timeline and band/wavelength filter | Mati | done | `mati/T12-timeline-filter` | [tasks/T12](tasks/T12-timeline-filter.md). Timeline per epoch (y = λ), λ/detector filter, v0.2 pairs, `M` = match B to A's λ |
| T13 | C: Overlay detections and known objects, with a clear "synthetic" badge where it applies | Mati | done | `mati/T13-objects-panel` | [tasks/T13](tasks/T13-objects-panel.md). Objects panel + headline count; paths on the image are T22 |
| T14 | C: Deploy: static viewer (e.g. GitHub Pages) + Live API on a host that runs Python, viewer pointed at it (contracts v0.3) | | open | | Needs T11, T18, T20. Reworded 2026-11-14 for live data (was: pre-baked targets, no live API calls) |
| T15 | C: Submission text, data credits and AI-use disclosure | | open | | Needs official text in `docs/CHALLENGE.md` |
| T16 | C: Demo video and slides | | open | | After feature freeze |
| T17 | A: Compute wavelength-matched `pairs` across epochs (+ `bandwidth_um`) in `target.json` (contracts v0.2) | Joerg | done | `joerg/T17-pairs` | Taken back: the viewer (T12) reads `pairs` but `pipeline.build` writes none. `pipeline/pairs.py` + one call in build.py |
| T18 | C: Live API service: `GET /api/target?ra=&dec=&size=` builds (pipeline + detect) or serves from cache, progress while building, CORS (contracts v0.3) | Jonathan | done | `jonathan/T18-live-api` | `python -m server [--fixture]`, see `server/README.md`. Live mode works once `pipeline.build` (T02–T04) exists; until then `--fixture` |
| T19 | A: Labels on the images: catalogue names/positions (SIMBAD, Gaia DR3 with proper motion) into `target.json` | Joerg | done | `joerg/T19-labels` | [task file](tasks/T19-labels.md). `pipeline/labels.py`; viewer side is T13 |
| T20 | C: Viewer ↔ Live API: RA/Dec/size input, `?ra=&dec=&size=` in the page URL, request + poll with progress, load from `target_url`, quick picks for the official test fields (contracts v0.3) | Mati | done | `mati/T20-live-api-client` | [tasks/T20](tasks/T20-live-api-client.md). Run: `web/README.md` (API :8000, viewer :8080). Test fields in `web/presets.json` |
| T21 | C: Everyone can run the viewer locally: one-command launcher (API + viewer), README run steps for Linux/macOS/Windows | Mati | done | `mati/T21-run-kit` | [tasks/T21](tasks/T21-run-kit.md). `python web/dev.py`, setup in README "How to run" |
| T22 | C: Movement paths in the viewer: line + tick per frame, early→late colour, current position + name, labelled exaggerated arrow for slow movers | Joerg | done | `joerg/T22-movement-paths` | [task file](tasks/T22-movement-paths.md). From the "Draw paths" idea. Hover/click info on labels |
| T23 | A: Labelling over time: labels that follow moving objects, motion summary + motion class per object, trail image, shift-and-stack | Joerg | doing | `joerg/T23-labels-over-time` | [task file](tasks/T23-labels-over-time.md). Umbrella for T19 (done) + T22; from 4 Ideas |
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
| T35 | C: Tracing over the stitched sky: paths, per-epoch markers and names of moving / important objects drawn on the explore map (T30/T32), following the epoch blink | Joerg | review | `joerg/T35-sky-traces` | [task file](tasks/T35-sky-traces.md). From Joerg's idea |
| T36 | C: Own sky map as the main view (no Aladin, no dependency): WebGL HiPS renderer (HEALPix tiles, SIN projection), drag/zoom/pinch like Google Earth, SPHEREx epochs as layers, blink in the map; frame viewer stays below as detail | Jonathan | done | `jonathan/T36-sky-map` | Replaces the T30 Aladin panel |
| T37 | A/C: Catalogue labels only on request: builds skip labels; `GET /api/targets/<id>/labels` computes them in the background; viewer has a Labels switch | Jonathan | done | `jonathan/T36-sky-map` | SIMBAD labels cost 30 s in deep fields (labels.py untouched) |
| T38 | A: Fast labels: vectorised tracks (all objects x frames at once), ranked cap of 400 SIMBAD + 400 Gaia per field, grid-based duplicate merge, SIMBAD + Gaia in parallel, 15 s per mirror | Joerg | done | (merged as e715788) | Deep field (COSMOS, 30,785 SIMBAD objects): 23 s -> 5.5 s, labels 50+ MB -> 1.2 MB. Official fields: same important labels |
| T39 | A: Wide per-epoch stitch test (reference): full 3.5° images from AWS, one mosaic per epoch over ~6°, HiPS, page with region-wide labels + traces | Joerg | done | `joerg/T39-wide-stitch` | `pipeline/reference/wide_stitch/` (README, `run.sh`). Input for T32/T36 (Jonathan) |
| T40 | C: Labels on by default + switch everywhere: default ON (remembered per browser), works in live/offline/`?explore=0`, second Labels switch next to the path controls | Joerg | done | `joerg/T40-labels-on` | Without labels the paths, names, inspector and sky-map traces had nothing to draw |
| T41 | C: Faster map images: server-side HiPS tile cache + prefetch (neighbours, children, Allsky), browser skips stale tiles and loads the centre first, epoch tiles cached and pre-rendered | Jonathan | done | `jonathan/T41-fast-tiles` | IRSA tiles 0.7 s first byte, Allsky 4.3 s, HTTP/1.1 (6 per browser) |
| T42 | A/C: Live deep zoom everywhere: order 6-7 SPHEREx tiles computed on demand from AWS level-2 images (band's detector, 3 images, cached row chunks, noise-normalised stretch); IRSA cube up to order 5; S3 404 -> resolve real path, not IRSA cutouts | Jonathan | doing | `jonathan/T42-live-zoom` | Red box = orientation only |
| T43 | C: Difference view A − B in the viewer (challenge: "subtract images taken at different times"): stars cancel for matched pairs, movers show as white/black pairs | Mati | done | `mati/T43-difference` | [tasks/T43](tasks/T43-difference-view.md). Button "A − B" / key `D`; best with a matched pair |
| T45 | C: Play the series like a video (core Objective): Play/Pause through all frames in the filter or one per epoch at matched wavelength, speed + loop | Mati | done | `mati/T45-play` | [tasks/T45](tasks/T45-play-series.md). "▶ Play all" / key `P`; modes: all frames in the filter, 1 per epoch at A's λ |
| T46 | All: tests on every push (GitHub Actions): pytest + browser test (fixture mode) + fixture schema check | Mati | done | `mati/T46-ci` | [tasks/T46](tasks/T46-ci.md). `.github/workflows/tests.yml`; first run: check the Actions tab |
| T47 | All: Live tile generator (`tilegen/`) on Google Cloud `us-east4` next to the AWS SPHEREx bucket; viewer/API/builds stay local (EU); Tiles switch local/US VM | Jonathan | done | `jonathan/T47-gcp` | From Jonathan's idea. Measure S3 throughput on the VM first |

| T48 | C: Cached Allsky fallback at deep zoom so pending/failed live tiles never erase available overview imagery | Joerg | done | `joerg/T48-map-overview-fallback` | [tasks/T48](tasks/T48-map-overview-fallback.md). User approved implementation + push; investigate repeated tile errors |
| T49 | A/C: Light curves + spectra on the fly at any position: aperture photometry on the cached SPHEREx FITS (pipeline + `/api/targets/<id>/photometry` + viewer charts); for the variable test stars RW Aur / R Dra | Mati | done | `mati/T49-photometry` | [tasks/T49](tasks/T49-photometry.md). `/api/targets/<id>/photometry`; panel under the timeline; CONTRACTS v0.10 |
| T50 | All: `web/dev.py --host ADDR`: serve viewer + Live API on one address only (e.g. WireGuard 10.0.0.2) instead of all interfaces (`--lan`) | Joerg | done | `joerg/T50-dev-host` | [tasks/T50](tasks/T50-dev-host.md). Joerg's new host serves the team over WireGuard 10.0.0.0/24 |
| T51 | B: `detect/run.py` so builds get known asteroids/comets now: JPL lookup (T07) + classify (T08) after every build; mover detection (T06) plugs into the same function later | Joerg | done | `joerg/T51-detect-run` | [tasks/T51](tasks/T51-detect-run.md). Builds call `detect.run.detect()` but the module never existed, so every field had 0 objects. Jonathan: T06 adds tracks here |
| T52 | A: More labels (idea I4 + more): VSX variable stars (type, period, range), CatWISE2020 brown dwarfs / high proper motion (moved to frame time), planets + bright moons (seen from SPHEREx) | Joerg | doing | `joerg/T52-more-labels` | [tasks/T52](tasks/T52-more-labels.md). New label `source` values + optional `note` (CONTRACTS v0.11) |
| T53 | B: Comets in the local orbit catalogue (MPC CometEls.txt), like the asteroids in T51 | Joerg | doing | `joerg/T52-more-labels` | [tasks/T53](tasks/T53-local-comets.md). SkyBoT fallback had comets, the local path not yet |
| T54 | A/C: Known objects + labels start while the images download (they need only frame times + field geometry), so a new field is complete when its frames are | Joerg | doing | `joerg/T52-more-labels` | [tasks/T54](tasks/T54-early-objects-labels.md). New field: frames 11 s, objects +2.5 s, labels +2-3 s today |
| T52 | All: Docs match the code (idea I2): README status/run/how-it-works, CONTRACTS without pre-baked `web/targets/` + `pipeline.publish`, undocumented API routes, a schema-0.2 fixture with pairs/labels/varied detections | Mati | doing | `mati/T52-docs-current` | [tasks/T52](tasks/T52-docs-current.md) |
| T55 | C: UI redesign under `/app/` (copy of `web/`); `web/` and `/web/` stay as they are for all other work | Jonathan | doing | `jonathan/T55-app-ui` | [tasks/T55](tasks/T55-app-ui.md). UI work only; everyone else keeps working in `web/` |

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

## Ideas

Format: `[name] idea — status: new`. Agents don't act on an idea until a human moves it to the Board.
Ordered by importance for the submission and demo, most important first; done ones at the bottom (Mati, 2026-11-14).
Ideas are numbered (I1, I2, …) to refer to them; numbers stay fixed, a new idea takes the next free number.
- I1 [Mati] **Limits before a public deploy** (T14): anyone can request any field and `refresh=1`, i.e. trigger
  unlimited IRSA/AWS downloads and JPL queries. Rate limit per IP, cap concurrent builds, disable
  `refresh` publicly (token), cache size cap with eviction. Server ~1 h.
  (gap scan vs. the official text, 2026-11-14) — status: new
- I2 [Mati] **Docs out of date** (consistency, CLAUDE.md): README "Status" still says every field is synthetic;
  CONTRACTS still describes pre-baked `web/targets/`, its size budget and `pipeline.publish`, which the
  live-data decision made obsolete (needs a Decisions line); the committed fixture is schema 0.1 without
  pairs / labels / varied detections (the browser test generates a richer one; commit it as a second
  fixture). ~1 h.
  (gap scan vs. the official text, 2026-11-14) — status: on the Board (T52)
- I3 [Mati] **Per-detector co-adds per epoch** (consideration: "add together all the data taken by each of the
  six detector arrays to improve the signal-to-noise"): mean/median of the aligned frames per detector
  and epoch as extra frames (`kind: "coadd"`, `n_exposures`; contract change). Helps faint red brown
  dwarfs (WISE 0855, Eps Ind B) that single 0.75-3 µm exposures barely show. A ~2 h + C ~0.5 h.
  (gap scan vs. the official text, 2026-11-14) — status: new
- I4 [Mati] **(b) VSX + CatWISE2020 labels.** VSX (AAVSO variable-star index): type, period, amplitude for variables
  (RW Aur, R Dra are official test targets). CatWISE2020: WISE positions + proper motions, the natural
  catalogue for brown dwarfs (WISE 0855, Eps Ind B). Both via VizieR/IRSA TAP into `labels` (`source:
  "vsx"` / `"catwise2020"`), moved to frame time like Gaia. A, `pipeline/labels.py` (T19/T23/T37 area).
  ~1.5 h. Suggested owner: Joerg. Contract: new `source` values only (additive).
  Also covers gap-scan item 7 (CatWISE2020 labels on the frames).
  (proposal (b) from the cross-check of a GPT write-up on SPHEREx science, 2026-11-14; owner question under Questions) — status: on the Board as T52 (Joerg)
- I5 [Mati] **Contamination flags** (consideration: "display metadata, like contamination flags"): only the
  hardware mask reaches the viewer (as no-data). Export a small per-frame flags image (or bit counts)
  with the frame; viewer: flags overlay toggle + flag names at the inspected pixel (OUTLIER may be a
  mover, SOURCE is a catalogued star, PERSIST is a ghost). A ~1.5 h + C ~1 h.
  (gap scan vs. the official text, 2026-11-14) — status: new
- I6 [Joerg] Feature list from Joerg (2026-11-14), what's not covered yet. Already covered: timeline
  (T12), blink (T11), matched pairs (T12/T17), layer toggles + motion paths + hover info (T22),
  objects list + status markers (T13), mover detection (T06), all-sky pan/zoom with epochs
  (T30/T32), Barnard's Star as validation (T19/T23). New: — status: partly done (see the tags below)
  - I6a (open, needs T06) Appear / disappear / brightness change between epochs, not only motion (detect side, B).
  - I6b (open, needs T06) "Uncatalogued?" check: a detection with no SIMBAD/Gaia label within ~1 px gets flagged
    (labels are already in target.json, so this is a cheap cross-match).
  - I6c (partly: score + reason per detection, T08; the list is open) Candidate ranking (motion significance, consistency across frames, catalogue match, artifact
    probability from the FLAGS bits) and a dedicated candidate list in the viewer.
  - I6d (→ part of T06) Photutils for source extraction (not in requirements.lock yet: add with a pin + lock update).
- I7 [Mati] **Embed + share** (consideration: "easily embed it in other websites"): `?embed=1` compact layout
  (stage + blink only, for iframes), and export the current frame / difference / series as PNG or GIF.
  C ~1.5 h.
  (gap scan vs. the official text, 2026-11-14) — status: new
- I8 [Mati] **(a) Spectral feature markers on the T49 spectrum chart.** Faint vertical guides with short names:
  H₂O ice 3.05, PAH 3.3, CH₃OH ice ~3.5, CO₂ ice 4.27, CO ice 4.67 µm; Pa-β 1.28, Br-γ 2.17, Br-α 4.05 µm
  (all checked); hover explains each; a toggle. Fits SPHEREx's ices goal, educational for the public.
  C, `web/photometry.js` only. ~1 h. Suggested owner: Mati. Done when: markers on, browser checks.
  (proposal (a) from the cross-check of a GPT write-up on SPHEREx science, 2026-11-14; owner question under Questions) — status: new
- I9 [Mati] **Data release in the UI** ("easy to update with the latest data releases"): carry the release
  (DR1 / QR3, from obs_collection) per frame into target.json, show it in frame info + footer, and let
  the API say when a cached field predates the newest release ("newer data available: Rebuild").
  (gap scan vs. the official text, 2026-11-14) — status: new
- I10 [Joerg] Auto target selection: instead of only typed coordinates, propose interesting fields
  automatically, e.g. high-proper-motion stars and brown dwarfs (Gaia/SIMBAD/CatWISE), known asteroids
  passing through SPHEREx frames (JPL, T07), fields where our detection (T06) finds unknown movers,
  or a "surprise me" pick ranked by how much moves there. Shown as a list / quick picks. — status: new
  (the five official test fields are quick picks already: T20/T25)
- I11 [Mati] **(c) Fuller spectra from all exposures.** T49 measures only the frames picked for blinking (builds
  keep 2 images per epoch+detector: 36 of ~358 for Barnard's Star), so spectra have ~12 points per
  epoch. Measure every exposure covering the position instead (T31 index lists them; T33 range reads
  fetch only the rows around the star), cached per position. A, `pipeline/photometry.py` + the index /
  S3 readers. ~2 h. Suggested owner: Jonathan (index + S3 are his), viewer side unchanged.
  (proposal (c) from the cross-check of a GPT write-up on SPHEREx science, 2026-11-14; owner question under Questions) — status: new
- I12 [Mati] **(d) "Follows the detector, not the sky" artifact rule.** A detection whose pixel position on the
  *detector* stays fixed while its sky position jumps (ghosts, persistence, hot pixels) is an artifact;
  also: seen on one detector only while overlapping frames of another detector show nothing. B,
  `detect/classify.py` (T08), needs real detections (T06) to tune. ~1 h. Suggested owner: whoever does
  T06, or Mati once T06 delivers.
  (proposal (d) from the cross-check of a GPT write-up on SPHEREx science, 2026-11-14; owner question under Questions) — status: new
- I13 [Mati] Split the two big web files before they tangle (Claude's size check, 2026-11-14): `web/viewer.js`
  582 lines, `web/app.js` 605. Move filter / pairs / matching / playback out of `viewer.js` into `compare.js`,
  and the sky-map wiring (T30/T36/T42) out of `app.js` into the explore module. Pure refactor, no framework
  needed; the browser test (CI) guards it. ~1 h. — status: new
- I14 [Joerg] Shift-and-stack: add frames after shifting each along a guessed motion; faint movers
  sharpen, stars smear. Standard for distant-object searches; matches the challenge's "add together
  or subtract images". — status: partly done (`python -m pipeline.stack`, T23; not in the viewer)
- I15 [Joerg] Motion classification for detections: from the track, rate + direction + shape, shown as
  a label, e.g. "asteroid-like, 30"/h" (seen in one burst only), "moves between epochs only: nearby
  star / brown dwarf", "large jump between epochs, slow drift within one: distant solar-system body".
  Rough numbers: main belt ~150 px/day; Barnard 1.7 px/yr; a body at 500 AU swings ~+-0.11 deg/yr
  from Earth's orbit, i.e. up to ~14' between epochs (about one default field!), ~1 px/day within
  an epoch. — status: partly done (classes for labels: T23; detections get status + reason incl. class: T08;
  real detections wait for T06)
- I16 [Joerg] (on the Board as T35) Tracing over the stitched sky: draw labels, paths and motion tracks (and detections) on the
  explore map (T30/T32 per-epoch HiPS), not only on a single field, so a mover can be followed across
  epochs while panning. The data is there: `labels[].positions`, `known_objects`, `detections` carry
  RA/Dec per frame; Aladin overlays (catalogue + polyline) can draw them. — status: on the Board (T35, in review)
- I17 [Joerg] Draw paths, not just positions: for every label, known object and detection, a line
  through its per-frame positions with a tick per frame and colour from early to late (data is
  already in the JSON). — status: done (T22)
- I18 [Joerg] Trail image: sum one burst (or one epoch) into a single picture so movers show as dot rows
  or streaks without playing the blink. — status: done (T23 trail view)
- I19 [Jonathan] Host the Live API + viewer in a cloud region next to AWS us-east-1 (where the SPHEREx
  bucket is): Google Cloud `us-east4` (Ashburn) or Azure `East US` (Virginia), VM with 2 vCPU / 4 GB
  (GCP e2-medium / Azure B2s), free credits available. Why: from Europe S3 gave 0.04-0.1 MB/s per
  connection in the afternoon (another us-east-1 bucket too), so live deep-zoom tiles take 20-60 s;
  next to the bucket they should take ~1 s. Needs: Dockerfile, warm-up script, HTTPS, guide; would
  also cover T14. — status: done (T47; covers much of T14)
- I20 [Mati] Done from the gap scan (2026-11-14): play the series like a video (T45), light curves + spectra on
  the fly (T49), CI on every push (T46); details in their task files. — status: done

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
