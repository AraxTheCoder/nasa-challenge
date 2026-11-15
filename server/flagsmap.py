"""T60: where a field's data is unreliable (CONTRACTS: "Quality flags").

    GET /api/targets/<id>/flags        {"status": "ready", "n_frames", "bad_fraction", "counts": {flag: pixel-frames},
                                        "meanings": {flag: {kind, meaning}}, "image": "flags.png", "min_share"}
    GET /api/targets/<id>/flags.png    RGBA overlay on the field grid (same size and orientation as the frames):
                                        red = unreliable, amber = look twice, opacity = share of frames flagged

Computed on first request from the FLAGS plane of the field's frames (cutouts re-fetched if they left the cache,
~1-12 s), then kept next to target.json.
"""
from __future__ import annotations

import json
import re
import threading

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter()
_ID = re.compile(r"^[a-z0-9-]+$")
_locks: dict[str, threading.Lock] = {}
_guard = threading.Lock()


def _build(tdir) -> dict | None:
    from PIL import Image
    from pipeline import flags
    tj = tdir / "target.json"
    if not tj.is_file():
        return None
    meta, png = tdir / "flags.json", tdir / "flags.png"
    with _guard:
        lock = _locks.setdefault(str(tdir), threading.Lock())
    with lock:
        if meta.is_file() and png.is_file() and meta.stat().st_mtime >= tj.stat().st_mtime:
            return json.loads(meta.read_text(encoding="utf-8"))
        target = json.loads(tj.read_text(encoding="utf-8"))
        if target.get("synthetic"):
            return {"status": "no_data", "message": "synthetic target: there are no SPHEREx flags"}
        m = flags.field_mask(target)
        if not m["n_frames"]:
            return {"status": "no_data", "message": "none of the field's images could be read"}
        Image.fromarray(m["rgba"], "RGBA").save(png, "PNG")
        out = {"status": "ready", "n_frames": m["n_frames"], "bad_fraction": round(m["bad_fraction"], 4),
               "counts": m["counts"], "min_share": flags.MIN_SHARE, "image": "flags.png",
               "meanings": {n: {"kind": flags.NAMES[n][1], "meaning": flags.NAMES[n][2]} for n in m["counts"]}}
        meta.write_text(json.dumps(out), encoding="utf-8")
        return out


@router.get("/api/targets/{tid}/flags")
async def field_flags(tid: str, request: Request):
    tdir = request.app.state.builder.target_dir(tid) if _ID.match(tid) else None
    body = await run_in_threadpool(_build, tdir) if tdir else None
    if body is None:
        return JSONResponse({"status": "error", "message": "target not built"}, status_code=404)
    return {"id": tid, **body}


@router.get("/api/targets/{tid}/flags.png")
async def field_flags_png(tid: str, request: Request):
    tdir = request.app.state.builder.target_dir(tid) if _ID.match(tid) else None
    body = await run_in_threadpool(_build, tdir) if tdir else None
    if not body or body.get("status") != "ready":
        return JSONResponse({"status": "error", "message": "no flags for this target"}, status_code=404)
    return FileResponse(tdir / "flags.png", media_type="image/png")
