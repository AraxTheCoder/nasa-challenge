"""T93: chemistry maps for a built field (CONTRACTS "Chemistry maps").

    GET /api/chemistry/features                                 the features (id, name, µm, kind, what)
    GET /api/targets/<id>/chemistry?feature=<f>                 cached result, else {"status": "not_started"}
    GET /api/targets/<id>/chemistry?feature=<f>&start=1         start; 202 {"status": "building", done, total},
                                                                then 200 {"status": "ready", ...stats, "layer"}
    GET /api/targets/<id>/chemistry/<f>.png                     the map (grey + alpha) on the field grid
    Map layer: /api/hips/<id>/x-<f>/...                         (server/hips.py), like the A − B difference

`pipeline.chemistry` makes the map from the field's SPHEREx exposures (a few seconds with cached cutouts).
"""
from __future__ import annotations

import re
import threading
import traceback

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter()
_ID = re.compile(r"^[a-z0-9-]+$")
_jobs: dict[tuple[str, str], dict] = {}
_lock = threading.Lock()


def _features():
    from pipeline.chemistry import FEATURES
    return FEATURES


@router.get("/api/chemistry/features")
def features():
    return {"features": [{"id": k, "name": n, "um": um, "half_width_um": hw, "kind": kind, "what": what}
                         for k, (n, um, hw, kind, what) in _features().items()]}


def _run(target_dir, tid: str, feature: str, job: dict) -> None:
    from pipeline.chemistry import compute
    try:
        job["stats"] = compute(target_dir, feature, progress=lambda d, t: job.update(done=d, total=t))
        job["status"] = "ready"
    except LookupError as e:
        job.update(status="no_data", message=str(e))
    except Exception as e:  # noqa: BLE001 - reported to the viewer
        traceback.print_exc()
        job.update(status="error", message=f"{type(e).__name__}: {e}")


@router.get("/api/targets/{tid}/chemistry")
def chemistry(tid: str, request: Request, feature: str, start: int = 0):
    if feature not in _features():
        return JSONResponse({"status": "error", "message": f"unknown feature {feature!r}"}, status_code=400)
    d = request.app.state.builder.target_dir(tid) if _ID.match(tid) else None
    if d is None or not (d / "target.json").is_file():
        return JSONResponse({"status": "error", "message": "target not built"}, status_code=404)
    import json
    if json.loads((d / "target.json").read_text(encoding="utf-8")).get("synthetic"):
        return {"status": "no_data", "id": tid, "message": "synthetic target: no SPHEREx exposures to map"}
    meta = d / "chemistry" / f"{feature}.json"
    if meta.is_file() and (d / "chemistry" / f"{feature}.png").is_file():
        from pipeline.chemistry import VERSION
        stats = json.loads(meta.read_text(encoding="utf-8"))
        if stats.get("version") == VERSION:
            return {"status": "ready", "id": tid, "layer": f"x-{feature}", **stats}
    key = (tid, feature)
    with _lock:
        job = _jobs.get(key)
        if job and job["status"] in ("ready", "error", "no_data") and start:
            job = None                                    # finished earlier: a new start retries
        if job is None and start:
            job = {"status": "building", "done": 0, "total": 0}
            _jobs[key] = job
            threading.Thread(target=_run, args=(d, tid, feature, job), daemon=True, name=f"chem-{tid}-{feature}").start()
    if job is None:
        return {"status": "not_started", "id": tid, "feature": feature}
    if job["status"] == "building":
        return JSONResponse({"status": "building", "id": tid, "feature": feature, "done": job["done"],
                             "total": job["total"]}, status_code=202)
    if job["status"] == "ready":
        return {"status": "ready", "id": tid, "layer": f"x-{feature}", **job["stats"]}
    code = 200 if job["status"] == "no_data" else 500
    return JSONResponse({"status": job["status"], "id": tid, "feature": feature, "message": job.get("message")},
                        status_code=code)


@router.get("/api/targets/{tid}/chemistry/{name}")
def chemistry_png(tid: str, name: str, request: Request):
    m = re.match(r"^([a-z0-9_]+)\.png$", name)
    d = request.app.state.builder.target_dir(tid) if _ID.match(tid) else None
    if not m or d is None or m.group(1) not in _features() or not (d / "chemistry" / name).is_file():
        return JSONResponse({"status": "error", "message": "no such map"}, status_code=404)
    return FileResponse(d / "chemistry" / name, media_type="image/png", headers={"Cache-Control": "no-cache"})
