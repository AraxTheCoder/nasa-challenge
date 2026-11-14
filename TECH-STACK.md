# Tech stack

Overview of the technologies in this repo, as of 2026-11-14 (rewritten for T52; the first version
described the pre-baked plan that the live-data decision replaced). Interfaces and rules live in
`docs/CONTRACTS.md`; this file only summarises.

## Architecture at a glance

```
IRSA TAP / local index (T31) ─┐
IRSA cutouts / AWS S3 ranges ─┴► pipeline/ (A) ──► data/targets/<id>/  frames + target.json
                                     ▲                        │
SIMBAD, Gaia DR3 ──► pipeline.labels ┤                        │ served by
SkyBoT, JPL Horizons ──► detect/ (B) ┘                        ▼
                              server/ (Live API, FastAPI) ◄──► web/ (static viewer, vanilla JS)
IRSA / CDS HiPS, tilegen (T42/T47) ──► /api/sky/... ──► sky map in web/
```

Everything is built live on request and cached; the viewer only talks to the Live API. The interface
between the tracks is the target folder (`index.json`, `target.json`, `frames/*.png`), validated
against `docs/target.schema.json`.

## Languages and runtime

| What | Choice |
|---|---|
| Pipeline, detection, Live API, tile generator | Python 3.12+ (`from __future__ import annotations`, type hints) |
| Frontend | HTML/CSS/JavaScript ES modules, no framework, no build step; WebGL for the sky map |
| Data interchange | JSON (JSON Schema draft 2020-12), 8-bit PNG frames with alpha (alpha 0 = no data) |

## Python dependencies (pinned, `requirements.lock`)

| Package | Used for |
|---|---|
| `astropy` | FITS, WCS, time, coordinates |
| `reproject` | aligning cutouts onto one north-up grid |
| `pyvo` | IRSA / Gaia / SIMBAD TAP queries |
| `numpy`, `scipy` | arrays, interpolation, statistics |
| `pillow` | PNG frames and tiles |
| `requests` | HTTP downloads, JPL / SkyBoT APIs |
| `fastapi`, `uvicorn` | Live API and tile generator |
| `astropy-healpix` | HiPS tile geometry on the server |
| dev: `pytest`, `httpx`, `jsonschema`, `playwright` | tests, contract checks, browser test |

The fixture generators in `fixtures/` use the standard library only. Updating a pin: README "Dependencies".

## External data services

| Service | Used for |
|---|---|
| NASA/IPAC IRSA, SPHEREx `spherex_dr1` / `spherex_qr3` | exposure list (TAP), FITS cutouts, all-sky SPHEREx cube HiPS, 2MASS + AllWISE HiPS |
| AWS Open Data `nasa-irsa-spherex` (us-east-1) | the same level-2 images, read with HTTP range requests (T33) |
| CDS | SPHEREx per-detector HiPS, SIMBAD (Harvard mirror when CDS is down) |
| ESA Gaia archive | Gaia DR3 positions + proper motions for labels |
| IMCCE SkyBoT | candidate asteroids and comets in a field (T51) |
| JPL Horizons, JPL SB Identification | positions as seen from SPHEREx (ID `-163182`); fallback candidate search |

SPHEREx facts that shape the stack: six detectors, 2040×2040 px, 6.15″/px, linear variable filters
(wavelength varies across the image, `WCS-WAVE` table), FLAGS bitmask, ~6 months between all-sky passes.

## Entry points

The full list with arguments is in `docs/CONTRACTS.md` → "Entry points". Day to day:
`python web/dev.py` (API + viewer), `python -m pipeline.build …`, `python -m detect.run …`.

## Hosting, tooling and workflow

| What | Choice |
|---|---|
| Running it | locally with `web/dev.py`; public hosting is T14 (open) |
| Tile generator | Google Cloud VM `us-east4` next to the AWS bucket (T47, `deploy/`); the rest stays local |
| Tests | pytest (`detect server pipeline tilegen tests`), Playwright browser test, Node checks in `web/tests/` |
| CI | GitHub Actions on every push and PR (T46, `.github/workflows/tests.yml`) |
| Version control | Git on GitHub, branches `<name>/T<id>-<slug>`, small merges to `main` |
| Coordination | `TEAM.md` board, `tasks/` notes, `CLAUDE.md` agent rules, one Claude Code session per person |
| Local caches | `data/` (gitignored); no `.fits` and no real fields in git; fixtures ≤ 5 MB each |
