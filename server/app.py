"""Live API (CONTRACTS v0.3). Run with `python -m server [--port 8000] [--fixture]`."""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response

import json

from . import hips
from .builder import REPO, Builder
from .coords import CoordError, parse_dec, parse_ra, parse_size, target_id

_ID = re.compile(r"^[a-z0-9-]+$")
_FRAME = re.compile(r"^[A-Za-z0-9_-]+\.(png|webp)$")
_HTTP = {"ready": 200, "building": 202, "no_data": 404, "error": 500}


def create_app(cache_root: Path = REPO / "data" / "targets", fixture: bool = False) -> FastAPI:
    builder = Builder(cache_root, fixture=fixture)
    app = FastAPI(title="SPHEREx blink Live API", version="0.3")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"],
                       allow_headers=["*"])
    app.state.builder = builder

    def reply(job) -> JSONResponse:
        return JSONResponse(job.body(), status_code=_HTTP[job.status])

    @app.get("/api/target")
    def request_target(ra: str, dec: str, size: str | None = None, refresh: int = 0):
        try:
            ra_deg, dec_deg, size_am = parse_ra(ra), parse_dec(dec), parse_size(size)
        except CoordError as e:
            return JSONResponse({"status": "error", "message": str(e)}, status_code=400)
        tid, ra_r, dec_r = target_id(ra_deg, dec_deg, size_am)
        return reply(builder.request(tid, ra_r, dec_r, size_am, refresh=bool(refresh)))

    @app.get("/api/jobs/{tid}")
    def job_status(tid: str):
        job = builder.get(tid) if _ID.match(tid) else None
        if job is None:
            raise HTTPException(404, "unknown job")
        return reply(job)

    @app.get("/api/targets")
    def index():
        return builder.index()

    @app.get("/api/targets/{tid}/target.json")
    def target_json(tid: str):
        path = builder.target_dir(tid) / "target.json" if _ID.match(tid) else None
        if path is None or not path.is_file():
            raise HTTPException(404, "target not built")
        return FileResponse(path, media_type="application/json",
                            headers={"Cache-Control": "no-cache"})

    @app.get("/api/targets/{tid}/labels")
    def target_labels(tid: str):
        """T37: catalogue labels on request. 202 while SIMBAD/Gaia are asked, 200 when target.json has them."""
        if not _ID.match(tid):
            raise HTTPException(404)
        body = builder.labels(tid)
        code = {"ready": 200, "building": 202}.get(body["status"], 404 if "not built" in str(body.get("message")) else 500)
        return JSONResponse(body, status_code=code)

    @app.get("/api/targets/{tid}/frames/{name}")
    def frame(tid: str, name: str):
        if not (_ID.match(tid) and _FRAME.match(name)):
            raise HTTPException(404)
        path = builder.target_dir(tid) / "frames" / name
        if not path.is_file():
            raise HTTPException(404)
        return FileResponse(path, headers={"Cache-Control": "public, max-age=86400"})

    # -- T32: per-epoch HiPS tiles for Aladin Lite ------------------------------------------------

    def _target(tid: str) -> dict:
        path = builder.target_dir(tid) / "target.json" if _ID.match(tid) else None
        if path is None or not path.is_file():
            raise HTTPException(404, "target not built")
        return json.loads(path.read_text(encoding="utf-8"))

    @app.get("/api/hips/{tid}")
    def hips_layers(tid: str):
        t = _target(tid)
        return {"id": tid, "synthetic": bool(t.get("synthetic")), "layers": hips.layers(tid, t)}

    @app.get("/api/hips/{tid}/e{ep}/properties")
    def hips_properties(tid: str, ep: int):
        t = _target(tid)
        if ep not in hips.epochs(t):
            raise HTTPException(404)
        return PlainTextResponse(hips.properties(tid, t, ep))

    @app.get("/api/hips/{tid}/e{ep}/Norder{order}/Dir{d}/Npix{name}")
    def hips_tile(tid: str, ep: int, order: int, d: int, name: str):
        if not name.endswith(".png") or not 0 <= order <= hips.HIPS_ORDER:
            raise HTTPException(404)
        _target(tid)
        try:
            npix = int(name[:-4])
        except ValueError:
            raise HTTPException(404) from None
        png = hips.tile_png(builder.target_dir(tid), ep, order, npix)
        if png is None:
            return Response(status_code=404, headers={"Cache-Control": "public, max-age=3600"})
        return Response(png, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})

    @app.get("/api/health")
    def health():
        return {"ok": True, "mode": "fixture" if fixture else "live"}

    return app
