"""tilegen service: `python -m tilegen [--host 127.0.0.1] [--port 8100]`.

    GET /health                                            -> {"ok": true, "orders": [6, 7], ...}
    GET /tiles/live/Norder<k>/Dir<d>/Npix<p>[_<slice>].png -> PNG, or 404 if no SPHEREx image covers it

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


def create_app(cache_root: Path = Path("data/tilegen_cache"), slots: int = 6, prefetch: bool = True) -> FastAPI:
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

    def render_to_cache(path: str, m) -> None:
        f = cache_root / path
        t0 = time.time()
        png = render.render(int(m.group(4) or 0), int(m.group(1)), int(m.group(3)))
        stats["seconds"] += time.time() - t0
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_name(f.name + f".{threading.get_ident()}.part")
        tmp.write_bytes(png if png is not None else MISSING)
        tmp.replace(f)

    def queue_neighbours(path: str, m) -> None:
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
                render_to_cache(path, TILE_RE.match(path))
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
                "rendered": n, "served_from_cache": stats["cached"], "prefetched": stats["prefetched"],
                "prefetch_pending": len(pending),
                "mean_render_s": round(stats["seconds"] / n, 2) if n else None}

    @app.get("/tiles/live/{path:path}")
    def tile(path: str):
        m = TILE_RE.match(path)
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
                        render_to_cache(path, m)
                    stats["rendered"] += 1
                finally:
                    busy["n"] -= 1
                    with lock:
                        inflight.pop(path, None)
                    ev.set()
            else:
                ev.wait(300)                       # same tile already being rendered: wait for it
        if prefetch:
            queue_neighbours(path, m)
        if not f.exists():
            raise HTTPException(503, "render failed")
        data = f.read_bytes()
        if data == MISSING:
            return Response(status_code=404, headers={"Cache-Control": "public, max-age=86400"})
        return Response(data, media_type="image/png", headers={"Cache-Control": "public, max-age=604800, immutable"})

    return app
