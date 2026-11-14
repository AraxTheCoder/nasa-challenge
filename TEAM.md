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
| T02 | A: Download cutouts for one target into `data/`, with a cache so re-runs don't re-download | | open | | Needs T01 |
| T03 | A: Align cutouts to one common WCS grid (north up) and get the wavelength at the target position per frame | | open | | Needs T02. Wavelength varies across a SPHEREx image |
| T04 | A: Render frames to PNG/WebP and write `target.json` per CONTRACTS, validated against the schema | | open | | Needs T03. First real target = end-to-end milestone |
| T05 | A: Batch-bake 3–5 demo targets and publish them to `web/targets/` (size budget in CONTRACTS) | | open | | Needs T04 and the target list from T10 |
| T06 | B: Mover detection v0 on the fixture: source extraction per frame, match across frames, keep what moves | | open | | Start on `fixtures/`, switch to real data after T04 |
| T07 | B: JPL SB Identification cross-match: known small bodies in the field per frame time → `known_objects` | | open | | Needs SPHEREx position from Horizons (-163182) as observer |
| T08 | B: Classify detections as known / unknown / artifact and write them into `target.json` | | open | | Needs T06, T07 |
| T09 | B: Sanity check on a known bright asteroid in real SPHEREx data: do we recover it at the JPL position? | | open | | Needs T04, T08 |
| T10 | B: "Planet X mode": pick a slow distant body (dwarf planet), check it's detectable across epochs, propose the demo target list | | open | | Feeds T05 |
| T11 | C: Static viewer skeleton: load `index.json` + `target.json` from the fixture, show frames, blink between two | Mati | done | `mati/T11-viewer-skeleton` | [tasks/T11](tasks/T11-viewer-skeleton.md). Vanilla JS, no build. Reads static target folders; not yet wired to the Live API (v0.3). Run: see `web/README.md` |
| T12 | C: Epoch timeline and band/wavelength filter | | open | | Needs T11 |
| T13 | C: Overlay detections and known objects, with a clear "synthetic" badge where it applies | | open | | Needs T11 |
| T14 | C: Deploy: static viewer (e.g. GitHub Pages) + Live API on a host that runs Python, viewer pointed at it (contracts v0.3) | | open | | Needs T11, T18, T20. Reworded 2026-11-14 for live data (was: pre-baked targets, no live API calls) |
| T15 | C: Submission text, data credits and AI-use disclosure | | open | | Needs official text in `docs/CHALLENGE.md` |
| T16 | C: Demo video and slides | | open | | After feature freeze |
| T17 | A: Compute wavelength-matched `pairs` across epochs (+ `bandwidth_um`) in `target.json` (contracts v0.2) | Joerg | open | | Part of T03/T04 output. Rule in CONTRACTS "Pair" |
| T18 | C: Live API service: `GET /api/target?ra=&dec=&size=` builds (pipeline + detect) or serves from cache, progress while building, CORS (contracts v0.3) | Jonathan | done | `jonathan/T18-live-api` | `python -m server [--fixture]`, see `server/README.md`. Live mode works once `pipeline.build` (T02–T04) exists; until then `--fixture` |
| T19 | A: Labels on the images: catalogue names/positions (SIMBAD, Gaia DR3 with proper motion, CatWISE) into `target.json` | Joerg | doing | `joerg/T19-labels` | [task file](tasks/T19-labels.md) |
| T20 | C: Viewer ↔ Live API: RA/Dec/size input, `?ra=&dec=&size=` in the page URL, request + poll with progress, load from `target_url`, quick picks for the official test fields (contracts v0.3) | Mati | doing | `mati/T20-live-api-client` | [tasks/T20](tasks/T20-live-api-client.md) |

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

## Ideas

Format: `[name] idea — status: new`. Agents don't act on an idea until a human moves it to the Board.

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
