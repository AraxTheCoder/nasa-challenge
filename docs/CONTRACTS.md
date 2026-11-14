# Contracts (v0.9)

v0.9 adds an optional plain-words `reason` to each detection (why it is known / unknown / artifact),
written by `detect.classify` (T08). Additive; `schema_version` stays `"0.2"`. See TEAM.md Decisions.

v0.8 makes catalogue labels opt-in: builds write `labels: []`; `GET /api/targets/<id>/labels` adds them
(see "Labels on request"). See TEAM.md Decisions.


v0.7 adds `importance` and `aliases` to each label (see "Label"): which names the viewer shows
first, and duplicates merged into one label. Additive. See TEAM.md Decisions, 2026-11-14.

v0.6 adds per-epoch HiPS tiles to the Live API (see "Per-epoch HiPS"), additive. See TEAM.md Decisions.


v0.5 adds an optional `motion` summary to each label (see "Label"), from `pipeline.motion`.
Additive; `schema_version` stays `"0.2"`. See TEAM.md Decisions, 2026-11-14.

v0.4 adds optional `labels` to `target.json`: catalogue names and positions (SIMBAD, Gaia DR3),
moved to each frame's time. Additive: `schema_version` stays `"0.2"`, old readers ignore the field.
See TEAM.md Decisions, 2026-11-14.

v0.3 makes the tool **live**: any RA/Dec a user enters is built on request from IRSA and cached
(see "Live API" below). The target folder format is unchanged. See TEAM.md Decisions, 2026-11-14.


v0.2 adds `pairs`, `bandwidth_um` and transparent no-data pixels. All three are optional and
additive: a v0.1 reader keeps working. See TEAM.md Decisions, 2026-11-14.

Interfaces between the three tracks. This file only changes together with a dated line under
TEAM.md "Decisions" that says why.

## Data flow

```
                      server/ (T18): GET /api/target?ra=&dec=&size=
                        │ cache hit → serve data/targets/<id>/
                        │ cache miss → build in background, report progress
                        ▼
pipeline/ (A)                detect/ (B)                       web/ (C)
IRSA → cutouts → aligned  →  adds known_objects + detections →  calls the Live API, then reads
frames + target.json         to the same target.json            target.json + frame images
```

The frontend never calls IRSA or JPL directly; it only talks to the Live API, which serves target
folders. Data is live (fetched from IRSA when first requested) and cached, not pre-baked.

## Folder layout

```
pipeline/                      A: Python package, data access + frame building
detect/                        B: Python package, mover detection + cross-match
web/                           C: static site, deployed to GitHub Pages
server/                        T18: Live API (Python), builds and caches target folders
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
| `schema_version` | A | `"0.1"` or `"0.2"` |
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
| `pairs` | A | optional (v0.2): frames from different epochs at matching wavelength, see below |
| `labels` | A | optional (v0.4): catalogue objects in the field with a position per frame, see below |

### Frame

```json
{ "id": "f000", "time_utc": "2026-05-01T00:00:00Z", "mjd": 61161.0, "epoch": 1,
  "detector": 3, "wavelength_um": 1.52, "bandwidth_um": 0.038, "image": "frames/f000.png",
  "obs_id": "…", "source_url": "…" }
```

- `epoch`: which all-sky survey pass the frame belongs to (1, 2, …). Blinking between epochs is
  the main view.
- `wavelength_um`: wavelength **at the target centre**. SPHEREx uses linear variable filters, so
  wavelength changes across a single exposure; one number per cutout is an approximation.
  Consecutive exposures see the same spot about 0.03 µm apart, so no two frames share a wavelength.
- `bandwidth_um`: optional (v0.2): width of the spectral channel at the target centre (from the
  `WCS-WAVE` table). Used to decide which frames count as "the same wavelength".
- `image`: path relative to the target folder. 8-bit PNG or WebP, already stretched for display.
  From v0.2, pixels with no data (outside the rotated original frame, or masked) are fully
  transparent (alpha 0), so the viewer can show them as "no data" instead of dark sky.
- `obs_id`, `source_url`: where the frame came from. `null` for synthetic frames.

### Pair (v0.2, optional)

```json
{ "a": "f005", "b": "f035", "detector": 2, "dwave_um": 0.0022, "dt_days": 174.1 }
```

Stars change brightness with wavelength, so only frames at nearly the same wavelength can be
compared fairly. A pair is two frames from **different epochs**, same detector, with
`|wavelength a - wavelength b| <= 0.5 * bandwidth` (smaller of the two). `a` is the earlier frame. Each frame is in at
most one pair per other epoch (the closest match). Detection (B) and the "matched pairs" blink
view (C) should prefer pairs over arbitrary frame combinations.

### Label (v0.4, optional)

```json
{ "id": "l000", "name": "Barnard's star", "kind": "variable star", "otype": "BY*",
  "source": "simbad", "named": true, "mag": null, "pm_mas_yr": 10393.4,
  "positions": [ { "frame_id": "f000", "ra_deg": 269.44629, "dec_deg": 4.76736, "x": 47.47, "y": 48.06 } ] }
```

- Written by `pipeline.labels.add_labels(target)` (A) after the frames exist. Synthetic targets get
  `labels: []`: real names on simulated frames would mislead.
- `positions`: one per frame, catalogue position moved to that frame's time with the proper
  motion (parallax ignored, < 0.1 px). For a fast star the label follows it across epochs.
- `source`: `simbad` (names, object types; tries the CDS host, then the Harvard and IDIA mirrors)
  or `gaia_dr3` (stars brighter than G = 16; `mag` is Gaia G).
- `named`: `true` for a human-readable name (Barnard's star, V3214 Oph), `false` for catalogue
  numbers (Gaia DR3 …, ZTF J…). Suggested UI default: show named labels, the rest on demand.
- `kind`: plain-words object type for the UI; `otype` is the raw SIMBAD type.
- A label marks a **catalogued** object, not a detection. Detections stay in `detections` (B).
- The same object can appear twice (SIMBAD and Gaia). The UI may hide a Gaia label within 2 px
  of a named SIMBAD label.
- `importance` (v0.7, optional): 0 = the field's object (the SIMBAD object nearest the requested
  centre, within 15″), 1 = notable motion (`motion.class` not `still`), 2 = a real name or a notable
  type (brown dwarf, variable, quasar, …), 3 = catalogue-number SIMBAD object, 4 = Gaia-only star.
  The viewer always names the most important few (≤ 8) and shows the rest on hover (T34).
- `aliases` (v0.7, optional): other labels for the same object closer than 3″ (~0.5 px), merged
  into this one: SIMBAD components (RW Aur A, RW Aur B) and the object's Gaia twin. The kept label
  is the SIMBAD one with the most readable name and takes the Gaia `mag` if it had none.
- `motion` (v0.5, optional, may be `null` with < 2 positions): summary over the whole series,
  written by `pipeline.motion.summarize(positions, frames, pixel_scale_arcsec)`:
  `{shift_arcsec, shift_px, reach_arcsec, days, rate_arcsec_per_yr, max_rate_within_epoch_arcsec_per_hr, pa_deg,
  direction, class, note}`. `pa_deg` is east of north, `direction` its compass point. `class` is one
  of `still`, `proper motion`, `fast mover`, `distant body?`; `note` says why in plain words. The
  `shift_*` is first → last position; `reach_arcsec` is the farthest it ever gets from the first
  one (a looping body can end near its start). The
  same function works for `known_objects[].positions` and `detections[].track` (B may use it).

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
- `reason` (v0.9, optional): one plain-words sentence why the detection got its status, e.g.
  "follows (4) Vesta (JPL) within 0.4 px on 3 frame(s)" or "seen in one frame only". Shown in the UI.
- Pipeline for detections: T06 finds tracks → `detect.known_objects` (T07, JPL) fills `known_objects`
  → `detect.classify` (T08) sets `status`, `matched_object`, `score`, `motion`, `reason`.

## Entry points

```
python -m server [--port 8000] [--fixture]            # Live API (T18)
python -m pipeline.build --id <id> --ra <deg> --dec <deg> --size <arcmin> [--out data/targets]
python -m detect.run <target_dir>
python -m detect.known_objects <target_dir> [--vmag 20]  # T07: known asteroids/comets from JPL
python -m detect.classify <target_dir>                   # T08: status/score/reason per detection
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

## Live API (v0.3)

Base URL is configurable in the frontend (`?api=` URL parameter or a constant); default for local
development `http://localhost:8000`. All responses are JSON unless they are frame images. CORS is
open (`Access-Control-Allow-Origin: *`), so the static site can live on a different host.

### Request a field

```
GET /api/target?ra=<ra>&dec=<dec>&size=<arcmin>[&refresh=1]
```

- `ra`, `dec`: decimal degrees (`133.795`, `-7.245`) or sexagesimal (`08h55m10.831s`,
  `-7d14m42.53s`, `08:55:10.831`, `-07:14:42.53`). ICRS.
- `size`: side of the square field in arcmin, default `15`, allowed `5`–`60`. Larger = slower.
- `refresh=1`: ignore the cache and rebuild (to pick up a new data release).

Responses:

| HTTP | Body | Meaning |
|---|---|---|
| 200 | `{"status": "ready", "id": "...", "target_url": "/api/targets/<id>/target.json"}` | built, fetch `target_url` |
| 202 | `{"status": "building", "id": "...", "progress": {...}, "poll_url": "/api/jobs/<id>"}` | build running, poll every 2 s |
| 400 | `{"status": "error", "message": "..."}` | bad coordinates or size |
| 404 | `{"status": "no_data", "id": "...", "message": "..."}` | SPHEREx has no images here |
| 500 | `{"status": "error", "id": "...", "message": "..."}` | build failed |

`progress`: `{"step": "query|download|align|render|detect", "done": 12, "total": 39, "message": "..."}`
(`done`/`total` may be `null`).

### Poll a build

```
GET /api/jobs/<id>          → same body as /api/target (ready / building / no_data / error)
```

### Serve a built target

```
GET /api/targets/<id>/target.json
GET /api/targets/<id>/frames/<frame_id>.png|webp
GET /api/targets            → index.json of everything in the cache (same format as above)
```

Image paths inside `target.json` stay relative to the target folder, so the frontend resolves
them against `target_url`.

### Target id and cache

- The id is derived from the request, so equal requests hit the same cache entry:
  `c<RA in 1e-4 deg, 7 digits>-<p|m><|Dec| in 1e-4 deg, 6 digits>-s<size>`,
  e.g. RA 133.7951, Dec -7.2452, 15' → `c1337951-m072452-s15`. Coordinates are rounded to
  1e-4 deg (0.36″) before building, and `center` in `target.json` is the rounded position.
- The cache is the target folder `data/targets/<id>/` (same layout as everywhere else), plus raw
  downloads in `data/raw/`. A cached target is served as long as it exists; `refresh=1` rebuilds.
- The demo fields named in `docs/CHALLENGE.md` are warmed by requesting them before the demo,
  not committed. That is still live data, only cached.
- Until `pipeline.build` exists, the server can run with `--fixture` and answers every request
  with `fixtures/targets/demo-synthetic`, which is `"synthetic": true` and must be shown as such.

### Labels on request (v0.8, T37)

Builds no longer ask SIMBAD/Gaia (that took up to 30 s in deep fields). The viewer's Labels switch
asks for them:

```
GET /api/targets/<id>/labels   → 202 {"status": "building", "message"} while running,
                                 200 {"status": "ready", "n"} once target.json has them
```

When done, `target.json` has `labels` filled (same format as before, T19) and `"labels_requested": true`.

### Per-epoch HiPS (v0.6, T32)

For Aladin Lite: each epoch of a built target as a HiPS layer (frames of that epoch averaged,
grey + alpha, alpha 0 = no data), rendered on demand. Only tiles that touch the field exist (404
elsewhere).

```
GET /api/hips/<id>                         → {"id", "synthetic", "layers": [{"epoch", "id": "e<n>", "label", "url", "n_frames"}]}
GET /api/hips/<id>/e<n>/properties         → HiPS properties (order 7, 512 px PNG tiles, equatorial)
GET /api/hips/<id>/e<n>/Norder<k>/Dir<d>/Npix<p>.png
```

`url` is relative to the API base. Tile pixel (row from top, col) ↔ HEALPix NESTED index at
nside 2^(k+9): `p * 512² + interleave(row → even bits, col → odd bits)` (checked against IRSA's
2MASS HiPS).

### Frontend URL

The viewer reads `?ra=&dec=&size=` from its own URL and requests that field on load, so links and
embeds work (official "Potential Considerations").

## Validation

Every `target.json` that is committed or published must validate against
`docs/target.schema.json`.
