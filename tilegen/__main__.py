"""python -m tilegen [--host 127.0.0.1] [--port 8100] [--cache data/tilegen_cache] [--slots 6]"""
from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from .app import create_app


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m tilegen", description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8100)
    ap.add_argument("--cache", type=Path, default=Path("data/tilegen_cache"))
    ap.add_argument("--slots", type=int, default=6, help="tiles rendered at the same time")
    args = ap.parse_args()
    uvicorn.run(create_app(args.cache, args.slots), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
