# Contracts (v0.25)

v0.25 (T89): false colour at the live orders is LRGB: detail (luminance) from the grey tile of the requested
band, colour from the all-band cube (`spherex-live-rgb` at order 5). So `spherex-live-p<n>-rgb` and
`spherex-live-rgb` keep the 102 band slices (the slice picks the detail band), and `e<n>c` works on a
one-detector field. One render per colour tile instead of six. URLs unchanged.

v0.24 (T91): `GET /api/targets/<id>/motion?name=<label>[&start=0]`: a catalogued star's proper motion (and,
with 3+ consistent epochs, its parallax / distance) measured from SPHEREx alone, next to the catalogue value.
New endpoint and cache (`data/motion/`) only. See "Measured motion".

v0.23: the discovery index (v0.13, T76: `GET /api/discoveries`, its file format and the hand-made sample) is
removed (Decision 2026-11-14, Mati: the tool visualizes, citizen scientists find things).

v0.22 (T58): limits for a public Live API (`python -m server --public`): 429 + Retry-After (per-IP request
rate or too many new jobs from one address), 503 `{"status": "busy"}` + Retry-After (server-wide job cap),
`refresh=1` and `POST /api/settings` only with the admin token. Off by default: nothing changes for the team's
servers. See "Public limits".

v0.21 (T89): sky layer `spherex-live-rgb` (the whole map in false colour: IRSA cube slices 8/25/42/59/76/93
to order 5, the live grey tiles at 6-7); `spherex-live` serves IRSA's blank cube slices 50/51 (dichroic channels)
from their neighbours 49/52 instead of 404. Additive.

v0.20 (T89): bands on the map. `GET /api/target` takes `&detector=<1-6>` (only that detector's images, id
`…-d<n>`); epoch layers `e<n>d<det>` (one detector) and `e<n>c` (false colour); sky layers
`spherex-live-p<n>-rgb` (false colour); at the live orders (6-7) a tile's slice is rounded down to its
detector's first slice (`(d-1)*17`), since the image only depends on the detector. Additive otherwise.

v0.19 (T55): `GET /api/pass-dates` gains `visits` per pass (its images grouped by gaps > 30 d). Additive only.

v0.18 (T64): data releases. Each frame may carry `collection` (the IRSA collection = SPHEREx release, e.g.
`spherex_qr3_deep`); target.json may carry `source_exposures` (what SPHEREx had at the centre at build time);
`GET /api/targets/<id>/updates` says whether newer images or a new release exist (see "Newer data"). Image
searches cover new releases automatically (`pipeline.releases`). Additive; `schema_version` stays `"0.2"`.

v0.17 (T86): the spectral-outliers answer gains chart data (`bands_um`, `envelope`, `colours`, `points`;
`version` 2), for the colour–colour diagram and band-shape chart. New fields only.

v0.16 (T55): tile settings get a third mode, `balanced` (default when a remote tile generator is configured):
each live tile goes to this machine or the VM, whichever is expected to finish it first; `GET /api/settings`
reports the measured throughput per side under `balance`. `local` / `remote` behave as before.

v0.15 (T85, T86): `GET /api/targets/<id>/spectral-outliers`: spectra of every catalogue source of a field and
the sources whose spectral shape is out of distribution for that field. New endpoint and cache only; nothing
existing changes. See "Spectral outliers".

v0.14 (T55, T82): survey passes on the sky map: `spherex-live-p<n>` layers documented, `x_survey_passes`
in the live properties, and `GET /api/pass-dates` (when each pass imaged a point). New fields / endpoint
only; nothing existing changes.

v0.13 (T76): the discovery index: `GET /api/discoveries` and its file format
(`docs/discoveries.schema.json`), written by the survey (T75) to `data/survey/discoveries.json`; until then the
API serves a hand-made sample (`fixtures/discoveries-sample.json`, `"synthetic": true`). See "Discoveries".
New endpoint and file only; target.json unchanged.

v0.12 (T52, T51): labels get more sources: `vsx` (variable stars), `catwise2020` (red moving WISE sources,
brown dwarf candidates), `horizons` (planets and moons, seen from SPHEREx); optional `note` (one line about
the object) and `mag_band` (band of `mag`, absent = G). `known_objects[].source` may be `mpcorb` (computed
from the MPC orbit catalogue), `skybot` or `jpl-sbident`. Additive; `schema_version` stays `"0.2"`.

v0.11 (T56) brings this file in line with the code: no pre-baked `web/targets/` and no `pipeline.publish`
(made obsolete by v0.3 live data); entry points and signatures as they are; the Live API routes the viewer
already uses are written down (`/objects`, `/sky`, `/settings`, `/health`); `labels_requested` /
`objects_requested` in target.json; label `source: "synthetic"` for made-up labels in fixtures; a second,
schema-0.2 fixture `fixtures/targets/demo-epochs/`. Nothing changes for code that follows the code.

v0.10 adds `GET /api/targets/<id>/photometry` (T49): aperture photometry at a position in every frame of a
built target, for spectra and light curves (see "Photometry"). New endpoint only; target.json unchanged.

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
pipeline/ (A)                detect/ (B), on request (T51)     web/ (C)
IRSA/AWS → cutouts →      →  adds known_objects + detections →  calls the Live API, then reads
aligned frames +             to the same target.json            target.json + frame images
target.json                  (GET /api/targets/<id>/objects)
```

The frontend never calls IRSA, AWS, JPL or the catalogues directly; it only talks to the Live API, which
serves target folders, photometry and sky-map tiles. Data is live (fetched when first requested) and
cached, not pre-baked. Catalogue labels (v0.8) and known objects (v0.11) are added after the build, when
the viewer asks for them, because SIMBAD/Gaia and JPL take from seconds to minutes.

## Folder layout

```
pipeline/                      A: Python package, data access + frame building
detect/                        B: Python package, mover detection + cross-match
web/                           C: static site, no build step (web/dev.py serves it locally; any static host)
server/                        T18: Live API (Python, FastAPI), builds and caches target folders
tilegen/                       T42/T47: live deep-zoom sky-map tiles (in-process, or the team VM in us-east4)
deploy/                        T47: scripts for the tile-generator VM
tests/                         T46: contract checks (fixtures vs. schema, presets), run by CI
data/                          gitignored: downloads, caches, work in progress
data/raw/                      cached downloads (FITS cutouts)
data/targets/<id>/             the Live API cache: one built target per requested field
data/mirror/                   T31: local copy of the SPHEREx image index
fixtures/targets/<id>/         tiny committed samples for tests and frontend development
docs/target.schema.json        JSON Schema for target.json
```

A **target folder** looks the same in `data/targets/` and `fixtures/targets/`:

```
<targets-root>/index.json      list of targets
<targets-root>/<id>/target.json
<targets-root>/<id>/frames/<frame_id>.png|webp
```

Committed samples (`fixtures/`) stay tiny: ≤ 5 MB per target, no `.fits`. Real fields are never committed.

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

Formal schema: `docs/target.schema.json`. Examples, both synthetic: `fixtures/targets/demo-synthetic/` (schema
0.1, the minimum) and `fixtures/targets/demo-epochs/` (schema 0.2 with every optional field: 3 epochs, pairs,
no-data pixels, labels with motion, known objects, known / unknown / artifact detections; regenerate with
`python fixtures/make_demo_epochs.py`).

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
| `labels_requested` | server | optional (v0.8): `true` once `GET …/labels` has run (labels may still be `[]`) |
| `objects_requested` | server | optional (v0.11): `true` once `GET …/objects` has run (known objects + detections) |
| `source_exposures` | A | optional (v0.18): `{count, latest_mjd, latest_utc, collections, checked_utc}`: the SPHEREx exposures covering the centre at build time (the frames are a selection of them) |

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
- `collection`: optional (v0.18): the IRSA collection the exposure belongs to = its SPHEREx release
  (`spherex_dr1`, `spherex_dr1_deep`, `spherex_qr3`, …; DR = data release, QR = quick release). Older builds
  don't have it; the release folder in `source_url` (`…/qr3/level2/…`) tells the same.

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
  or `gaia_dr3` (stars brighter than G = 16; `mag` is Gaia G). `synthetic` (v0.11) only in synthetic
  fixtures: a made-up object; the viewer marks it as not real.
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
- Pipeline for detections: T06 finds tracks → `detect.known_objects` (T07/T51: asteroids from a local copy
  of the MPC orbit catalogue (`detect.mpcorb`) when built, else candidates from IMCCE SkyBoT or JPL
  sb_ident with positions from JPL Horizons; always as seen from SPHEREx) fills `known_objects`
  → `detect.classify` (T08) sets `status`, `matched_object`, `score`, `motion`, `reason`.
  `detect.run.detect_target` (T51) runs these steps; T06 plugs in there.

## Entry points

```
python web/dev.py [--fixture|--live] [--lan|--host ADDR]  # Live API + viewer in one go (T21)
python -m server [--port 8000] [--fixture] [--cache data/targets] [--tiles-remote URL] [--use-remote]  # Live API (T18)
python -m pipeline.query --ra <deg> --dec <deg>          # T01: SPHEREx images covering a position
python -m pipeline.build --id <id> --ra <deg> --dec <deg> --size <arcmin> [--out data/targets] [--labels] [--refresh]
python -m pipeline.labels <target_dir>                   # T19: SIMBAD + Gaia labels into target.json
python -m pipeline.photometry <target_dir> --ra <deg> --dec <deg>   # T49: fluxes in every frame
python -m pipeline.stack <target_dir> [--object <id|name>]          # T23: shift-and-stack image
python -m pipeline.mirror harvest|build|find             # T31: local SPHEREx image index
python -m detect.run <target_dir> [--vmag 20]            # T51: known objects + classify (+ T06 later)
python -m detect.known_objects <target_dir> [--vmag 20]  # T07: known asteroids/comets
python -m detect.classify <target_dir>                   # T08: status/score/reason per detection
python web/warm.py [--only <name>] [--refresh]           # T05: pre-build the official test fields
python fixtures/make_demo_epochs.py                      # T56: regenerate the schema-0.2 fixture
```

```python
# pipeline/build.py (A)
def build_target(target_id: str, ra_deg: float, dec_deg: float, size_arcmin: float,
                 out_root: Path = Path("data/targets"), progress=None, per_group: int = PER_GROUP,
                 name: str | None = None, refresh: bool = False, final_root: Path | None = None,
                 labels: bool = False) -> Path:
    """Query, download, align, render. Returns the target folder with a valid target.json.
    progress(step, done=None, total=None, message="") feeds the Live API's progress bar."""

# detect/run.py (B)
def detect_target(target: dict, jpl=None, vmag_lim: float = DEFAULT_VMAG) -> dict:
    """Fill known_objects and detections in place; touches only those two fields and appends to
    provenance. A failed JPL lookup never raises: known_objects stays [] and the error goes into provenance."""

def detect(target_dir: str | Path, jpl=None, vmag_lim: float = DEFAULT_VMAG) -> Path:
    """detect_target on <target_dir>/target.json, written back. Returns target_dir."""
```

`detect` works on the rendered frames and the JSON. If B needs the aligned FITS data as well,
that is a contract change: raise it in TEAM.md first.

## Live API (v0.3)

Base URL is configurable in the frontend (`?api=` URL parameter or a constant); default for local
development `http://localhost:8000`. All responses are JSON unless they are frame images. CORS is
open (`Access-Control-Allow-Origin: *`), so the static site can live on a different host.

### Request a field

```
GET /api/target?ra=<ra>&dec=<dec>&size=<arcmin>[&refresh=1][&detector=<1-6>]
```

- `ra`, `dec`: decimal degrees (`133.795`, `-7.245`) or sexagesimal (`08h55m10.831s`,
  `-7d14m42.53s`, `08:55:10.831`, `-07:14:42.53`). ICRS.
- `size`: side of the square field in arcmin, default `15`, allowed `5`–`210` (210′ ≈ one SPHEREx
  detector image, 2040 px × 6.15″; was `5`–`60` until 2026-11-14, see TEAM.md Decisions). Larger = slower.
- `refresh=1`: ignore the cache and rebuild (to pick up a new data release).
- `detector` (v0.20, T89): only images from this SPHEREx detector (1: 0.75–1.09 µm … 6: 4.42–5.00 µm), e.g. the
  band shown on the map: ~1/6 of the cutouts (an 86′ field: 31 s instead of ~100 s). The target id gets `-d<n>`
  and is cached apart from the all-detector field.

Responses:

| HTTP | Body | Meaning |
|---|---|---|
| 200 | `{"status": "ready", "id": "...", "target_url": "/api/targets/<id>/target.json"}` | built, fetch `target_url` |
| 202 | `{"status": "building", "id": "...", "progress": {...}, "poll_url": "/api/jobs/<id>"}` | build running, poll every 2 s |
| 400 | `{"status": "error", "message": "..."}` | bad coordinates or size |
| 404 | `{"status": "no_data", "id": "...", "message": "..."}` | SPHEREx has no images here |
| 500 | `{"status": "error", "id": "...", "message": "..."}` | build failed |

`progress`: `{"step": "query|download|align|render", "done": 12, "total": 39, "message": "..."}`
(`done`/`total` may be `null`). Known objects and labels are not part of the build (see below).

### Poll a build

```
GET /api/jobs/<id>          → same body as /api/target (ready / building / no_data / error)
```

### Serve a built target

```
GET /api/targets/<id>/target.json
GET /api/targets/<id>/frames/<frame_id>.png|webp
GET /api/targets            → index.json of everything in the cache (same format as above)
GET /api/health             → {"ok": true, "mode": "live" | "fixture"}
```

Image paths inside `target.json` stay relative to the target folder, so the frontend resolves
them against `target_url`.

### Photometry (v0.10, T49)

```
GET /api/targets/<id>/photometry?ra=<deg>&dec=<deg>     a sky position
GET /api/targets/<id>/photometry?x=<px>&y=<px>          a pixel on the target grid (conventions above)
GET /api/targets/<id>/photometry                        the field centre
```

Measured on the cached SPHEREx cutouts the frames were built from (`pipeline.photometry`): IMAGE minus a
local annulus background (removes ZODI), aperture r = 3 native px, flagged pixels left out, error from
VARIANCE or the annulus scatter (S3 cutouts have no VARIANCE). Answer (200):

```json
{ "status": "ready", "id": "...", "ra_deg": 76.9566, "dec_deg": 30.4013, "unit": "uJy",
  "aperture_px": 3.0, "annulus_px": [5.0, 8.0], "note": "...", "missing": ["f031"],
  "frames": [ { "frame_id": "f000", "epoch": 1, "mjd": 60902.9, "time_utc": "...", "detector": 1,
                "wavelength_um": 1.068, "bandwidth_um": 0.022, "flux_ujy": 153437.8, "err_ujy": 599.8,
                "masked_fraction": 0.0, "masked": false } ] }
```

- `wavelength_um` / `bandwidth_um` are **at the measured position** (not the field centre's frame value).
- `masked`: more than 20 % of the aperture flagged (saturation, bad pixels); `flux_ujy` may be `null`.
- `missing`: frames without a cached cutout or where the position is off the image.
- Synthetic targets: 200 with `{"status": "no_data", "message": ...}`. Unknown target: 404. Bad ra/dec: 400.

### Spectral outliers (v0.15, T85, T86)

```
GET /api/targets/<id>/spectral-outliers            cached result, else {"status": "not_started"}
GET /api/targets/<id>/spectral-outliers?start=1    start measuring; 202 {"status": "building", "done", "total"}
                                                   while it runs (poll without start), then 200 as below
```

T85 (`pipeline.fieldspectra`) reads every SPHEREx exposure of the field once (a field-sized cutout each) and
measures every catalogue label (no solar-system objects, no X-ray / radio positions) with the T49 photometry,
each source moved along its own track. Cached as `data/field_spectra/<id>.json` (sources × exposures arrays);
each source's spectrum is also written to the T66 per-position cache, so `/api/photometry` at a source
answers at once. T86 (`pipeline.spectral_outliers`) ranks them. Answer (200):

```json
{ "status": "ready", "id": "...", "version": 1, "summary": "9 of 137 sources stand out ...",
  "n_sources": 172, "n_judged": 137, "n_reference": 80, "components": 2, "epochs": [1, 2, 3],
  "method": "...", "scatter_pct": [3.0, ...],
  "field": { "target_id": "...", "n_sources": 172, "n_exposures": 237, "missing": 0, "seconds": 21.2 },
  "scores": { "<label id>": 23.3 },
  "not_judged": [ { "id": "l000", "name": "RW Aur", "why": "saturated / flagged in most exposures", "bands": 3 } ],
  "items": [ { "id": "l111", "name": "Gaia DR3 ...", "source": "gaia_dr3", "otype": "*", "mag": 15.18,
               "ra_deg": 77.00062, "dec_deg": 30.33474, "score": 23.3, "chi2": 10.1,
               "reason": "Redder than ordinary sources here: ...", "caveats": ["blended: ..."],
               "deviations": [ { "um_min": 1.249, "um_max": 1.363, "sign": -1, "pct": -35.1, "z": 8.2,
                                 "n_bands": 1, "epochs_agree": 2, "epochs_seen": 3, "meaning": "..." } ],
               "bands_um": [0.77, ...], "residual_pct": [12.0, null, ...], "z": [1.2, null, ...] } ] }
```

- Shape only: each (source, epoch) is scaled to its own level; "ordinary" is learned from the field's own
  unblended, non-variable, non-galaxy sources (mean shape + `components` principal shapes).
- `items` are sorted by `score` (summed significance of consistent deviations; halved for blends, ×0.3 for
  jagged residuals). `scores` has every judged source, for colouring.
- `items[].ra_deg/dec_deg` open the source's spectrum with `GET /api/photometry?ra=&dec=`.
- Chart data (v0.17, `version` 2): `bands_um` (22 band centres); `envelope` {`p16`, `p50`, `p84`}: the ordinary
  sources' band shape (log10, own level taken out); `colours` {short, mid, long: [µm, µm]};
  `points`: every judged source `{id, name, otype, ra_deg, dec_deg, x, y, outlier, reference, score, shape,
  model}` with `x` = short − mid and `y` = mid − long colour in magnitudes (+ = redder), `shape` its band
  shape and `model` what an ordinary source of its kind would show (log10, null = no band).
- Synthetic targets: 200 `{"status": "no_data"}`. Unknown target: 404.

### Public limits (v0.22, T58)

Only when the server runs with `--public` (or `SPHEREX_PUBLIC=1`); otherwise none of this applies.

- Every `/api/...` call except `/api/health` counts against a per-IP rate (`/api/sky/...` and `/api/hips/...`
  tiles have their own, larger allowance). Beyond it: **429** `{"status": "error", "message": "too many …"}` with
  `Retry-After` (seconds).
- Starting expensive work costs one job from the address's job allowance (default 30 per hour, 10 at once):
  a field build (`/api/target` for a field not cached and not being built), an all-exposure spectrum
  (`photometry?all=1`, `/api/photometry`) not yet cached, `spectral-outliers?start=1` for a field not measured.
  Polling a running job or reading a cached result is free. Beyond: **429** as above.
- At most `--max-jobs` (default 4) such jobs run on the whole server. Beyond: **503**
  `{"status": "busy", "message": …}` with `Retry-After`.
- `refresh=1` is ignored and `POST /api/settings` answers **403** unless the request carries the admin token
  (`SPHEREX_ADMIN_TOKEN`) as `?token=` or header `X-Admin-Token`.
- The field / cutout / spectra caches are kept under `--cache-gb` (default 20) by evicting the least recently
  used; a field that is being built is never evicted.

### Measured motion (v0.24, T91)

```
GET /api/targets/<id>/motion?name=<label name, alias or id>          cached, else starts measuring (~15 s)
GET /api/targets/<id>/motion?name=…&start=0                          cached, else {"status": "not_started"}
GET /api/targets/<id>/motion?ra=<deg>&dec=<deg>[&start=0]            the catalogued star moving ≥ 0.3″/yr within 8″
                                                                     of that spot; 404 {"status": "none"} if none
```

202 `{"status": "building", "done", "total"}` while measuring (poll with `start=0`), then 200:

```json
{ "target_id": "...", "id": "l000", "name": "* eps Ind B", "status": "ready", "version": 1,
  "pm_east_arcsec_yr": 3.81, "pm_north_arcsec_yr": -2.58, "err_east": 0.2, "err_north": 0.2,
  "pm_total_arcsec_yr": 4.6, "pm_total_err": 0.26, "pa_deg": 124.0,
  "catalogue": { "pm_total_arcsec_yr": 4.68, "pa_deg": 122.0, "source": "simbad" },
  "difference_arcsec_yr": 0.1, "difference_sigma": 0.4, "verdict": "agrees with the catalogue", "summary": "...",
  "parallax": { "parallax_arcsec": 0.286, "parallax_err": 0.022, "chi2_dof": 1.94, "reliable": true,
                "distance_pc": 3.49, "note": "measured" },
  "epochs": [ { "epoch": 1, "mjd": 60805.7, "east": -2.01, "north": 1.06, "err_east": 0.03, "err_north": 0.04, "n": 91 } ],
  "span_years": 1.39, "n_exposures": 357, "n_measured": 351, "n_references": 22, "method": "..." }
```

- `status` `not_found`: the star itself could not be found in single exposures (the fit locked onto a neighbour
  ≥ 3″ away in every epoch, e.g. WISE 0855); `not_enough`: measured in fewer than two epochs. Both with `message`.
- `parallax` is fitted with 3+ epochs; `distance_pc` only when `reliable` (χ²/dof ≤ 3 and > 3σ), else `note` says why.
- `epochs[].east/north`: arcsec from the label's reference position, pointing-corrected with Gaia reference stars.
- Unknown label: 404 `{"status": "error"}`. Synthetic target: 200 `{"status": "no_data"}`. Public servers (T58):
  a new measurement costs one job.

### Target id and cache

- The id is derived from the request, so equal requests hit the same cache entry:
  `c<RA in 1e-4 deg, 7 digits>-<p|m><|Dec| in 1e-4 deg, 6 digits>-s<size>`,
  e.g. RA 133.7951, Dec -7.2452, 15' → `c1337951-m072452-s15`. Coordinates are rounded to
  1e-4 deg (0.36″) before building, and `center` in `target.json` is the rounded position.
- The cache is the target folder `data/targets/<id>/` (same layout as everywhere else), plus raw
  downloads in `data/raw/`. A cached target is served as long as it exists; `refresh=1` rebuilds.
- The demo fields named in `docs/CHALLENGE.md` are warmed by requesting them before the demo
  (`web/warm.py`, T05), not committed. That is still live data, only cached.
- `--fixture` (tests, offline development) answers every request with a copy of
  `fixtures/targets/demo-synthetic` in its own cache, which is `"synthetic": true` and must be shown as such.

### Labels on request (v0.8, T37)

Builds no longer ask SIMBAD/Gaia (that took up to 30 s in deep fields). The viewer's Labels switch
asks for them:

```
GET /api/targets/<id>/labels   → 202 {"status": "building", "message"} while running,
                                 200 {"status": "ready", "n"} once target.json has them
```

When done, `target.json` has `labels` filled (same format as before, T19) and `"labels_requested": true`.

### Known objects on request (v0.11, T51)

Builds don't wait for known objects either. The server starts the lookup after every live build (local MPC
orbit catalogue, ~2-3 s; SkyBoT or JPL as fallbacks, slower), and the viewer polls it once the field is
shown, unless `objects_requested` is set or the target is synthetic:

```
GET /api/targets/<id>/objects  → 202 {"status": "building", "n": null, "message"} while running (poll),
                                 200 {"status": "ready", "n"} once target.json has them,
                                 404 not built, 500 {"status": "error", "message"}
```

When done, `target.json` has `known_objects` and `detections` filled by `detect.run.detect_target` and
`"objects_requested": true`. Then reload `target_url`.

### Per-epoch HiPS (v0.6, T32)

For Aladin Lite: each epoch of a built target as a HiPS layer (frames of that epoch averaged,
grey + alpha, alpha 0 = no data), rendered on demand. Only tiles that touch the field exist (404
elsewhere).

```
GET /api/hips/<id>                         → {"id", "synthetic", "layers": [{"epoch", "id": "e<n>", "label", "url", "n_frames", "detectors"}]}
GET /api/hips/<id>/e<n>/properties         → HiPS properties (order 7, 512 px PNG tiles, equatorial)
GET /api/hips/<id>/e<n>/Norder<k>/Dir<d>/Npix<p>.png
```

v0.20 (T89): `e<n>d<det>` = only that detector's frames of the epoch; `e<n>c` = false colour, RGBA tiles;
`detectors` lists the epoch's. v0.25: `e<n>c` = the epoch's image (detail) times the colour of the all-band cube
there (LRGB, R = D5+D6, G = D3+D4, B = D1+D2), so it works on a one-detector field; in fixture mode (no cube) it
falls back to the field's own detectors (R = mean of 5+6, G = 3+4, B = 1+2).

`url` is relative to the API base. Tile pixel (row from top, col) ↔ HEALPix NESTED index at
nside 2^(k+9): `p * 512² + interleave(row → even bits, col → odd bits)` (checked against IRSA's
2MASS HiPS).

### Sky map tiles (T41, T42) and tile settings (T47)

The viewer's sky map (`web/sky.js`) reads all-sky HiPS maps through the Live API, which caches them on disk:

```
GET /api/sky/<survey>/properties
GET /api/sky/<survey>/Norder<k>/Dir<d>/Npix<p>[_<slice>].png|jpg
GET /api/sky/<survey>/Norder3/Allsky[_<slice>].png|jpg
```

`survey`: `spherex-cube` (IRSA's SPHEREx all-sky cube, one slice per band), `spherex-d1` … `spherex-d6`
(CDS, one per detector), `spherex-live` (the cube up to order 5, then order 6-7 tiles we render from the
level-2 images in the AWS bucket, `tilegen/`), `spherex-live-p<n>` (T82: the same live tiles from survey
pass n's images only, orders 6-7; pass n = images from 2025-05-01 + (n-1) x 182.625 d), `spherex-live-p<n>-rgb`
(v0.20: the same in false colour, RGBA; v0.25: LRGB = the grey tile of the requested band x the colour of
`spherex-live-rgb` at order 5, R = D5+D6, G = D3+D4, B = D1+D2), `2mass`, `allwise`.
At the live orders a requested slice is rounded down to its detector's first, `(d-1)*17` (v0.20).
`spherex-live-rgb` (v0.21): the whole map in false colour (to order 5 one cube slice per detector; v0.25: at
orders 6-7 LRGB like the passes, and the band slices are kept for that); IRSA's blank cube slices 50/51 are
served from slices 49/52 (v0.21).
404 = upstream has no such tile; 503 + `Retry-After` = the local image index is still being built;
502 = upstream or tile generator down. `spherex-live/properties` lists the passes the image index has
images from: `x_survey_passes = 1 2 3` (v0.14).

```
GET /api/pass-dates?ra=<deg>&dec=<deg>
→ {"ra", "dec", "passes": [{"pass": 1, "start": "2025-08-18", "end": "2025-09-30", "n_images": 65,
                            "visits": [{"start", "end", "n_images"}, ...]}, ...]}
```

v0.14 (T55): when SPHEREx imaged that point in each pass (UTC dates of the level-2 images whose centre is
within 1.2 deg, all detectors); passes without images there are left out. `visits` (v0.19): the pass's images
grouped by gaps > 30 d; near a pass boundary one pass can hold two visits half a year apart. 503 + `Retry-After` while the
local image index is being built.

```
GET  /api/settings                     → {"tiles": "balanced" | "local" | "remote", "remote_url", "remote_available",
                                          "balance": {"local": {avg_s, tiles_per_s, inflight, done, failed}, "remote": {…}}}
POST /api/settings {"tiles": "balanced"} → same body; which generator renders the live tiles (400 if unknown)
```

`balanced` (v0.16, default with a remote): a tile costs (tiles in flight on that side + 1) / that side's measured
throughput (tiles in flight / seconds per tile, moving average); the cheaper side renders it, a side unused for
20 s gets the next tile while idle (so both stay measured), a failing side is backed off. Local renders of
combined tiles use the VM's images per tile, so tiles look the same from either side. `balance` is omitted
without a remote.

`remote` is the team's tile generator on a VM next to the bucket (`deploy/`, T47): seconds instead of
minutes from Europe. Only the tiles go there; builds, caches and the API stay local.

### Newer data (v0.18, T64)

```
GET /api/targets/<id>/updates
```

Compares `source_exposures` (build time) with the exposure list now (local image index, else IRSA TAP cached
for a day) and the release folders in the public bucket (`pipeline.releases`, one listing, cached for a day).
Answer (200):

```json
{ "status": "ready", "id": "...", "basis": "build", "newer_images": 12,
  "newer_from_utc": "...", "newer_to_utc": "...", "new_passes": 1, "new_collections": ["spherex_qr4"],
  "releases_built": ["DR1", "QR3"], "releases_now": ["DR1", "QR3", "QR4"],
  "releases_published": ["DR1", "QR2", "QR3", "QR4"], "new_releases": ["QR4"],
  "release_note": "SPHEREx has published QR4 since this tool was written; it is searched from now on.",
  "checked": { "service": "...", "query": "...", "retrieved_utc": "..." },
  "checked_label": "the local SPHEREx image index (harvested 2026-11-14)",
  "message": "12 newer SPHEREx images here (…; 1 new survey pass; new release QR4). Rebuild to include them.",
  "built": { ... source_exposures ... }, "now": { ... same shape, now ... } }
```

- Newer images = exposures after `source_exposures.latest_mjd`. Fields built before v0.18 (`basis: "frames"`):
  only exposures more than 30 days after the last frame (a new survey pass) count, because the frames are a
  selection and later exposures of the last pass may just not have been picked.
- `new_releases`: release folders in the bucket this code didn't know (2026-11-14: `dr1`, `qr2`, `qr3`); they are
  searched from then on as `spherex_<rel>` and `spherex_<rel>_deep`. The local image index only has them after
  a new harvest (`pipeline.mirror`); `release_note` says so.
- Rebuild = `GET /api/target?…&refresh=1`. Synthetic targets: `{"status": "no_data"}`. Unknown target: 404.
  Image search failed (IRSA down): 502 with a message.

### Frontend URL

The viewer reads `?ra=&dec=&size=` from its own URL and requests that field on load, so links and
embeds work (official "Potential Considerations"). Other parameters (`?api=`, `?data=`, `?explore=0`, …):
`web/README.md`.

## Validation

Every `target.json` that is committed or built must validate against `docs/target.schema.json`. CI
(T46) checks the committed fixtures on every push (`tests/test_contract.py`). Built targets are not
validated at build time yet (idea: validate in `server/builder.py` before a build counts as ready).
