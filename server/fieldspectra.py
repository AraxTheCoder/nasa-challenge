"""T85/T86: spectra of every catalogue source of a field, and the ones that stand out (CONTRACTS v0.15);
T61: the ones that change brightness (`variability`, v0.33).

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

from . import limits

router = APIRouter()
_ID = re.compile(r"^[a-z0-9-]+$")
_jobs: dict[str, dict] = {}
_lock = threading.Lock()
limits.register_active(lambda: len(_jobs))    # T58: field-spectra runs count against the server-wide cap


@lru_cache(maxsize=64)
def _analysis_lock_for(path: str):
    return threading.Lock()


@lru_cache(maxsize=64)
def _outliers(path: str, mtime: float, sources_json: str, catalogue_json: str = "{}") -> dict:
    from pipeline import fieldspectra, spectral_outliers
    from pathlib import Path
    from pipeline import profile_matches, redshift
    from detect.variability import VERSION as variability_version
    derived = Path(path).with_suffix(".analysis.json")
    stamp = [mtime, spectral_outliers.VERSION, profile_matches.VERSION, variability_version, redshift.VERSION, sources_json, catalogue_json]
    if derived.is_file():
        try:
            hit = json.loads(derived.read_text(encoding="utf-8"))
            if hit.get("stamp") == stamp:
                return hit["result"]
        except (ValueError, OSError):
            pass
    fs = _read_field(path, mtime)
    fs = {**fs, "sources": json.loads(sources_json)}
    fieldspectra.seed_spectra(fs)          # measured from the command line: clicks on its sources answer at once too
    fs, shifts = redshift.resolve(fs, json.loads(catalogue_json))
    blends = spectral_outliers._blends(fs["sources"])
    out = spectral_outliers.find_outliers(fs, blends=blends)
    out["chemistry_profiles"] = profile_matches.find_matches(fs, blends=blends)
    out["redshifts"] = shifts
    try:                                   # T61: sources that change brightness (the same spectra, the level)
        from detect.variability import find_variables
        out["variability"] = find_variables(fs)
    except Exception as e:  # noqa: BLE001 - the outlier list must not depend on it
        traceback.print_exc()
        out["variability"] = {"status": "error", "message": f"{type(e).__name__}: {e}", "variables": [], "blended": []}
    result = {**out, "field": {"target_id": fs["target_id"], "n_sources": len(fs["sources"]),
                             "n_exposures": len(fs["exposures"]), "missing": len(fs["missing"]),
                             "seconds": fs.get("seconds"), "version": fs.get("version"),
                             "fieldspectra_version": fieldspectra.VERSION}}
    fieldspectra._write(derived, {"stamp": stamp, "result": result})
    return result


@lru_cache(maxsize=8)
def _read_field(path: str, mtime: float) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _cached(target: dict, target_dir=None) -> dict | None:
    from pipeline import fieldspectra
    p = fieldspectra.cache_path(target["id"])
    if not p.is_file():
        return None
    mtime = p.stat().st_mtime
    fs_head = _read_field(str(p), mtime)
    sources = fieldspectra.sources_of(target)
    from pipeline.srcfind import spherex_sources
    sources = sources + spherex_sources(target, sources)   # T135: stored ones only, never found here
    if fs_head.get("version") != fieldspectra.VERSION or \
            fs_head.get("sources_key") != fieldspectra._key(sources):
        return None                         # older method or the labels changed: measure again
    from pipeline.spectral_outliers import peer_group
    from .redshifts import catalogue
    cat = catalogue(target_dir, target) if target_dir is not None and any(peer_group(s) != "stars" for s in sources) else {}
    catalogue_json = json.dumps(cat, sort_keys=True)
    sources_json = json.dumps(sources, sort_keys=True)
    with _analysis_lock_for(str(p)):  # concurrent polls of this field share one analysis
        result = _outliers(str(p), mtime, sources_json, catalogue_json)
    return _tag_spherex(result, target, target_dir, sources)


def _tag_spherex(result: dict, target: dict, target_dir, sources: list[dict]) -> dict:
    """T135: flagged SPHEREx-only sources looked up in SIMBAD / Gaia / CatWISE (cached per field), uncatalogued
    first. A copy: the analysis above is cached in memory."""
    if target_dir is None or not any(s.get("source") == "spherex" for s in sources):
        return result
    from pipeline import catcheck, srcfind
    mjds = sorted(f["mjd"] for f in target.get("frames", []) if f.get("mjd"))
    year = catcheck._year_of_mjd(mjds[len(mjds) // 2]) if mjds else 2025.9
    try:
        items = srcfind.tag_items([dict(it) for it in result.get("items", [])], target_dir, sources, year)
    except Exception:  # noqa: BLE001 - the list stands without the lookup
        traceback.print_exc()
        return result
    return {**result, "items": items}


def _state(target: dict, start: bool, target_dir=None) -> dict:
    hit = _cached(target, target_dir)
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
        return {"status": "ready", **(_cached(target, target_dir) or {})}
    return dict(job)


@router.get("/api/targets/{tid}/spectral-outliers")
async def spectral_outliers(tid: str, request: Request, start: int = 0):
    path = request.app.state.builder.target_dir(tid) / "target.json" if _ID.match(tid) else None
    if path is None or not path.is_file():
        return JSONResponse({"status": "error", "message": "target not built"}, status_code=404)
    target = json.loads(path.read_text(encoding="utf-8"))
    if target.get("synthetic"):
        return {"status": "no_data", "id": tid, "message": "synthetic target: there are no SPHEREx images to measure"}
    if start and tid not in _jobs and await run_in_threadpool(_cached, target, path.parent) is None:
        deny = limits.new_job(request)               # T58: a new run costs a job (per IP + server-wide cap)
        if deny is not None:
            return deny
    body = await run_in_threadpool(_state, target, bool(start), path.parent)
    code = {"ready": 200, "not_started": 200, "building": 202}.get(body["status"], 500)
    return JSONResponse({"id": tid, **body}, status_code=code)
