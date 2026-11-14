# Planet X and SPHEREx (working title)

NASA Space Apps Challenge 2026 entry for the challenge "Planet X and SPHEREx".

A public, browser-based blink comparator for SPHEREx data: pick a patch of sky, flip between
survey epochs, and see what moved. Known asteroids and comets are labelled, so unlabelled movers
stand out.

**Status:** work in progress. The viewer and the Live API run end to end; until the pipeline can
build real fields (T02–T04), every field is the synthetic demo, clearly labelled as such. See
`TEAM.md` for the plan and task board.

## How it works

1. `pipeline/`: queries IRSA for all SPHEREx exposures covering a position, downloads cutouts,
   aligns them and writes display frames plus one `target.json` per target.
2. `detect/`: finds sources that move between frames and cross-matches them with known small
   bodies from JPL.
3. `server/`: Live API. Builds a field on request for any RA/Dec (steps 1 and 2) and caches it.
4. `web/`: static viewer. Asks the Live API for a field, shows build progress, then blinks the frames.

Interfaces between the three parts: `docs/CONTRACTS.md`.

## How to run

Needs **Python 3.11 or newer** and git. From a fresh clone:

```bash
git clone git@github.com:jabra11/nasa-challenge.git
cd nasa-challenge
python3 -m venv .venv
source .venv/bin/activate                  # Linux, macOS, WSL. Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r server/requirements.txt
python web/dev.py
```

`web/dev.py` starts the Live API (port 8000) and the viewer (port 8080), opens
<http://localhost:8080/web/> in your browser and stops both on Ctrl+C. Type RA/Dec or pick one of the
official test fields. Each time you come back: `cd nasa-challenge`, activate the venv, `python web/dev.py`.

| Option | What |
|---|---|
| `--fixture` / `--live` | synthetic demo field for every request / real SPHEREx data from IRSA. Default: live once `pipeline.build` exists, fixture until then |
| `--api-port N`, `--web-port N` | other ports if 8000 / 8080 are taken |
| `--lan` | others on your network can open the printed URL too |
| `--no-browser` | just print the URL |

Activating is only a shortcut. Without it, call the venv's Python directly:
`.venv/bin/python web/dev.py` (Windows: `.venv\Scripts\python web\dev.py`).

Troubleshooting:

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

Pipeline and detection on their own (track A/B, as they become available):

```
python -m pipeline.query --ra <deg> --dec <deg>            # list SPHEREx images covering a position (T01)
python -m pipeline.build --id <id> --ra <deg> --dec <deg> --size <arcmin>   # planned (T02-T04)
python -m detect.run data/targets/<id>                      # planned (T06-T08)
```

## Repository layout

| Path | What |
|---|---|
| `pipeline/` | data access and frame building (Python) |
| `detect/` | mover detection and cross-match (Python) |
| `server/` | Live API: builds and caches fields on request (Python, FastAPI) |
| `web/` | static viewer (no build step); `web/dev.py` runs API + viewer locally |
| `fixtures/` | tiny committed samples; `demo-synthetic` is simulated, not SPHEREx data |
| `data/` | local downloads and caches, not in git |
| `docs/` | challenge text, contracts, JSON schema |

## Data credits

- **SPHEREx** data from the NASA/IPAC Infrared Science Archive (IRSA), operated by
  Caltech/IPAC. _TODO: add the exact data set name, release (QR2/QR3) and DOI from the IRSA
  SPHEREx page, plus the acknowledgement text IRSA asks for._
- **JPL Horizons** and the **JPL Small-Body Identification** API, Solar System Dynamics group,
  Jet Propulsion Laboratory.
- _TODO: astropy / astroquery / pyvo citations once we use them._

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
