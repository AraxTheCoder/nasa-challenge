"""tilegen service: `python -m tilegen [--host 127.0.0.1] [--port 8100]`.

    GET /health                                            -> {"ok": true, "orders": [6, 7], ...}
    GET /tiles/live/Norder<k>/Dir<d>/Npix<p>[_<slice>].png -> PNG, or 404 if no SPHEREx image covers it
    GET /tiles/live-p<n>/Norder<k>/...                     -> the same from survey pass n's images only (T82)
    GET /cutout?url=<IRSA level-2 FITS URL>&ra=&dec=&size=<deg> -> gzip of the cutout FITS that
        pipeline.s3.fetch_cutout writes (T57: builds in Europe get ~200 kB instead of ~2-3 MB of rows);
        404 + `X-Cutout: off-image` if the field is not on that image. Cached in data/vm_cutouts/.

Rendered tiles are cached on disk (data/tilegen_cache/). Meant to run next to the AWS SPHEREx bucket
(us-east-1); the Live API asks it in remote mode (python -m server --tiles-remote <url>).
"""
from __future__ import annotations

import re
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from . import render

TILE_RE = re.compile(r"^Norder(\d+)/Dir(\d+)/Npix(\d+)(?:_(\d+))?\.png$")
MISSING = b"MISSING"
PASS_RE = re.compile(r"^p(\d+)/(.*)$")       # cache key of a pass tile: p<n>/Norder.../Npix....png


def parse_key(key: str):
    """Cache key -> (pass or None, TILE_RE match of the tile path, or None)."""
    pm = PASS_RE.match(key)
    return (int(pm.group(1)), TILE_RE.match(pm.group(2))) if pm else (None, TILE_RE.match(key))
VIA = "team-vm-us-east4"   # T57: in the cutout's header and the frame's source_url (#rows=...;via=...)


def create_app(cache_root: Path = Path("data/tilegen_cache"), slots: int = 6, prefetch: bool = True,
               cutout_slots: int = 24) -> FastAPI:
    app = FastAPI(title="SPHEREx tile generator", version="1")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])
    sem = threading.BoundedSemaphore(slots)
    inflight: dict[str, threading.Event] = {}
    lock = threading.Lock()
    stats = {"rendered": 0, "cached": 0, "seconds": 0.0, "prefetched": 0}
    busy = {"n": 0}
    # Background prefetch: newest asked tile first (LIFO), only while no request is being rendered,
    # one at a time, so it never slows down what users wait for.
    pending: list[str] = []
    wake = threading.Condition()

    def render_to_cache(path: str, m, pass_: int | None = None) -> None:
        f = cache_root / path
        t0 = time.time()
        args = (int(m.group(4) or 0), int(m.group(1)), int(m.group(3)))
        png = render.render(*args, pass_=pass_) if pass_ else render.render(*args)
        stats["seconds"] += time.time() - t0
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_name(f.name + f".{threading.get_ident()}.part")
        tmp.write_bytes(png if png is not None else MISSING)
        tmp.replace(f)

    def queue_neighbours(path: str, m, pass_: int | None = None) -> None:
        try:
            from astropy_healpix import HEALPix
            order, npix, sl = int(m.group(1)), int(m.group(3)), m.group(4)
            nb = HEALPix(nside=2 ** order, order="nested").neighbours(npix)
        except Exception:  # noqa: BLE001
            return
        with wake:
            for p in nb:
                if p < 0:
                    continue
                sub = f"Norder{order}/Dir{(int(p) // 10000) * 10000}/Npix{int(p)}{'_' + sl if sl else ''}.png"
                if pass_:
                    sub = f"p{pass_}/{sub}"
                if not (cache_root / sub).exists() and sub not in pending:
                    pending.append(sub)
            del pending[:-64]                                   # keep the newest 64
            wake.notify()

    def prefetcher() -> None:
        while True:
            with wake:
                while not pending or busy["n"] > 0:
                    wake.wait(1.0)
                path = pending.pop()
            if (cache_root / path).exists():
                continue
            with lock:
                if path in inflight:
                    continue
                ev = inflight[path] = threading.Event()
            try:
                pass_, m = parse_key(path)
                render_to_cache(path, m, pass_)
                stats["prefetched"] += 1
            except Exception:  # noqa: BLE001 - best effort
                pass
            finally:
                with lock:
                    inflight.pop(path, None)
                ev.set()

    if prefetch:
        threading.Thread(target=prefetcher, daemon=True, name="tilegen-prefetch").start()

    @app.get("/health")
    def health():
        n = stats["rendered"]
        return {"ok": True, "orders": list(render.LIVE_ORDERS), "images_per_tile": render.IMAGES_PER_TILE,
                "images_per_pass_tile": render.PASS_IMAGES,
                "passes": True,                                 # T82: /tiles/live-p<n>/ is served
                "rendered": n, "served_from_cache": stats["cached"], "prefetched": stats["prefetched"],
                "prefetch_pending": len(pending),
                "mean_render_s": round(stats["seconds"] / (n + stats["prefetched"]), 2) if n + stats["prefetched"] else None}

    @app.get("/tiles/live/{path:path}")
    def tile(path: str):
        return serve(path)

    @app.get("/tiles/live-p{pass_}/{path:path}")
    def pass_tile(pass_: int, path: str):
        if not 1 <= pass_ <= 20:
            raise HTTPException(404)
        return serve(f"p{pass_}/{path}")

    def serve(path: str):
        pass_, m = parse_key(path)
        if not m or int(m.group(1)) not in render.LIVE_ORDERS:
            raise HTTPException(404)
        f = cache_root / path
        if f.exists():
            stats["cached"] += 1
        else:
            with lock:
                ev = inflight.get(path)
                owner = ev is None
                if owner:
                    ev = inflight[path] = threading.Event()
            if owner:
                busy["n"] += 1
                try:
                    with sem:
                        render_to_cache(path, m, pass_)
                    stats["rendered"] += 1
                finally:
                    busy["n"] -= 1
                    with lock:
                        inflight.pop(path, None)
                    ev.set()
            else:
                ev.wait(300)                       # same tile already being rendered: wait for it
        if prefetch:
            queue_neighbours(path, m, pass_)
        if not f.exists():
            raise HTTPException(503, "render failed")
        data = f.read_bytes()
        if data == MISSING:
            return Response(status_code=404, headers={"Cache-Control": "public, max-age=86400"})
        return Response(data, media_type="image/png", headers={"Cache-Control": "public, max-age=604800, immutable"})

    # -- T57: cutouts for the Live API's builds (pipeline.s3.fetch_cutout_remote) ----------------
    cut_root = cache_root.parent / "vm_cutouts"
    cut_sem = threading.BoundedSemaphore(cutout_slots)
    cut_stats = {"cut": 0, "cached": 0, "seconds": 0.0}

    @app.get("/cutout")
    def cutout(url: str, ra: float, dec: float, size: float):
        """gzip of the cutout FITS (IMAGE, FLAGS, WCS-WAVE) that pipeline.s3.fetch_cutout writes."""
        import gzip
        import hashlib

        from pipeline import s3

        if s3.s3_url(url) is None or not url.endswith(".fits") or ".." in url:
            raise HTTPException(400, "url must be an IRSA SPHEREx level-2 image")
        # size: the cutout side the build asks for, field x 1.5 for rotation (5.26 deg at the API's 210')
        if not (0 < size <= 6.0) or not (-90 <= dec <= 90) or not (0 <= ra < 360):
            raise HTTPException(400, "bad ra/dec/size")
        key = hashlib.sha1(f"{url}|{ra:.7f}|{dec:.7f}|{size:.4f}".encode()).hexdigest()
        gz = cut_root / key[:2] / f"{key}.fits.gz"
        off = gz.with_suffix(".off")
        headers = {"Cache-Control": "public, max-age=604800, immutable"}
        if off.exists():
            return Response(status_code=404, headers={**headers, "X-Cutout": s3.OFF_IMAGE})
        if not gz.exists():
            t0 = time.time()
            tmp = cut_root / "tmp" / f"{key}.{threading.get_ident()}.fits"
            busy["n"] += 1                         # tile prefetch pauses while someone waits for this
            try:
                with cut_sem:
                    s3.fetch_cutout(url, ra, dec, size, tmp, via=VIA)
            except LookupError:
                off.parent.mkdir(parents=True, exist_ok=True)
                off.touch()
                return Response(status_code=404, headers={**headers, "X-Cutout": s3.OFF_IMAGE})
            except Exception as e:  # noqa: BLE001 - the client falls back / looks the path up
                if s3.is_not_found(e):
                    return Response(status_code=404, headers={"X-Cutout": s3.MISSING})
                return Response(f"S3 read failed: {e}"[:300], status_code=502, headers={"X-Cutout": s3.S3_ERROR})
            finally:
                busy["n"] -= 1
            gz.parent.mkdir(parents=True, exist_ok=True)
            part = gz.with_name(f"{gz.name}.{threading.get_ident()}.part")
            part.write_bytes(gzip.compress(tmp.read_bytes(), 5))
            part.replace(gz)
            tmp.unlink(missing_ok=True)
            cut_stats["cut"] += 1
            cut_stats["seconds"] += time.time() - t0
        else:
            cut_stats["cached"] += 1
        return Response(gz.read_bytes(), media_type="application/gzip", headers=headers)

    @app.get("/cutout/health")
    def cutout_health():
        n = cut_stats["cut"]
        return {"ok": True, "cut": n, "served_from_cache": cut_stats["cached"],
                "mean_cut_s": round(cut_stats["seconds"] / n, 2) if n else None}

    return app


def app_from_env() -> FastAPI:
    """uvicorn factory for several worker processes (python -m tilegen --workers n): settings from env.
    Each worker renders on its own (Python's GIL holds one process to ~1 CPU); the disk cache is shared."""
    import os
    return create_app(Path(os.environ.get("TILEGEN_CACHE", "data/tilegen_cache")), int(os.environ.get("TILEGEN_SLOTS", "6")))
