"""python -m tilegen [--host 127.0.0.1] [--port 8100] [--cache data/tilegen_cache] [--slots 6] [--workers 1]"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn

from .app import create_app


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m tilegen", description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8100)
    ap.add_argument("--cache", type=Path, default=Path("data/tilegen_cache"))
    ap.add_argument("--slots", type=int, default=6, help="tiles rendered at the same time (per worker)")
    ap.add_argument("--workers", type=int, default=1, help="processes (one CPU each: Python's GIL)")
    args = ap.parse_args()
    # T94: caps on the disk caches (a full disk failed every new tile); one janitor per service (the parent)
    from . import janitor
    gb = lambda name, default: float(os.environ.get(name, default)) * 1e9   # noqa: E731
    janitor.start([(Path("data/raw/s3chunks"), gb("TILEGEN_CHUNK_CACHE_GB", 8)),
                   (args.cache.parent / "vm_cutouts", gb("TILEGEN_CUTOUT_CACHE_GB", 4)),
                   (args.cache, gb("TILEGEN_TILE_CACHE_GB", 4))], keep_free=gb("TILEGEN_KEEP_FREE_GB", 3))
    if args.workers > 1:
        os.environ["TILEGEN_CACHE"], os.environ["TILEGEN_SLOTS"] = str(args.cache), str(args.slots)
        uvicorn.run("tilegen.app:app_from_env", factory=True, workers=args.workers, host=args.host, port=args.port)
    else:
        uvicorn.run(create_app(args.cache, args.slots), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
