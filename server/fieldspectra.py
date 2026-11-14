"""T85/T86: spectra of every catalogue source of a field, and the ones that stand out (CONTRACTS v0.15).

    GET /api/targets/<id>/spectral-outliers             cached result, or {"status": "not_started"}
    GET /api/targets/<id>/spectral-outliers?start=1     start measuring (202 {"status": "building", done, total}
                                                        while it runs, poll), then 200 {"status": "ready", ...}

Measuring reads every SPHEREx exposure of the field once (~250, ~20 s the first time, then cached under
data/field_spectra/). Afterwards each source's spectrum is also in the per-position spectrum cache, so
`/api/photometry?ra=&dec=` at a source answers at once.
"""
from __future__ import annotations

import json
import re
import threading
import traceback
from functools import lru_cache

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

router = APIRouter()
_ID = re.compile(r"^[a-z0-9-]+$")
_jobs: dict[str, dict] = {}
_lock = threading.Lock()


@lru_cache(maxsize=64)
def _outliers(path: str, mtime: float) -> dict:
    from pipeline import fieldspectra, spectral_outliers
    fs = json.loads(open(path, encoding="utf-8").read())
    fieldspectra.seed_spectra(fs)          # measured from the command line: clicks on its sources answer at once too
    out = spectral_outliers.find_outliers(fs)
    return {**out, "field": {"target_id": fs["target_id"], "n_sources": len(fs["sources"]),
                             "n_exposures": len(fs["exposures"]), "missing": len(fs["missing"]),
                             "seconds": fs.get("seconds"), "version": fs.get("version"),
                             "fieldspectra_version": fieldspectra.VERSION}}


def _cached(target: dict) -> dict | None:
    from pipeline import fieldspectra
    p = fieldspectra.cache_path(target["id"])
    if not p.is_file():
        return None
    fs_head = json.loads(p.read_text(encoding="utf-8"))
    if fs_head.get("version") != fieldspectra.VERSION or \
            fs_head.get("sources_key") != fieldspectra._key(fieldspectra.sources_of(target)):
        return None                         # older method or the labels changed: measure again
    return _outliers(str(p), p.stat().st_mtime)


def _state(target: dict, start: bool) -> dict:
    hit = _cached(target)
    if hit is not None:
        return {"status": "ready", **hit}
    tid = target["id"]
    with _lock:
        job = _jobs.get(tid)
        if job is None and not start:
            return {"status": "not_started", "message": "start=1 measures every source of the field in every "
                                                        "exposure (~20 s the first time)"}
        if job is None:
            job = _jobs[tid] = {"status": "building", "done": 0, "total": None}

            def run():
                from pipeline import fieldspectra
                try:
                    fs = fieldspectra.measure_field(target, progress=lambda d, n: job.update(done=d, total=n))
                    fieldspectra.seed_spectra(fs)
                    job.update(status="ready")
                except Exception as e:  # noqa: BLE001
                    traceback.print_exc()
                    job.update(status="error", message=f"{type(e).__name__}: {e}")
                finally:
                    with _lock:
                        _jobs.pop(tid, None)

            threading.Thread(target=run, daemon=True, name=f"fieldspectra-{tid}").start()
    if job["status"] == "ready":
        return {"status": "ready", **(_cached(target) or {})}
    return dict(job)


@router.get("/api/targets/{tid}/spectral-outliers")
async def spectral_outliers(tid: str, request: Request, start: int = 0):
    path = request.app.state.builder.target_dir(tid) / "target.json" if _ID.match(tid) else None
    if path is None or not path.is_file():
        return JSONResponse({"status": "error", "message": "target not built"}, status_code=404)
    target = json.loads(path.read_text(encoding="utf-8"))
    if target.get("synthetic"):
        return {"status": "no_data", "id": tid, "message": "synthetic target: there are no SPHEREx images to measure"}
    body = await run_in_threadpool(_state, target, bool(start))
    code = {"ready": 200, "not_started": 200, "building": 202}.get(body["status"], 500)
    return JSONResponse({"id": tid, **body}, status_code=code)
