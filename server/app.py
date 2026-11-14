"""Live API (CONTRACTS v0.3). Run with `python -m server [--port 8000] [--fixture]`."""
from __future__ import annotations

import re
from pathlib import Path

import asyncio

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response

import json
import threading

from . import hips
from .skycache import SkyCache
from .builder import REPO, Builder
from .photometry import router as photometry_router  # T49
from .coords import CoordError, parse_dec, parse_ra, parse_size, target_id

_ID = re.compile(r"^[a-z0-9-]+$")
_FRAME = re.compile(r"^[A-Za-z0-9_-]+\.(png|webp)$")
_HTTP = {"ready": 200, "building": 202, "no_data": 404, "error": 500}


def create_app(cache_root: Path = REPO / "data" / "targets", fixture: bool = False,
               tiles_remote: str | None = None, use_remote: bool = False,
               cutouts_remote: str | None = None) -> FastAPI:
    if not fixture:
        from pipeline import s3   # T57: builds get their cutouts from the team VM (fallback: S3 directly)
        s3.REMOTE = cutouts_remote.rstrip("/") if cutouts_remote else None
    builder = Builder(cache_root, fixture=fixture)
    app = FastAPI(title="SPHEREx blink Live API", version="0.3")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"],
                       allow_headers=["*"])
    app.state.builder = builder
    app.include_router(photometry_router)  # T49: /api/targets/<id>/photometry

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

    @app.get("/api/targets/{tid}/objects")
    def target_objects(tid: str):
        """T51: known asteroids/comets (JPL) + detections. 202 while running, 200 when target.json has them."""
        if not _ID.match(tid):
            raise HTTPException(404)
        body = builder.objects(tid)
        code = {"ready": 200, "building": 202}.get(body["status"], 404 if "not built" in str(body.get("message")) else 500)
        return JSONResponse(body, status_code=code)

    sky_cache: dict = {}
    sky_lock = threading.Lock()
    sky_dir = cache_root.parent / "sky_labels"

    @app.get("/api/sky-labels")
    def sky_labels(ra: float, dec: float, radius: float = 0.5):
        """T72: catalogue labels for any patch of the map (SIMBAD, VSX, CatWISE), snapped to a grid
        and cached in memory + data/sky_labels/. ~2-4 s the first time, instant after."""
        from pipeline.labels import sky_labels as compute, sky_region
        if not (-90 <= dec <= 90) or not (0 < radius <= 5):
            raise HTTPException(400, "bad ra/dec/radius")
        r_ra, r_dec, r_rad = sky_region(ra % 360, dec, radius)
        key = f"{r_ra:.4f}_{r_dec:+.4f}_{r_rad:.2f}"
        hit = sky_cache.get(key)
        f = sky_dir / f"{key}.json"
        if hit is None and f.is_file():
            hit = sky_cache[key] = json.loads(f.read_text(encoding="utf-8"))
        if hit is None:
            hit = compute(r_ra, r_dec, r_rad)
            if hit["provenance"]:              # cache only when a catalogue answered
                with sky_lock:
                    sky_cache[key] = hit
                    sky_dir.mkdir(parents=True, exist_ok=True)
                    tmp = f.with_suffix(".part")
                    tmp.write_text(json.dumps(hit), encoding="utf-8")
                    tmp.replace(f)
        return JSONResponse(hit, headers={"Cache-Control": "max-age=86400"})

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
        # T41: render the field's tiles now, in the background, so the map finds them ready
        threading.Thread(target=hips.prerender, args=(builder.target_dir(tid),), daemon=True).start()
        return {"id": tid, "synthetic": bool(t.get("synthetic")), "layers": hips.layers(tid, t),
                "frame_layers": hips.frame_layers(tid, t)}       # T81: f<id>; A − B is d-<a>-<b>

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

    # -- T41: cached all-sky HiPS maps (IRSA/CDS) for the sky map -----------------------------

    from tilegen.client import TileGenerator

    sky = SkyCache(cache_root.parent / "hips_cache", TileGenerator(tiles_remote, use_remote))
    if not fixture:
        sky.warm()
    _MEDIA = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}

    @app.get("/api/hips/{tid}/{layer}/properties")
    def hips_layer_properties(tid: str, layer: str):
        """T81: frames (f003) and differences (d-f003-f017) as layers, like the epochs."""
        t = _target(tid)
        if not re.match(hips.LAYER_RE, layer) or not hips.has_layer(t, layer):
            raise HTTPException(404)
        return PlainTextResponse(hips.properties(tid, t, layer))

    @app.get("/api/hips/{tid}/{layer}/Norder{order}/Dir{d}/Npix{name}")
    def hips_layer_tile(tid: str, layer: str, order: int, d: int, name: str):
        if not re.match(hips.LAYER_RE, layer) or not name.endswith(".png") or not 0 <= order <= hips.HIPS_ORDER:
            raise HTTPException(404)
        t = _target(tid)
        if not hips.has_layer(t, layer):
            raise HTTPException(404)
        try:
            npix = int(name[:-4])
        except ValueError:
            raise HTTPException(404) from None
        png = hips.tile_png(builder.target_dir(tid), layer, order, npix)
        if png is None:
            return Response(status_code=404, headers={"Cache-Control": "public, max-age=3600"})
        return Response(png, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})

    @app.get("/api/sky/{survey}/{path:path}")
    async def sky_file(survey: str, path: str, request: Request):
        if not SkyCache.valid(survey, path):
            raise HTTPException(404)
        slot = False
        try:
            if sky.is_live_render(survey, path):
                # Wait for a render slot, but give up as soon as the browser hangs up, so tiles that
                # left the screen never block visible ones.
                while not sky.live_slots.acquire(blocking=False):
                    if await request.is_disconnected():
                        return Response(status_code=499)
                    await asyncio.sleep(0.05)
                slot = True
                if await request.is_disconnected():
                    return Response(status_code=499)
            data = await run_in_threadpool(sky.get, survey, path)
        except Exception as e:  # noqa: BLE001 - upstream / tile generator down
            from pipeline.mirror import IndexNotReady
            if isinstance(e, IndexNotReady):        # fresh checkout: index being built, ask again
                return Response(str(e), status_code=503, headers={"Retry-After": "20"})
            return Response(str(e), status_code=502)
        finally:
            if slot:
                sky.live_slots.release()
        if data is None:
            return Response(status_code=404, headers={"Cache-Control": "public, max-age=86400"})
        if path == "properties":
            return PlainTextResponse(data.decode("utf-8", "replace"))
        sky.prefetch_around(survey, path)
        return Response(data, media_type=_MEDIA[path.rsplit(".", 1)[-1]],
                        headers={"Cache-Control": "public, max-age=604800, immutable"})

    # -- T47: which tile generator renders the live deep-zoom tiles (local / remote US VM) --------

    def settings_info() -> dict:
        info = dict(sky.tiles.info())
        if not fixture:
            from pipeline import s3
            info["cutouts_remote"] = s3.REMOTE           # T57: who cuts the images for builds
            info["cutouts"] = "remote" if s3.remote_available() else "s3"
        return info

    @app.get("/api/settings")
    def get_settings():
        return settings_info()

    @app.post("/api/settings")
    async def set_settings(request: Request):
        body = await request.json()
        if "tiles" in body:
            try:
                sky.tiles.use_remote(body["tiles"] == "remote")
            except ValueError as e:
                return JSONResponse({"error": str(e)}, status_code=400)
        return settings_info()

    @app.get("/api/health")
    def health():
        return {"ok": True, "mode": "fixture" if fixture else "live"}

    return app
