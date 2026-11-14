"""T64: which SPHEREx data releases exist, so a new one (QR4, DR2, ...) is searched without a code change.

The image search (pipeline.query, pipeline.mirror) used to ask IRSA for four fixed collections, so a new
release would never have shown up. Asking IRSA's ObsCore which collections exist scans the whole table
(> 5 min on 2026-11-14), but the public bucket lists one folder per release at its top level, in one request
(< 1 s): dr1/, qr2/, qr3/ on 2026-11-14. Cached for a day in data/raw/releases.json.

- collections(): the collections to search: the ones in use so far plus spherex_<rel> and spherex_<rel>_deep
  for every release folder that is new (not in KNOWN). qr and qr2 are earlier quick releases that were never
  searched (their data are in DR1), so they stay out.
- dedupe(): if two releases hold the same exposure (a data release reprocessing a quick release), keep one:
  a data release (DR) over a quick release (QR), then the higher number.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

BUCKET = "https://nasa-irsa-spherex.s3.amazonaws.com/"
CACHE = Path("data/raw/releases.json")
TTL_S = 24 * 3600
IN_USE = ("spherex_dr1", "spherex_dr1_deep", "spherex_qr3", "spherex_qr3_deep")   # searched before T64
KNOWN = {"qr", "qr2", "dr1", "qr3"}                                                  # bucket folders on 2026-11-14
_REL = re.compile(r"^(dr|qr)(\d*)$")


def _list_bucket() -> list[str]:
    import requests
    r = requests.get(BUCKET, params={"list-type": "2", "delimiter": "/"}, timeout=(5, 20))
    r.raise_for_status()
    return sorted(p.rstrip("/") for p in re.findall(r"<Prefix>([^<]+/)</Prefix>", r.text) if _REL.match(p.rstrip("/")))


def bucket_releases(cache: Path = CACHE, refresh: bool = False) -> dict:
    """{"releases": ["dr1", "qr2", "qr3"], "retrieved_utc": ...} from the bucket, cached for a day. If the bucket
    can't be reached: the last cached answer (even if old), else the known folders with "retrieved_utc": None."""
    old = None
    if cache.is_file():
        try:
            old = json.loads(cache.read_text(encoding="utf-8"))
        except ValueError:
            old = None
    if old and not refresh and time.time() - cache.stat().st_mtime < TTL_S:
        return old
    try:
        found = {"releases": _list_bucket(), "retrieved_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "source": f"{BUCKET}?list-type=2&delimiter=/"}
    except Exception:  # noqa: BLE001 - no network: keep searching what we know
        return old or {"releases": sorted(KNOWN), "retrieved_utc": None, "source": "built-in list (bucket not reachable)"}
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(found), encoding="utf-8")
    except OSError:
        pass
    return found


def new_releases(releases: list[str]) -> list[str]:
    return [r for r in releases if r not in KNOWN]


def collections(releases: list[str] | None = None) -> tuple[str, ...]:
    """Collections to search: IN_USE + spherex_<rel>[_deep] for each new release folder."""
    rels = bucket_releases()["releases"] if releases is None else releases
    extra = [c for r in new_releases(rels) for c in (f"spherex_{r}", f"spherex_{r}_deep")]
    return IN_USE + tuple(c for c in extra if c not in IN_USE)


def rank(collection: str) -> tuple[int, int]:
    """spherex_dr2 > spherex_dr1 > spherex_qr4 > spherex_qr3 (deep or not doesn't matter)."""
    m = _REL.match(collection.removeprefix("spherex_").split("_")[0])
    if not m:
        return (-1, -1)
    return (1 if m.group(1) == "dr" else 0, int(m.group(2) or 0))


def dedupe(exposures: list) -> list:
    """One exposure per (obs_id, detector), from the best release (rank); order kept."""
    best: dict[tuple[str, int], object] = {}
    for e in exposures:
        k = (e.obs_id, e.detector)
        if k not in best or rank(e.collection) > rank(best[k].collection):
            best[k] = e
    keep = {id(e) for e in best.values()}
    return [e for e in exposures if id(e) in keep]
