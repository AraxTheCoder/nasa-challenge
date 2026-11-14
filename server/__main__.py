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
    ap.add_argument("--use-remote", action="store_true", help="start with the remote tile generator")
    ap.add_argument("--no-data-setup", action="store_true",
                    help="don't fetch/build the orbit catalogue and image index in the background (T71)")
    args = ap.parse_args()
    if str(args.tiles_remote).lower() in ("none", ""):
        args.tiles_remote = None
    if not args.fixture and not args.no_data_setup:
        from . import data_setup
        data_setup.start(REPO / "data")     # T71: background; the fallbacks serve until it is done
    uvicorn.run(create_app(args.cache, fixture=args.fixture, tiles_remote=args.tiles_remote,
                           use_remote=args.use_remote), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
