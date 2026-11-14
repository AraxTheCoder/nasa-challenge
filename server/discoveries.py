"""T76: the discovery index (CONTRACTS v0.13 "Discoveries").

    GET /api/discoveries                          every candidate, best score first
        ?class=brown_dwarf,variable               only these classes
        &ra=<deg>&dec=<deg>&radius=<deg>          only within radius of a position (all three or none)
        &min_score=0.5  &limit=50                 score floor, at most this many
        &random=1                                 one candidate picked at random (after the filters)

Reads the survey's index (data/survey/discoveries.json, written by pass 2, T75) or, until there is one, the
hand-made sample fixtures/discoveries-sample.json ("synthetic": true). Format: docs/discoveries.schema.json.
The file is re-read when it changes, so a new survey run shows up without a restart.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from .builder import REPO

router = APIRouter()
SURVEY_INDEX = REPO / "data" / "survey" / "discoveries.json"
SAMPLE_INDEX = REPO / "fixtures" / "discoveries-sample.json"
_cache: dict[Path, tuple[float, dict]] = {}


def index_path() -> Path:
    return SURVEY_INDEX if SURVEY_INDEX.is_file() else SAMPLE_INDEX


def load_index(path: Path | None = None) -> dict:
    path = path or index_path()
    mtime = path.stat().st_mtime
    hit = _cache.get(path)
    if hit and hit[0] == mtime:
        return hit[1]
    data = json.loads(path.read_text(encoding="utf-8"))
    _cache[path] = (mtime, data)
    return data


def sep_deg(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    c = math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(r1 - r2)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def select(index: dict, classes: set[str] | None = None, near: tuple[float, float, float] | None = None,
           min_score: float | None = None) -> list[dict]:
    """Candidates passing the filters, best score first (ties: by id, so the order is stable)."""
    out = []
    for c in index.get("candidates", []):
        if classes and c.get("class") not in classes:
            continue
        if min_score is not None and c.get("score", 0) < min_score:
            continue
        if near and sep_deg(near[0], near[1], c["ra_deg"], c["dec_deg"]) > near[2]:
            continue
        out.append(c)
    return sorted(out, key=lambda c: (-c.get("score", 0), c["id"]))


def _bad(message: str) -> JSONResponse:
    return JSONResponse({"status": "error", "message": message}, status_code=400)


@router.get("/api/discoveries")
def discoveries(cls: str | None = Query(None, alias="class"), ra: float | None = None, dec: float | None = None,
                radius: float | None = None, min_score: float | None = None, limit: int | None = None,
                pick: int = Query(0, alias="random")):
    near = None
    if (ra, dec, radius) != (None, None, None):
        if None in (ra, dec, radius):
            return _bad("ra, dec and radius go together")
        if not (0 <= ra < 360 and -90 <= dec <= 90 and 0 < radius <= 180):
            return _bad("ra must be in [0, 360), dec in [-90, 90], radius in (0, 180]")
        near = (ra, dec, radius)
    if limit is not None and limit < 1:
        return _bad("limit must be at least 1")
    path = index_path()
    try:
        index = load_index(path)
    except (OSError, ValueError) as e:
        return JSONResponse({"status": "error", "message": f"discovery index unreadable: {e}"}, status_code=500)
    classes = {c.strip() for c in cls.split(",") if c.strip()} if cls else None
    found = select(index, classes, near, min_score)
    if pick and found:
        found = [random.choice(found)]
    elif limit:
        found = found[:limit]
    head = {k: index.get(k) for k in ("synthetic", "survey", "description", "method", "generated_utc", "provenance")}
    source = str(path.relative_to(REPO)) if path.is_relative_to(REPO) else path.name
    return {"status": "ready", **head, "source": source,
            "total": len(index.get("candidates", [])), "count": len(found), "candidates": found}
