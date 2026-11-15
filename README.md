# Planet X and SPHEREx (working title)

[![tests](https://github.com/jabra11/nasa-challenge/actions/workflows/tests.yml/badge.svg)](https://github.com/jabra11/nasa-challenge/actions/workflows/tests.yml)

NASA Space Apps Challenge 2026 entry for the challenge "Planet X and SPHEREx".

A public, browser-based blink comparator for SPHEREx data: pick a patch of sky, flip between
survey epochs, and see what moved. Known asteroids and comets are labelled, so unlabelled movers
stand out.

**Status:** work in progress, running on real data. Type any RA/Dec (or pick one of the five official
test fields): the Live API fetches the SPHEREx images covering it (NASA/IPAC IRSA, AWS Open Data),
aligns them and the viewer blinks them. What works today:

- blink two frames, play the whole series like a video, or show the difference A − B;
  wavelength-matched pairs across epochs, an epoch timeline and a wavelength filter
- catalogue names (SIMBAD, Gaia DR3) that follow moving stars, motion paths, a motion class per object
- known asteroids and comets in the field (MPC orbit catalogue, SkyBoT / JPL; positions as seen from SPHEREx)
- spectrum and light curve at any point (aperture photometry on the SPHEREx images)
- a pan-and-zoom map of the whole sky (SPHEREx all-sky maps, live deep zoom) with the field's epochs
- our own detection of things that are there at one moment and gone at others, seen by both simultaneous
  detectors (T06), with artifacts such as afterglows of bright stars sorted out (T67)
- per field: sources with an unusual spectrum (T86) and sources that change brightness at the same wavelength
  (T61), as lists and rings on the map; SPHEREx's quality flags as a mask (T60)
- a moving star's motion measured from SPHEREx alone, next to the catalogue value, and its distance when the
  parallax fit is consistent (T91: Barnard's Star 10.46 ± 0.19″/yr vs Gaia 10.39; Epsilon Indi B 3.49 pc vs 3.64)
- a guided tour of the five official targets: "▶ Tour" on the map or `?tour=1` in a link (T92)
- a discussion per map tile: "💬" on the map shows how often the tile was viewed and what others wrote; comments,
  replies and "look here" positions, plus recent discussions across the sky (T120)
- chemistry maps: where ices, PAH or hydrogen lines absorb or emit, one feature or several as one colour picture,
  presets tried on real fields, and a redshift for galaxies (T93, T96, T107–T109)

Synthetic data appears only in fixture mode and tests, and is labelled as such everywhere. Plan and task board:
`TEAM.md`.

## How it works

1. `pipeline/`: finds all SPHEREx exposures covering a position (IRSA TAP or a local index),
   reads cutouts (IRSA, or byte ranges from the AWS bucket), aligns them north up on one grid and
   writes display frames plus one `target.json` per field. Also: catalogue labels, motion summaries,
   photometry, shift-and-stack.
2. `detect/`: known asteroids and comets in the field (local MPC orbit catalogue, SkyBoT / JPL), our own
   detections from the cached SPHEREx images (T06), classification as known / unknown / artifact (T08, T67),
   and sources that change brightness (T61).
3. `server/`: Live API. Builds a field on request for any RA/Dec (step 1), caches it, adds labels and
   known objects when the viewer asks, serves photometry, field spectra, chemistry maps and sky-map tiles.
4. `web/`: static viewer, no build step. Asks the Live API for a field, shows build progress, then
   blinks, plays and compares the frames. Details and URL options: `web/README.md`.
5. `tilegen/`: renders deep-zoom sky-map tiles from the SPHEREx images, locally or on a small VM next
   to the AWS bucket (`deploy/`).

Interfaces between the three parts: `docs/CONTRACTS.md`.

## How to run

Needs **Python 3.12 or newer** (3.12–3.14 tested) and git. Check with `python3 --version`; if yours is
older, see "Python too old" below. From a fresh clone:

```bash
git clone git@github.com:jabra11/nasa-challenge.git
cd nasa-challenge
python3 -m venv .venv
source .venv/bin/activate                  # Linux, macOS, WSL. Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock      # exact versions, same for everyone
python web/dev.py
```

`web/dev.py` starts the Live API (port 8000) and the viewer (port 8080), opens
<http://localhost:8080/web/> in your browser and stops both on Ctrl+C. Type RA/Dec or pick one of the
official test fields. Each time you come back: `cd nasa-challenge`, activate the venv, `python web/dev.py`.

On the first start the Live API also fetches its local data in the background (T71): the MPC orbit
catalogue for known asteroids and comets (~95 MB, refreshed weekly) and the SPHEREx image index (a few
minutes). Everything works from the first second; until these are ready, known objects and image
searches use slower online services. Its progress shows in the terminal as `[data setup] ...`;
`python -m server --no-data-setup` skips it.

| Option | What |
|---|---|
| `--fixture` / `--live` | synthetic demo field for every request / real SPHEREx data (default) |
| `--api-port N`, `--web-port N` | other ports if 8000 / 8080 are taken |
| `--lan` | others on your network can open the printed URL too |
| `--host ADDR` | listen on one address only, e.g. `--host 10.0.0.2` for the WireGuard network (overrides `--lan`) |
| `--no-browser` | just print the URL |
| `--warm` | also pre-build the five official test fields (first time: tens of minutes; `web/warm.py`) |

Activating is only a shortcut. Without it, call the venv's Python directly:
`.venv/bin/python web/dev.py` (Windows: `.venv\Scripts\python web\dev.py`).

Troubleshooting:

- **Python too old** (numpy 2.5 needs 3.12+): install 3.12 or newer from python.org, your package
  manager (`sudo apt install python3.12 python3.12-venv`), or with uv: `uv python install 3.12`, then
  create the venv with that Python (`python3.12 -m venv .venv` or `uv venv --python 3.12 .venv`).
  If an old `.venv` exists, delete it first.

- **Activation fails**: on Linux/macOS/WSL it is `source .venv/bin/activate` (with `source`; running
  the file directly gives "Permission denied"). In WSL use the Linux commands, not the Windows ones.
  Or skip activating, see above.
- **"Port … is already in use"**: another server still runs (often an old `python -m http.server`).
  Stop it or use `--api-port` / `--web-port`.
- **"Missing Python packages"**: the venv is not active, or the install step was skipped.
- **Windows: "running scripts is disabled"** when activating: run
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use `cmd` and `.venv\Scripts\activate.bat`.
- **WSL**: the Windows browser opens automatically, and `localhost` URLs work from Windows. `--lan`
  reaches other machines only with WSL mirrored networking (`networkingMode=mirrored` in `.wslconfig`).
- Without the launcher, or to run the parts separately: see `web/README.md` and `server/README.md`.

In the viewer: `Space` blink, `P` play the series, `D` difference A − B, `X` swap A/B, `M` match B
to A's wavelength, `←`/`→` step through frames. Click an object for its details and history.

Pipeline and detection on their own (all entry points: `docs/CONTRACTS.md`):

```
python -m pipeline.query --ra <deg> --dec <deg>            # list SPHEREx images covering a position (T01)
python -m pipeline.build --id <id> --ra <deg> --dec <deg> --size <arcmin>   # build a field into data/targets/
python -m detect.run data/targets/<id>                      # known asteroids/comets + classification
python -m pipeline.photometry data/targets/<id> --ra <deg> --dec <deg>     # fluxes in every frame
```

## Dependencies

All versions are pinned exactly so everyone runs the same thing.

| File | What |
|---|---|
| `pipeline/requirements.txt`, `server/requirements.txt` | the packages each part needs, `==` pins, edited by hand |
| `requirements-dev.txt` | test tools on top (pytest, httpx, jsonschema, playwright) |
| `requirements.lock`, `requirements-dev.lock` | everything incl. sub-dependencies, generated; **install from these** |

Tests: `python -m pip install -r requirements-dev.lock` (and `playwright install chromium` for the
browser test).

CI (`.github/workflows/tests.yml`, T46) runs on every push to main and every pull request: the Python
tests, the contract checks in `tests/` (both fixtures validate against the schema, presets are sane), the Node
tests `web/tests/*.mjs` (e.g. the sky-map projection) and the browser test in fixture mode (no external servers). Run the same locally before pushing:
`python -m pytest detect server pipeline tilegen tests -q && python web/tests/browser_test.py`.

Updating dependencies (whoever adds or bumps a package): change the pin in the `requirements*.txt`
file, regenerate both locks, commit all of it together, and add a line under TEAM.md "Decisions":

```
uv pip compile server/requirements.txt --python-version 3.12 --universal -o requirements.lock
uv pip compile requirements-dev.txt --python-version 3.12 --universal -o requirements-dev.lock
```

## Repository layout

| Path | What |
|---|---|
| `pipeline/` | data access, frame building, labels, photometry (Python) |
| `detect/` | known objects, classification, mover detection (Python) |
| `server/` | Live API: builds and caches fields on request (Python, FastAPI) |
| `web/` | static viewer (no build step); `web/dev.py` runs API + viewer locally |
| `tilegen/`, `deploy/` | deep-zoom sky-map tiles; scripts for the tile VM |
| `fixtures/` | tiny committed samples, both simulated (not SPHEREx data): `demo-synthetic` (minimal), `demo-epochs` (every field of the contract) |
| `tests/` | contract checks run by CI |
| `data/` | local downloads and caches, not in git |
| `docs/` | challenge text, contracts, JSON schema |
| `TEAM.md`, `tasks/`, `CLAUDE.md` | plan, task board, task notes, rules for the team's Claude Code sessions |

## Data credits

Text for the project page: `docs/SUBMISSION.md`.

- **SPHEREx** (NASA): Data Release 1 spectral images (DOI
  [10.26131/IRSA678](https://www.ipac.caltech.edu/doi/10.26131/IRSA678)), the DR1 Spectral All-Sky Cube
  (DOI [10.26131/IRSA679](https://www.ipac.caltech.edu/doi/10.26131/IRSA679)) and Quick Release 3 (DOI
  [10.26131/IRSA662](https://www.ipac.caltech.edu/doi/10.26131/IRSA662)), from the NASA/IPAC Infrared
  Science Archive (IRSA) and its AWS Open Data bucket `nasa-irsa-spherex`. This project makes use of data
  products from the Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices
  Explorer (SPHEREx), which is a joint project of the Jet Propulsion Laboratory and the California
  Institute of Technology, and is funded by the National Aeronautics and Space Administration.
- **IRSA** (TAP, cutouts, HiPS): this project has made use of the NASA/IPAC Infrared Science Archive,
  which is funded by the National Aeronautics and Space Administration and operated by the California
  Institute of Technology.
- **2MASS** and **AllWISE** all-sky maps (IRSA HiPS). 2MASS is a joint project of the University of
  Massachusetts and the Infrared Processing and Analysis Center / Caltech, funded by NASA and the
  National Science Foundation. WISE is a joint project of the University of California, Los Angeles, and
  the Jet Propulsion Laboratory / Caltech, funded by NASA.
- **JPL Horizons** and the **JPL Small-Body Identification** API, Solar System Dynamics group, Jet
  Propulsion Laboratory.
- **Gaia DR3**: this work has made use of data from the European Space Agency (ESA) mission Gaia
  (<https://www.cosmos.esa.int/gaia>), processed by the Gaia Data Processing and Analysis Consortium
  (DPAC, <https://www.cosmos.esa.int/web/gaia/dpac/consortium>). Funding for the DPAC has been provided
  by national institutions, in particular the institutions participating in the Gaia Multilateral
  Agreement.
- **SIMBAD** and **VizieR**, operated at CDS, Strasbourg, France (Wenger et al. 2000; Ochsenbein et al.
  2000), also through the Harvard mirrors; the **AAVSO International Variable Star Index (VSX)** through
  VizieR; the SPHEREx per-detector **HiPS** maps of CDS (HiPS: Fernique et al. 2015).
- **Minor Planet Center**: this project has made use of data and services provided by the International
  Astronomical Union's Minor Planet Center (orbit catalogue MPCORB). **SkyBoT**, IMCCE / Paris
  Observatory (Berthier et al. 2006).
- Software: astropy (Astropy Collaboration 2013, 2018, 2022), astropy-healpix, reproject, pyvo, numpy,
  scipy, Pillow, FastAPI, uvicorn.

The SPHEREx wording follows IRSA's release pages (`irsa.ipac.caltech.edu/data/SPHEREx/docs/`, read
2026-11-15); the other texts are the archives' standard acknowledgements, written from memory: compare
with each archive's page before a formal publication.

Anything simulated or injected in this project is labelled as synthetic in the data and in the UI.

## AI-use disclosure

This project was built with the help of Claude (Anthropic) through Claude Code, used for
planning, code, documentation and repo coordination. Each team member worked with their own
Claude Code session; the rules those sessions follow are in `CLAUDE.md`. All results were
reviewed by the team.

## Team

_TODO: names._

## License

_TODO._
