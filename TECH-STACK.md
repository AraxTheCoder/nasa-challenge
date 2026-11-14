# Tech stack

Overview of the technologies used in this repo, as of 2026-11-14. Status marks what is actually in
the code (**in use**) versus what is only planned in `TEAM.md` / `docs/CONTRACTS.md` (**planned**).
Interfaces and rules live in `docs/CONTRACTS.md`; this file only summarises.

## Architecture at a glance

```
IRSA (TAP + FITS cutouts) ──► pipeline/ (A, Python) ──► data/targets/<id>/  frames + target.json
JPL Horizons / SB Ident   ──► detect/   (B, Python) ──► adds known_objects + detections
                                                     ──► pipeline.publish ──► web/targets/
                                         web/ (C, static site, GitHub Pages) reads only JSON + images
```

Everything is baked offline. The frontend makes no live API calls. The only interface between
the tracks is the target folder (`index.json`, `target.json`, `frames/*.png|webp`), validated
against `docs/target.schema.json`.

## Languages and runtime

| What | Choice | Status |
|---|---|---|
| Pipeline and detection | Python 3 (`from __future__ import annotations`, dataclasses, type hints) | in use |
| Frontend | HTML/CSS/JavaScript, static, ideally no build step (T11) | planned |
| Data interchange | JSON (JSON Schema draft 2020-12), 8-bit PNG/WebP frames | in use |

## Python dependencies (`pipeline/requirements.txt`)

| Package | Used for | Status |
|---|---|---|
| `astropy>=7` | time conversion (`astropy.time`), later FITS I/O, WCS, reprojection | in use (time) |
| `pyvo>=1.6` | IRSA TAP queries (`pyvo.dal.TAPService`) | in use |
| `numpy>=2` | arrays, epoch clustering | in use |
| `requests>=2.31` | HTTP downloads of cutouts (T02) | listed, planned |
| `astroquery` | possible alternative for JPL Horizons / IRSA access | mentioned in Decisions, not added |

Further libraries for alignment (e.g. `reproject`), source extraction (e.g. `photutils`/`sep`),
image rendering (e.g. `Pillow`) and schema validation (`jsonschema`) are not chosen yet. Add them
to `requirements.txt` when a task needs them.

The fixture generator `fixtures/make_demo_synthetic.py` uses the standard library only.

## External data services

| Service | Used for | Access |
|---|---|---|
| NASA/IPAC IRSA, SPHEREx collections `spherex_dr1`, `spherex_qr3` (+ `*_deep`) | exposure list per sky position, FITS images and cutouts | TAP `https://irsa.ipac.caltech.edu/TAP` (ObsCore + CAOM `plane`/`artifact` join); cutouts via `?center=ra,dec&size=..deg` on the FITS URL |
| JPL Horizons | SPHEREx observer position (ID `-163182`) | REST API, planned (T07) |
| JPL Small-Body Identification API | known asteroids/comets in the field per frame time | REST API, planned (T07) |

SPHEREx data facts relevant to the stack: one image per detector (D1-D6), 2040×2040 px,
6.15″/px, linear variable filter (wavelength varies across the image, `WCS-WAVE` table),
FLAGS bitmask plane. Details in the TEAM.md Log.

## Entry points (CLI)

| Command | Track | Status |
|---|---|---|
| `python -m pipeline.query --ra <deg> --dec <deg> [--out ...]` | A | in use (T01) |
| `python -m pipeline.build --id <id> --ra <deg> --dec <deg> --size <arcmin>` | A | planned |
| `python -m detect.run <target_dir>` | B | planned |
| `python -m pipeline.publish <id> [--to web/targets]` | A | planned |
| `python fixtures/make_demo_synthetic.py .` | – | in use |

## Hosting, tooling and workflow

| What | Choice |
|---|---|
| Hosting | GitHub Pages, static, pre-baked targets (T14) |
| Version control | Git on GitHub, branches `<name>/T<id>-<slug>`, small merges to `main` |
| Coordination | `TEAM.md` board, `CLAUDE.md` agent rules, one Claude Code session per person |
| Claude Code config | `.claude/settings.json`: SessionStart hook runs `git fetch` + `git status` |
| Local caches | `data/` (gitignored), no `.fits` in git, size budget ≤ 5 MB per target, ≤ 50 MB in `web/targets/` |
| Ignored tooling | `.gitignore` already covers venv, pytest, ruff, mypy, Jupyter, node/Vite artefacts |

No test framework, linter config or CI pipeline is set up yet.
