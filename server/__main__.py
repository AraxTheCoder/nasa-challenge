"""python -m server [--host 127.0.0.1] [--port 8000] [--fixture] [--cache data/targets]"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn

from .app import create_app
from .builder import REPO


# The team's tile generator on Google Cloud us-east4 (T47, deploy/README.md).
TEAM_TILEGEN = "https://136-107-125-170.sslip.io"


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m server", description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--fixture", action="store_true",
                    help="answer every request with the synthetic fixture (until pipeline.build exists)")
    ap.add_argument("--cache", type=Path, default=REPO / "data" / "targets")
    ap.add_argument("--tiles-remote", default=os.environ.get("SPHEREX_TILES_REMOTE", TEAM_TILEGEN),
                    help="URL of a tilegen service, e.g. the US VM next to the S3 bucket "
                         f"(default: $SPHEREX_TILES_REMOTE or {TEAM_TILEGEN}; 'none' to disable). "
                         "In local mode it also stands in while the local index is being built.")
    ap.add_argument("--use-remote", action="store_true",
                    help="start with the remote tile generator only (default with a remote: balanced, T55)")
    ap.add_argument("--cutouts-remote", default=os.environ.get("SPHEREX_CUTOUTS_REMOTE", TEAM_TILEGEN),
                    help="tilegen service that cuts the SPHEREx images for builds next to the bucket (T57; "
                         f"default: $SPHEREX_CUTOUTS_REMOTE or {TEAM_TILEGEN}; 'none' = read S3 directly)")
    ap.add_argument("--public", action="store_true", default=os.environ.get("SPHEREX_PUBLIC") == "1",
                    help="T58: limits for a public server (per-IP rates, job cap, admin token for refresh/settings, "
                         "cache cap); also $SPHEREX_PUBLIC=1. Admin token: $SPHEREX_ADMIN_TOKEN")
    ap.add_argument("--cache-gb", type=float, default=None,
                    help="keep the field / cutout / tile-chunk / spectra caches under this size by evicting the least "
                         "recently used (T58, T97). Default: $SPHEREX_CACHE_GB, else 20 with --public, else no cap")
    ap.add_argument("--max-jobs", type=int, default=int(os.environ.get("SPHEREX_MAX_JOBS", 4)),
                    help="with --public: expensive jobs (builds, spectra) running at once on the server (default 4)")
    ap.add_argument("--trust-proxy", action="store_true",
                    help="with --public: client IP from X-Forwarded-For (only behind your own reverse proxy)")
    ap.add_argument("--no-data-setup", action="store_true",
                    help="don't fetch/build the orbit catalogue and image index in the background (T71)")
    args = ap.parse_args()
    if str(args.tiles_remote).lower() in ("none", ""):
        args.tiles_remote = None
    if str(args.cutouts_remote).lower() in ("none", ""):
        args.cutouts_remote = None
    from . import limits
    if args.cache_gb is None:
        env = os.environ.get("SPHEREX_CACHE_GB")
        args.cache_gb = float(env) if env else (20.0 if args.public else 0.0)
    limits.configure(args.public, cache_gb=args.cache_gb, max_active=args.max_jobs, trust_proxy=args.trust_proxy)
    if args.cache_gb and not args.public:
        print(f"cache cap {args.cache_gb:g} GB (least recently used evicted)", flush=True)
    if args.public:
        print(f"public mode: per-IP limits, {args.max_jobs} jobs at once, cache cap {args.cache_gb:g} GB, "
              f"admin token {'set' if limits.CFG.token else 'NOT set (refresh and settings disabled)'}", flush=True)
    if not args.fixture and not args.no_data_setup:
        from . import data_setup
        data_setup.start(REPO / "data")     # T71: background; the fallbacks serve until it is done
    if not args.fixture:   # T94: caps on the local disk caches (row chunks for local tiles, map tiles)
        from tilegen import janitor
        gb = lambda name, default: float(os.environ.get(name, default)) * 1e9   # noqa: E731
        janitor.start([(REPO / "data" / "raw" / "s3chunks", gb("SPHEREX_CHUNK_CACHE_GB", 10)),
                       (REPO / "data" / "hips_cache", gb("SPHEREX_TILE_CACHE_GB", 10))],
                      keep_free=gb("SPHEREX_KEEP_FREE_GB", 5))
    uvicorn.run(create_app(args.cache, fixture=args.fixture, tiles_remote=args.tiles_remote,
                           use_remote=args.use_remote, cutouts_remote=args.cutouts_remote),
                host=args.host, port=args.port)


if __name__ == "__main__":
    main()
