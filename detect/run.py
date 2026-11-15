"""T51: the detect step every Live API build runs (`server/builder.py` calls `detect(target_dir)`).

    python -m detect.run data/targets/<id>        # updates target.json in place

1. Mover detection (T06, `detect.movers`): finds tracks in the field's cached SPHEREx images -> `detections`.
2. JPL known objects (T07): catalogued asteroids and comets in the field -> `known_objects`.
3. Classification (T08): known / unknown / artifact per detection; only when there are detections.

Without cached SPHEREx images (old or copied fields) the mover search is skipped and no provenance entry
is named "detect", so the viewer keeps saying "Mover detection has not run" and lists the known objects as
catalogued, not as missed detections. A failed mover search or JPL
lookup never fails the build: `known_objects` stays empty and the error goes into provenance.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .classify import classify_detections
from .known_objects import DEFAULT_VMAG, Jpl, add_known_objects
from .movers import find_movers


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def detect_target(target: dict, jpl: Jpl | None = None, vmag_lim: float = DEFAULT_VMAG, movers: bool = True) -> dict:
    """Run the detect steps on a target dict in place. Returns the target.
    movers=False (T106): known objects only, e.g. on a build's stub before any image is downloaded; the mover
    search then runs when the viewer asks for the field's objects."""
    if target.get("synthetic"):
        return target  # the fixture already carries its synthetic objects

    try:                                             # 1. T06: tracks from the field's SPHEREx images
        if movers:
            find_movers(target)
    except Exception as e:  # noqa: BLE001 - detection is an extra: the field is still worth showing
        target["detections"] = []
        target.setdefault("provenance", []).append({
            "service": "mover search (T06) failed", "query": f"{type(e).__name__}: {e}"[:500], "retrieved_utc": _now()})

    try:
        add_known_objects(target, jpl, vmag_lim)
    except Exception as e:  # noqa: BLE001 - JPL down or changed: the field is still worth showing
        target["known_objects"] = []
        target.setdefault("provenance", []).append({
            "service": "JPL known objects (T07) failed",
            "query": f"{type(e).__name__}: {e}"[:500],
            "retrieved_utc": _now(),
        })

    if target.get("detections"):
        classify_detections(target)
    return target


def detect(target_dir: str | Path, jpl: Jpl | None = None, vmag_lim: float = DEFAULT_VMAG) -> Path:
    """Run the detect steps on `<target_dir>/target.json` and write it back. Returns target_dir."""
    path = Path(target_dir) / "target.json"
    target = json.loads(path.read_text(encoding="utf-8"))
    detect_target(target, jpl, vmag_lim)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(target, indent=2), encoding="utf-8")
    tmp.replace(path)
    return Path(target_dir)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m detect.run", description=__doc__.split("\n\n")[0])
    ap.add_argument("target_dir", type=Path)
    ap.add_argument("--vmag", type=float, default=DEFAULT_VMAG, help="faintest V magnitude to look for")
    args = ap.parse_args(argv)
    detect(args.target_dir, vmag_lim=args.vmag)
    t = json.loads((args.target_dir / "target.json").read_text(encoding="utf-8"))
    print(f"{len(t.get('known_objects', []))} known object(s), {len(t.get('detections', []))} detection(s)")
    for o in t.get("known_objects", []):
        print(f"  {o['name']:<36} {len(o['positions'])} frame(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
