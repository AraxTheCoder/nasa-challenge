# Contracts (v0.1, PROPOSED)

Interfaces between the three tracks. This file only changes together with a dated line under
TEAM.md "Decisions" that says why.

## Data flow

```
pipeline/ (A)                detect/ (B)                       web/ (C)
IRSA → cutouts → aligned  →  adds known_objects + detections →  reads index.json + target.json
frames + target.json         to the same target.json            and the frame images, nothing else
```

The frontend never calls IRSA or JPL. Everything it shows comes from a target folder.

## Folder layout

```
pipeline/                      A: Python package, data access + frame building
detect/                        B: Python package, mover detection + cross-match
web/                           C: static site, deployed to GitHub Pages
web/targets/                   baked targets for the demo (committed, see size budget)
data/                          gitignored: downloads, caches, work in progress
data/raw/                      cached downloads (FITS)
data/targets/<id>/             pipeline + detect output before publishing
fixtures/targets/<id>/         tiny committed samples for tests and frontend development
docs/target.schema.json        JSON Schema for target.json
```

A **target folder** looks the same in `data/targets/`, `fixtures/targets/` and `web/targets/`:

```
<targets-root>/index.json      list of targets
<targets-root>/<id>/target.json
<targets-root>/<id>/frames/<frame_id>.png|webp
```

Size budget for anything committed: one target ≤ 5 MB, `web/targets/` ≤ 50 MB in total.

## index.json

```json
{
  "schema_version": "0.1",
  "targets": [
    { "id": "demo-synthetic", "name": "Synthetic demo field", "synthetic": true,
      "ra_deg": 150.0, "dec_deg": 2.2, "n_frames": 4 }
  ]
}
```

## target.json

Formal schema: `docs/target.schema.json`. Example: `fixtures/targets/demo-synthetic/target.json`.

| Field | Written by | Meaning |
|---|---|---|
| `schema_version` | A | `"0.1"` |
| `id` | A | folder name, `[a-z0-9-]+` |
| `name` | A | display name |
| `synthetic` | A | `true` if the frames are simulated. Must be shown in the UI |
| `center` | A | `{ra_deg, dec_deg}`, ICRS |
| `size_arcmin` | A | side length of the square field |
| `image` | A | `{width, height, pixel_scale_arcsec}`, identical for all frames |
| `provenance` | A, B | list of `{service, query, retrieved_utc}`, enough to repeat the request |
| `frames` | A | list of frames, sorted by time |
| `known_objects` | B | catalogued small bodies in the field. A writes `[]` |
| `detections` | B | moving sources found by us. A writes `[]` |

### Frame

```json
{ "id": "f000", "time_utc": "2026-05-01T00:00:00Z", "mjd": 61161.0, "epoch": 1,
  "detector": 3, "wavelength_um": 1.52, "image": "frames/f000.png",
  "obs_id": "…", "source_url": "…" }
```

- `epoch`: which all-sky survey pass the frame belongs to (1, 2, …). Blinking between epochs is
  the main view.
- `wavelength_um`: wavelength **at the target centre**. SPHEREx uses linear variable filters, so
  wavelength changes across a single exposure; one number per cutout is an approximation.
- `image`: path relative to the target folder. 8-bit PNG or WebP, already stretched for display.
- `obs_id`, `source_url`: where the frame came from. `null` for synthetic frames.

### Image and coordinate conventions

- All frames of a target are resampled to **one common grid**: same size, same pixel scale, north
  up, east left, centred on `center`.
- Pixel coordinates `x, y`: 0-based, origin at the top-left pixel centre, `x` to the right, `y`
  down. They index the frame image directly.
- Every sky position in the JSON carries both `ra_deg/dec_deg` and `x/y`, so the frontend needs
  no WCS maths.

### Known object

```json
{ "name": "(4) Vesta", "source": "jpl-sbident", "synthetic": false,
  "positions": [ { "frame_id": "f000", "ra_deg": 150.01, "dec_deg": 2.21, "x": 20.0, "y": 48.0 } ] }
```

Positions are predicted for each frame time as seen from SPHEREx (Horizons ID `-163182`), not
from the geocentre.

### Detection

```json
{ "id": "d001", "status": "known", "matched_object": "(4) Vesta", "synthetic": false,
  "score": 0.93,
  "track": [ { "frame_id": "f000", "ra_deg": 150.01, "dec_deg": 2.21, "x": 20.0, "y": 48.0 } ],
  "motion": { "rate_arcsec_per_hr": 30.5, "pa_deg": 90.0 } }
```

- `status`: `known` (matches a known object), `unknown` (moves, no match), `artifact` (rejected,
  kept for debugging; the UI hides these by default).
- `matched_object`: `name` of a known object, or `null`.
- `synthetic`: `true` if the source was injected by us. Must be shown in the UI.
- `score`: 0–1, higher is more convincing.
- `motion.pa_deg`: direction of motion, degrees east of north.

## Entry points

```
python -m pipeline.build --id <id> --ra <deg> --dec <deg> --size <arcmin> [--out data/targets]
python -m detect.run <target_dir>
python -m pipeline.publish <id> [--to web/targets]      # copies a target and updates index.json
```

```python
# pipeline/build.py (A)
def build_target(target_id: str, ra_deg: float, dec_deg: float,
                 size_arcmin: float, out_root: Path = Path("data/targets")) -> Path:
    """Query, download, align, render. Returns the target folder with a valid target.json."""

# detect/run.py (B)
def detect(target_dir: Path) -> dict:
    """Read target.json + frames, fill known_objects and detections, write target.json back.
    Touches only those two fields and appends to provenance. Returns the updated dict."""
```

`detect` works on the rendered frames and the JSON. If B needs the aligned FITS data as well,
that is a contract change: raise it in TEAM.md first.

## Validation

Every `target.json` that is committed or published must validate against
`docs/target.schema.json`.
