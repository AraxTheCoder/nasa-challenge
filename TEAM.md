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
| C | Frontend & submission | `web/` | Mati |

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
| T01 | A: IRSA query: list all SPHEREx exposures covering an RA/Dec (SIA/TAP), with time, detector, access URL | Joerg | doing | `joerg/T01-irsa-query` | Record the query + timestamp for provenance |
| T02 | A: Download cutouts for one target into `data/`, with a cache so re-runs don't re-download | | open | | Needs T01 |
| T03 | A: Align cutouts to one common WCS grid (north up) and get the wavelength at the target position per frame | | open | | Needs T02. Wavelength varies across a SPHEREx image |
| T04 | A: Render frames to PNG/WebP and write `target.json` per CONTRACTS, validated against the schema | | open | | Needs T03. First real target = end-to-end milestone |
| T05 | A: Batch-bake 3–5 demo targets and publish them to `web/targets/` (size budget in CONTRACTS) | | open | | Needs T04 and the target list from T10 |
| T06 | B: Mover detection v0 on the fixture: source extraction per frame, match across frames, keep what moves | | open | | Start on `fixtures/`, switch to real data after T04 |
| T07 | B: JPL SB Identification cross-match: known small bodies in the field per frame time → `known_objects` | | open | | Needs SPHEREx position from Horizons (-163182) as observer |
| T08 | B: Classify detections as known / unknown / artifact and write them into `target.json` | | open | | Needs T06, T07 |
| T09 | B: Sanity check on a known bright asteroid in real SPHEREx data: do we recover it at the JPL position? | | open | | Needs T04, T08 |
| T10 | B: "Planet X mode": pick a slow distant body (dwarf planet), check it's detectable across epochs, propose the demo target list | | open | | Feeds T05 |
| T11 | C: Static viewer skeleton: load `index.json` + `target.json` from the fixture, show frames, blink between two | | open | | No build step if possible |
| T12 | C: Epoch timeline and band/wavelength filter | | open | | Needs T11 |
| T13 | C: Overlay detections and known objects, with a clear "synthetic" badge where it applies | | open | | Needs T11 |
| T14 | C: Deploy to GitHub Pages with pre-baked targets, target picker, no live API calls | | open | | Needs T11; real targets arrive with T05 |
| T15 | C: Submission text, data credits and AI-use disclosure | | open | | Needs official text in `docs/CHALLENGE.md` |
| T16 | C: Demo video and slides | | open | | After feature freeze |

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

## Log

Append-only, newest at the bottom. Format: `date time [name] done / next / gotchas`.

- 2026-11-14 [joerg + Claude] Done: team scaffolding (CLAUDE.md, TEAM.md, contracts v0.1, schema,
  synthetic fixture, folders, SessionStart hook). Next: assign tracks, paste official challenge
  text, agree on contracts, claim T01/T06/T11. Gotchas: the fixture is fully synthetic, never show
  it as SPHEREx data; the SPHEREx data DOI in README is still a TODO.
