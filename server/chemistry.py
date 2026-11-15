"""T93: chemistry maps for a built field (CONTRACTS "Chemistry maps").

    GET /api/chemistry/features                                 the features (id, name, µm, kind, what), T107 presets
    GET /api/targets/<id>/chemistry?feature=<f>&z=<z>           T109: the map at a redshift (key <f>_z<z·10⁴>)
    GET /api/targets/<id>/redshift                              T109: galaxies with a measured redshift in the field
    GET /api/targets/<id>/chemistry/candidates?maps=<k>[-<k>...][&cats=simbad,gaia,...&preset=<id>]
                                                                T128: spots where the picture's features show
    GET /api/targets/<id>/chemistry?feature=<f>                 cached result, else {"status": "not_started"}
    GET /api/targets/<id>/chemistry?feature=<f>&start=1         start; 202 {"status": "building", done, total},
                                                                then 200 {"status": "ready", ...stats, "layer"}
    GET /api/targets/<id>/chemistry/<f>.png                     the map (grey + alpha) on the field grid
    GET /api/targets/<id>/chemistry/<a>-<b>[-<c>...].png      T96/T108: 2 or more maps as one colour picture (RGBA)
    Map layer: /api/hips/<id>/x-<f>/...                         (server/hips.py), like the A − B difference;
               /api/hips/<id>/x-<a>-<b>[-<c>]/...               T96: the colour picture (features in wavelength order)

`pipeline.chemistry` makes the map from the field's SPHEREx exposures (a few seconds with cached cutouts).
"""
from __future__ import annotations

import re
import threading
import traceback

import numpy as np
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

router = APIRouter()
_ID = re.compile(r"^[a-z0-9-]+$")
_jobs: dict[tuple[str, str], dict] = {}
_lock = threading.Lock()


def _features():
    from pipeline.chemistry import FEATURES
    return FEATURES


@router.get("/api/chemistry/features")
def features():
    from pipeline.catcheck import CATALOGUES, DEFAULT
    from pipeline.chemistry import COMBINE_COLOURS, COMBINE_MAX, PRESETS, SHOWS
    hexes = lambda cs: ["#" + "".join(f"{round(255 * v):02x}" for v in c) for c in cs]
    return {"features": [{"id": k, "name": n, "um": um, "half_width_um": hw, "kind": kind, "what": what,
                          "shows": SHOWS[k]}                                  # T96: its direction in a combination
                         for k, (n, um, hw, kind, what) in _features().items()],
            "combine": {"max": COMBINE_MAX, "colours": {str(k): hexes(v) for k, v in COMBINE_COLOURS.items()}},
            "presets": PRESETS,                                                 # T107
            "catalogues": [{"id": k, "name": n, "what": w, "default": k in DEFAULT}   # T128: for the candidates
                           for k, (n, w) in CATALOGUES.items()]}


def _run(target_dir, tid: str, feature: str, job: dict, z: float = 0.0) -> None:
    from pipeline.chemistry import compute
    try:
        job["stats"] = compute(target_dir, feature, progress=lambda d, t: job.update(done=d, total=t), z=z)
        job["status"] = "ready"
    except LookupError as e:
        job.update(status="no_data", message=str(e))
    except Exception as e:  # noqa: BLE001 - reported to the viewer
        traceback.print_exc()
        job.update(status="error", message=f"{type(e).__name__}: {e}")


@router.get("/api/targets/{tid}/chemistry")
def chemistry(tid: str, request: Request, feature: str, start: int = 0, z: float = 0.0):
    from pipeline.chemistry import map_key, z_of
    if feature not in _features():
        return JSONResponse({"status": "error", "message": f"unknown feature {feature!r}"}, status_code=400)
    try:
        z = z_of(z)                                       # T109: the map at a redshift
    except ValueError as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)
    mkey = map_key(feature, z)
    d = request.app.state.builder.target_dir(tid) if _ID.match(tid) else None
    if d is None or not (d / "target.json").is_file():
        return JSONResponse({"status": "error", "message": "target not built"}, status_code=404)
    import json
    if json.loads((d / "target.json").read_text(encoding="utf-8")).get("synthetic"):
        return {"status": "no_data", "id": tid, "message": "synthetic target: no SPHEREx exposures to map"}
    meta = d / "chemistry" / f"{mkey}.json"
    if meta.is_file() and (d / "chemistry" / f"{mkey}.png").is_file():
        from pipeline.chemistry import VERSION
        stats = json.loads(meta.read_text(encoding="utf-8"))
        if stats.get("version") == VERSION:
            return {"status": "ready", "id": tid, "layer": f"x-{mkey}", "key": mkey, "z": z, **stats}
    key = (tid, mkey)
    with _lock:
        job = _jobs.get(key)
        if job and job["status"] in ("ready", "error", "no_data") and start:
            job = None                                    # finished earlier: a new start retries
        if job is None and start:
            job = {"status": "building", "done": 0, "total": 0}
            _jobs[key] = job
            threading.Thread(target=_run, args=(d, tid, feature, job, z), daemon=True, name=f"chem-{tid}-{mkey}").start()
    if job is None:
        return {"status": "not_started", "id": tid, "feature": feature, "z": z, "key": mkey}
    if job["status"] == "building":
        return JSONResponse({"status": "building", "id": tid, "feature": feature, "z": z, "key": mkey,
                             "done": job["done"], "total": job["total"]}, status_code=202)
    if job["status"] == "ready":
        return {"status": "ready", "id": tid, "layer": f"x-{mkey}", "key": mkey, "z": z, **job["stats"]}
    code = 200 if job["status"] == "no_data" else 500
    return JSONResponse({"status": job["status"], "id": tid, "feature": feature, "z": z, "key": mkey,
                         "message": job.get("message")}, status_code=code)


@router.get("/api/targets/{tid}/redshift")
def redshift(tid: str, request: Request):
    """T109: galaxies with a measured redshift in the field (SIMBAD), biggest first; cached per field."""
    import json
    d = request.app.state.builder.target_dir(tid) if _ID.match(tid) else None
    if d is None or not (d / "target.json").is_file():
        return JSONResponse({"status": "error", "message": "target not built"}, status_code=404)
    target = json.loads((d / "target.json").read_text(encoding="utf-8"))
    if target.get("synthetic"):
        return {"status": "ready", "id": tid, "galaxies": [], "provenance": None}
    from pipeline.chemistry import REDSHIFT_VERSION, galaxy_redshifts
    cache = d / "chemistry" / "redshift.json"
    if cache.is_file():
        hit = json.loads(cache.read_text(encoding="utf-8"))
        if hit.get("version") == REDSHIFT_VERSION:     # T112: answers from before the galaxy-only filter are redone
            return {"status": "ready", "id": tid, **hit}
    out = {**galaxy_redshifts(target), "version": REDSHIFT_VERSION}
    if out["provenance"] is not None:                  # SIMBAD answered: keep it (no answer: ask again next time)
        cache.parent.mkdir(exist_ok=True)
        cache.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"status": "ready", "id": tid, **out}


@router.get("/api/targets/{tid}/chemistry/candidates")   # T128: before .../chemistry/{name}, which would take it
def chemistry_candidates(tid: str, request: Request, maps: str = "", cats: str = "", preset: str = ""):
    """T128: the spots of a chemistry picture (maps = its keys joined by "-", as in the layer name) where its features
    show: ranked, named after the field's catalogue labels. cats=simbad,gaia,...: each spot looked up in those
    catalogues (pipeline/catcheck.py, cached per field), then uncatalogued first, other types next, the preset's
    expected types (`expects`) last. Visualization only: spots to look at."""
    from pipeline.chemistry import PRESETS, candidates
    d = request.app.state.builder.target_dir(tid) if _ID.match(tid) else None
    if d is None or not (d / "target.json").is_file():
        return JSONResponse({"status": "error", "message": "no such field"}, status_code=404)
    keys = [k for k in maps.split("-") if k]
    if not keys:
        return JSONResponse({"status": "error", "message": "maps=<key>[-<key>...] needed"}, status_code=400)
    try:
        out = candidates(d, keys)
    except ValueError as e:                               # unknown map, mixed redshifts, the same feature twice
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)
    except LookupError as e:                              # a map not made yet (or made on another grid)
        return JSONResponse({"status": "not_made", "message": str(e)}, status_code=404)
    want = [c for c in cats.split(",") if c]
    if want:
        from pipeline import catcheck
        if any(c not in catcheck.CATALOGUES for c in want):
            return JSONResponse({"status": "error", "message": f"catalogues: {', '.join(catcheck.CATALOGUES)}"},
                                status_code=400)
        import json
        frames = json.loads((d / "target.json").read_text(encoding="utf-8")).get("frames") or []
        mjds = sorted(f["mjd"] for f in frames if f.get("mjd"))
        year = catcheck._year_of_mjd(mjds[len(mjds) // 2]) if mjds else 2025.9     # SPHEREx's date for the field
        res = catcheck.check(d, [(it["ra_deg"], it["dec_deg"]) for it in out["items"]], want, year)
        expects = next((p.get("expects") for p in PRESETS if p["id"] == preset), None)
        out["items"] = catcheck.tag(out["items"], res, expects)
        out.update(checked=[c for c in want if c not in res["failed"]], failed=res["failed"], preset=preset or None)
    return {"status": "ready", "id": tid, **out}


@router.get("/api/targets/{tid}/chemistry/{name}")
def chemistry_png(tid: str, name: str, request: Request):
    m = re.match(r"^([a-z0-9_]+(?:-[a-z0-9_]+)*)\.png$", name)
    d = request.app.state.builder.target_dir(tid) if _ID.match(tid) else None
    missing = JSONResponse({"status": "error", "message": "no such map"}, status_code=404)
    if not m or d is None:
        return missing
    parts = m.group(1).split("-")
    if len(parts) > 1:                                   # T96/T108: the colour picture of 2+ maps made earlier
        import io
        from PIL import Image
        from pipeline.chemistry import combined_map
        try:
            rgb, cov = combined_map(d, parts)
        except (ValueError, LookupError):
            return missing
        buf = io.BytesIO()
        Image.fromarray(np.dstack([rgb, np.where(cov, 255, 0).astype(np.uint8)]), "RGBA").save(buf, "PNG")
        return Response(buf.getvalue(), media_type="image/png", headers={"Cache-Control": "no-cache"})
    from pipeline.chemistry import parse_key
    try:
        parse_key(parts[0])                              # T109: <feature>[_z<z·10⁴>]
    except ValueError:
        return missing
    if not (d / "chemistry" / name).is_file():
        return missing
    import io
    from PIL import Image
    from pipeline.chemistry import load_map
    grey, cov = load_map(d / "chemistry" / name)         # T121: the map as shown on the sky map (smoothed)
    buf = io.BytesIO()
    Image.fromarray(np.dstack([grey.round().astype(np.uint8), np.where(cov, 255, 0).astype(np.uint8)]), "LA").save(buf, "PNG")
    return Response(buf.getvalue(), media_type="image/png", headers={"Cache-Control": "no-cache"})
