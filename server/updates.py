"""T64: newer SPHEREx data for a built field (CONTRACTS v0.15 "Newer data").

    GET /api/targets/<id>/updates

Compares what SPHEREx had at the field centre when the field was built (target.json `source_exposures`)
with the exposure list now, and lists release folders in the bucket this tool didn't know (pipeline.releases) (`pipeline.build.cached_exposures`: the local image index if there is one, else
IRSA TAP cached for up to a day). Newer images = exposures after the latest one known at build time. Fields
built before T64 have no `source_exposures`: then only exposures more than a survey-pass gap (30 days) after
the last frame count, since frames are a selection and later exposures of the last pass may simply not have
been picked. The viewer offers Rebuild (`/api/target?...&refresh=1`) when there are newer images.
"""
from __future__ import annotations

import json
import re

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

router = APIRouter()
_ID = re.compile(r"^[a-z0-9-]+$")
PASS_GAP_DAYS = 30.0    # = pipeline.query.EPOCH_GAP_DAYS: a new survey pass


def _base(collection: str) -> str:
    return collection.removeprefix("spherex_").split("_")[0]


def _from_url(url: str | None) -> str | None:
    """Fields built before T64: the release folder in the frame's source_url (.../qr3/level2/...)."""
    m = re.search(r"/(dr\d+|qr\d*)/level2/", url or "")
    return f"spherex_{m.group(1)}" if m else None


def checked_label(prov: dict | None) -> str:
    """'the local SPHEREx index (harvested 2026-11-14)' or 'IRSA (2026-11-14)'."""
    prov = prov or {}
    when = (prov.get("retrieved_utc") or "")[:10] or "date unknown"
    if "local mirror" in prov.get("service", ""):
        return f"the local SPHEREx image index (harvested {when})"
    return f"IRSA ({when})"


def compare(target: dict, exposures: list, prov: dict | None, bucket: dict | None = None) -> dict:
    """Pure: target.json + the exposure list now (+ the bucket's release folders, pipeline.releases) -> the
    answer body (without status/id)."""
    from pipeline.releases import new_releases
    from pipeline.build import exposure_summary, release_name
    frames = target.get("frames", [])
    built = target.get("source_exposures")
    if built and built.get("latest_mjd") is not None:
        basis, since = "build", built["latest_mjd"] + 1e-4
        built_cols = set(built.get("collections") or [])
    else:
        basis = "frames"
        since = max((f["mjd"] for f in frames), default=0.0) + PASS_GAP_DAYS
        built_cols = {f.get("collection") or _from_url(f.get("source_url")) for f in frames} - {None}
    newer = sorted((e for e in exposures if e.mjd_mid > since), key=lambda e: e.mjd_mid)
    now = exposure_summary(exposures, prov)
    built_epochs = {f.get("epoch") for f in frames}
    new_passes = len({e.epoch for e in newer} - built_epochs)
    built_rels = {_base(c) for c in built_cols}            # deep or not: the same release
    new_cols = sorted({e.collection for e in newer if _base(e.collection) not in built_rels}) if built_cols else []
    names = lambda cols: sorted({release_name(c).split()[0] for c in cols if c})  # noqa: E731 - "DR1", "QR3"
    if newer:
        span = newer[0].time_utc[:10] + ("" if newer[-1].time_utc[:10] == newer[0].time_utc[:10] else f" to {newer[-1].time_utc[:10]}")
        extra = [f"{new_passes} new survey pass{'es' if new_passes > 1 else ''}" if new_passes else None,
                 f"new release {', '.join(names(new_cols))}" if new_cols else None]
        message = (f"{len(newer)} newer SPHEREx image{'s' if len(newer) > 1 else ''} here ({span}"
                   + "".join(f"; {x}" for x in extra if x) + "). Rebuild to include them.")
    else:
        message = "Up to date: no newer SPHEREx images here."
    published = sorted((bucket or {}).get("releases") or [])
    fresh = [r.upper() for r in new_releases(published)]
    release_note = None
    if fresh:
        missing = [r for r in fresh if r not in names(now["collections"])]
        release_note = (f"SPHEREx has published {', '.join(fresh)} since this tool was written; it is searched from now on"
                        + ("" if not missing or "local mirror" not in (prov or {}).get("service", "") else
                           ", but the local image index predates it: re-harvest the index (pipeline.mirror) to see it here")
                        + ".")
    return {"basis": basis, "built": built, "now": now, "newer_images": len(newer),
            "newer_from_utc": newer[0].time_utc if newer else None, "newer_to_utc": newer[-1].time_utc if newer else None,
            "new_passes": new_passes, "new_collections": new_cols,
            "releases_built": names(built_cols), "releases_now": names(now["collections"]),
            "releases_published": [r.upper() for r in published], "new_releases": fresh, "release_note": release_note,
            "checked": prov, "checked_label": checked_label(prov), "message": message}


def _check(path_str: str) -> dict:
    from pipeline.build import cached_exposures
    from pipeline.releases import bucket_releases
    target = json.loads(open(path_str, encoding="utf-8").read())
    c = target["center"]
    exposures, prov = cached_exposures(c["ra_deg"], c["dec_deg"])
    return compare(target, exposures, prov, bucket_releases())


@router.get("/api/targets/{tid}/updates")
async def updates(tid: str, request: Request):
    path = request.app.state.builder.target_dir(tid) / "target.json" if _ID.match(tid) else None
    if path is None or not path.is_file():
        return JSONResponse({"status": "error", "message": "target not built"}, status_code=404)
    target = json.loads(path.read_text(encoding="utf-8"))
    if target.get("synthetic"):
        return {"status": "no_data", "id": tid, "message": "synthetic target: no SPHEREx data releases"}
    try:
        body = await run_in_threadpool(_check, str(path))
    except Exception as e:  # noqa: BLE001 - IRSA down etc.: say so, the field itself is fine
        return JSONResponse({"status": "error", "id": tid, "message": f"could not check for newer data: {e}"}, status_code=502)
    return {"status": "ready", "id": tid, **body}
