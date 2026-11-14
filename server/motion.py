"""T91: a star's motion measured from SPHEREx alone (CONTRACTS v0.23).

    GET /api/targets/<id>/motion?ra=&dec=[&start=0]      the same for the moving catalogued star at that spot
                                                         (within 8″; 404 {"status": "none"} if there is none)
    GET /api/targets/<id>/motion?name=<label name or id>[&start=0]   cached result, else starts measuring
        (start=0: only the cached result, or {"status": "not_started"}):
        202 {"status": "building", "done", "total"} (poll), then 200 {"status": "ready" | "not_found" | ...}

First time ~15 s (a Gaussian fit to the star and up to 40 reference stars in every exposure of the field, the
field cutouts of T85 cached), then cached under data/motion/.
"""
from __future__ import annotations

import json
import re
import threading
import traceback

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from . import limits

router = APIRouter()
_ID = re.compile(r"^[a-z0-9-]+$")
_jobs: dict[tuple[str, str], dict] = {}
_lock = threading.Lock()
limits.register_active(lambda: len(_jobs))    # T58: counts against the server-wide job cap


def _state(target: dict, name: str, start: bool = True) -> dict:
    from pipeline import astrometry
    star = astrometry.find_star(target, name)
    if star is None:
        return {"status": "error", "message": f"no catalogue label called {name!r} in this field"}
    hit = astrometry.cached(target, star["id"])
    if hit is not None:
        return {**hit, "status": hit.get("status", "ready")}
    key = (target["id"], star["id"])
    with _lock:
        job = _jobs.get(key)
        if job is None and not start:
            return {"status": "not_started", "name": star["name"],
                    "message": "not measured yet: start=1 (default) measures it (~15 s)"}
        if job is None:
            job = _jobs[key] = {"status": "building", "done": 0, "total": None, "name": star["name"]}

            def run():
                try:
                    r = astrometry.measure_motion(target, star["id"], progress=lambda d, n: job.update(done=d, total=n))
                    job.update(final=r, status="done")
                except Exception as e:  # noqa: BLE001
                    traceback.print_exc()
                    job.update(status="error", message=f"{type(e).__name__}: {e}")
                finally:
                    with _lock:
                        _jobs.pop(key, None)

            threading.Thread(target=run, daemon=True, name=f"motion-{key}").start()
    if job.get("status") == "done":
        return job["final"]
    return {k: v for k, v in job.items() if k != "final"}


def _is_new(target: dict, name: str) -> bool:
    from pipeline import astrometry
    star = astrometry.find_star(target, name)
    return bool(star) and (target["id"], star["id"]) not in _jobs and astrometry.cached(target, star["id"]) is None


MIN_PM_MAS_YR = 300
NEAR_ARCSEC = 8.0


def _moving_label_at(target: dict, ra: float, dec: float) -> str | None:
    """Id of the catalogued star moving >= 0.3″/yr nearest to (ra, dec) within 8″ (any of its frame positions)."""
    import math
    best, bd = None, NEAR_ARCSEC
    for lab in target.get("labels", []):
        if (lab.get("pm_mas_yr") or 0) < MIN_PM_MAS_YR or (lab.get("kind") or "").lower() in ("asteroid", "comet", "planet", "moon"):
            continue
        for p in lab.get("positions", []):
            d = 3600 * math.hypot(((p["ra_deg"] - ra + 180) % 360 - 180) * math.cos(math.radians(dec)), p["dec_deg"] - dec)
            if d < bd:
                best, bd = lab.get("id"), d
    return best


@router.get("/api/targets/{tid}/motion")
async def motion(tid: str, request: Request, name: str | None = None, ra: float | None = None,
                 dec: float | None = None, start: int = 1):
    path = request.app.state.builder.target_dir(tid) / "target.json" if _ID.match(tid) else None
    if path is None or not path.is_file():
        return JSONResponse({"status": "error", "message": "target not built"}, status_code=404)
    target = json.loads(path.read_text(encoding="utf-8"))
    if target.get("synthetic"):
        return {"status": "no_data", "id": tid, "message": "synthetic target: there are no SPHEREx images to measure"}
    if name is None:                                 # by position: the spectrum panel's "is this a moving star?"
        if ra is None or dec is None:
            return JSONResponse({"status": "error", "message": "name or ra + dec needed"}, status_code=400)
        name = _moving_label_at(target, ra, dec)
        if name is None:
            return JSONResponse({"target_id": tid, "status": "none",
                                 "message": "no catalogued star moving ≥ 0.3″/yr at this position"}, status_code=404)
    if start and await run_in_threadpool(_is_new, target, name):
        deny = limits.new_job(request)
        if deny is not None:
            return deny
    body = await run_in_threadpool(_state, target, name, bool(start))
    code = {"building": 202, "error": 404}.get(body.get("status"), 200)
    return JSONResponse({"target_id": tid, **body}, status_code=code)
