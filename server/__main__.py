"""python -m server [--host 127.0.0.1] [--port 8000] [--fixture] [--cache data/targets]"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn

from .app import create_app
from .builder import REPO


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m server", description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--fixture", action="store_true",
                    help="answer every request with the synthetic fixture (until pipeline.build exists)")
    ap.add_argument("--cache", type=Path, default=REPO / "data" / "targets")
    ap.add_argument("--tiles-remote", default=os.environ.get("SPHEREX_TILES_REMOTE"),
                    help="URL of a tilegen service, e.g. the US VM next to the S3 bucket "
                         "(default: $SPHEREX_TILES_REMOTE)")
    ap.add_argument("--use-remote", action="store_true", help="start with the remote tile generator")
    args = ap.parse_args()
    uvicorn.run(create_app(args.cache, fixture=args.fixture, tiles_remote=args.tiles_remote,
                           use_remote=args.use_remote), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
