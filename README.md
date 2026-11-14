# Planet X and SPHEREx (working title)

NASA Space Apps Challenge 2026 entry for the challenge "Planet X and SPHEREx".

A public, browser-based blink comparator for SPHEREx data: pick a patch of sky, flip between
survey epochs, and see what moved. Known asteroids and comets are labelled, so unlabelled movers
stand out.

**Status:** scaffolding only, no application code yet. See `TEAM.md` for the plan and task board.

## How it works

1. `pipeline/`: queries IRSA for all SPHEREx exposures covering a position, downloads cutouts,
   aligns them and writes display frames plus one `target.json` per target.
2. `detect/`: finds sources that move between frames and cross-matches them with known small
   bodies from JPL.
3. `web/`: static viewer that reads only the baked target folders. No live API calls in the demo.

Interfaces between the three parts: `docs/CONTRACTS.md`.

## How to run

_TODO once there is code._ Planned entry points:

```
python -m pipeline.build --id <id> --ra <deg> --dec <deg> --size <arcmin>
python -m detect.run data/targets/<id>
python -m pipeline.publish <id>
# then serve web/ with any static file server
```

## Repository layout

| Path | What |
|---|---|
| `pipeline/` | data access and frame building (Python) |
| `detect/` | mover detection and cross-match (Python) |
| `web/` | static viewer, deployed to GitHub Pages |
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
