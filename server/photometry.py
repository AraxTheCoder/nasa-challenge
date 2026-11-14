"""T49: light curves and spectra on the fly (CONTRACTS v0.10 "Photometry").

    GET /api/targets/<id>/photometry?ra=&dec=      a sky position (ICRS, degrees)
    GET /api/targets/<id>/photometry?x=&y=         a pixel on the target grid (CONTRACTS conventions)
    GET /api/targets/<id>/photometry               the field centre

Measures the cached SPHEREx cutouts of a built target with `pipeline.photometry` (a few seconds,
results kept in memory). Synthetic targets have no SPHEREx images: 200 with status no_data.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

router = APIRouter()
_ID = re.compile(r"^[a-z0-9-]+$")


@lru_cache(maxsize=256)
def _measure(target_json: str, mtime: float, ra: float, dec: float) -> dict:
    from pipeline.photometry import measure  # needs astropy/scipy; imported on first use only

    target = json.loads(Path(target_json).read_text(encoding="utf-8"))
    return measure(target, ra, dec)


def _grid_to_sky(target: dict, x: float, y: float) -> tuple[float, float]:
    from pipeline.labels import Grid

    g = Grid(target)
    ra, dec = g.wcs.pixel_to_world_values(x, g.h - 1 - y)  # contract y is down; FITS y is up
    return float(ra), float(dec)


@router.get("/api/targets/{tid}/photometry")
async def photometry(tid: str, request: Request, ra: float | None = None, dec: float | None = None,
                     x: float | None = None, y: float | None = None):
    path = request.app.state.builder.target_dir(tid) / "target.json" if _ID.match(tid) else None
    if path is None or not path.is_file():
        return JSONResponse({"status": "error", "message": "target not built"}, status_code=404)
    target = json.loads(path.read_text(encoding="utf-8"))
    if target.get("synthetic"):  # a valid answer ("nothing to measure"), not a missing resource: 200
        return {"status": "no_data", "id": tid, "message": "synthetic target: there are no SPHEREx images to measure"}
    if ra is None or dec is None:
        if x is not None and y is not None:
            ra, dec = await run_in_threadpool(_grid_to_sky, target, x, y)
        else:
            ra, dec = target["center"]["ra_deg"], target["center"]["dec_deg"]
    if not (0 <= ra < 360 and -90 <= dec <= 90):
        return JSONResponse({"status": "error", "message": "ra must be in [0, 360), dec in [-90, 90]"}, status_code=400)
    res = await run_in_threadpool(_measure, str(path), path.stat().st_mtime, round(ra, 5), round(dec, 5))
    return {"status": "ready", **res}
