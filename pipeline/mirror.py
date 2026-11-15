"""T31: local mirror of the SPHEREx image index, so a position search takes milliseconds, not 10-20 s.

    python -m pipeline.mirror harvest      # full-table async TAP jobs -> data/mirror/*.csv (minutes)
    python -m pipeline.mirror build        # csv -> data/mirror/index.npz (+ footprints)
    python -m pipeline.mirror find --ra 269.4463 --dec 4.7682

Filtering by time is not indexed at IRSA (one day of rows took 119 s), but a full scan is fast, so
we pull the whole ObsCore table in async jobs, one per detector, with only the columns we need.
IRSA streams results slowly under load (~36 KB/s on 2026-11-14) and has no HTTP Range, so the
footprint polygon (~200 B/row) is left out: an image counts as covering a position when its centre
is within FOOTPRINT_RADIUS_DEG (the inscribed circle of the 3.5 deg square; corners are skipped).
FITS paths are derived from the per-week processing version learnt from a small sample of
artifact URIs; unknown weeks are resolved with one TAP query per build (`resolve_urls`).
`find_exposures_local` returns the same `Exposure` list as `pipeline.query.find_exposures`.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .query import IRSA_ROOT, TAP_URL, Exposure, assign_epochs

MIRROR = Path("data/mirror")
FOOTPRINT_RADIUS_DEG = 1.74


def jobs() -> dict[str, str]:
    """ObsCore per detector, for every release in use, new ones included (T64: pipeline.releases)."""
    from .releases import collections
    cols = "'" + "', '".join(collections()) + "'"
    return {f"obscore_d{d}": f"""SELECT obs_id, obs_collection, t_min, t_max, t_exptime, em_min, em_max,
        s_ra, s_dec FROM spherex.obscore WHERE obs_collection IN ({cols})
        AND dataproduct_type = 'image' AND energy_bandpassname = 'SPHEREx-D{d}'""" for d in range(1, 7)}
# A sample of FITS paths (one per week folder is enough) to learn the processing version per week.
# One FITS path per week folder (first exposure of each), so most paths can be derived offline.
URI_WEEKS = """SELECT a.uri FROM spherex.artifact AS a WHERE a.producttype = 'science'
        AND a.uri LIKE '%_0001_1D1_spx_%'"""
URI_SAMPLE = """SELECT TOP 20000 a.uri FROM spherex.artifact AS a WHERE a.producttype = 'science'
        AND a.uri LIKE '%D1_spx_%'"""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# -- harvest ---------------------------------------------------------------------------------------

def run_async(adql: str, dest: Path, poll_s: float = 10, tries: int = 6) -> None:
    """Run (or reuse) an async TAP job and download its CSV, restarting on dropped connections."""
    import requests

    if dest.exists():
        print(f"{dest.name}: already there", flush=True)
        return
    adql = " ".join(adql.split())
    jobfile = dest.with_suffix(".job")
    job = jobfile.read_text().strip() if jobfile.exists() else None
    if job and requests.get(f"{job}/phase", timeout=60).text.strip() in ("ERROR", "ABORTED", ""):
        job = None
    if not job:
        job = _submit(adql)
        jobfile.write_text(job)
    print(f"{dest.name}: job {job}", flush=True)
    t0 = time.time()
    while True:
        phase = requests.get(f"{job}/phase", timeout=60).text.strip()
        if phase in ("COMPLETED", "ERROR", "ABORTED"):
            break
        print(f"{dest.name}: {phase} {time.time() - t0:.0f}s", flush=True)
        time.sleep(poll_s)
    if phase != "COMPLETED":
        raise RuntimeError(f"{dest.name}: {phase}: {requests.get(f'{job}/error', timeout=60).text[:300]}")
    tmp = dest.with_suffix(".part")
    for attempt in range(tries):
        try:
            with requests.get(f"{job}/results/result", stream=True, timeout=600) as res:
                res.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in res.iter_content(1 << 20):
                        f.write(chunk)
            break
        except requests.RequestException as e:
            print(f"{dest.name}: download broke ({e.__class__.__name__}), retry {attempt + 1}", flush=True)
            time.sleep(10)
    else:
        raise RuntimeError(f"{dest.name}: download failed {tries} times")
    tmp.replace(dest)
    (dest.with_suffix(".prov.json")).write_text(json.dumps(
        {"service": f"IRSA TAP async {TAP_URL}", "query": adql, "retrieved_utc": _now()}), encoding="utf-8")
    print(f"{dest.name}: done in {time.time() - t0:.0f}s, {dest.stat().st_size >> 20} MB", flush=True)


def _submit(adql: str) -> str:
    import requests

    r = requests.post(f"{TAP_URL}/async", data={"REQUEST": "doQuery", "LANG": "ADQL", "QUERY": adql,
                                                "FORMAT": "csv", "RESPONSEFORMAT": "csv",
                                                "MAXREC": 5_000_000, "PHASE": "RUN"},
                      timeout=120, allow_redirects=False)
    if r.status_code not in (200, 303) or not r.headers.get("Location"):
        raise RuntimeError(f"submit failed: HTTP {r.status_code} {r.text[:200]}")
    return r.headers["Location"]


def harvest(root: Path = MIRROR) -> None:
    from concurrent.futures import ThreadPoolExecutor

    root.mkdir(parents=True, exist_ok=True)
    jobs_ = dict(jobs(), uri_sample=URI_SAMPLE, uri_weeks=URI_WEEKS)
    with ThreadPoolExecutor(len(jobs_)) as pool:
        futs = {pool.submit(run_async, q, root / f"{name}.csv"): name for name, q in jobs_.items()}
        failed = []
        for f, name in futs.items():
            try:
                f.result()
            except Exception as e:  # noqa: BLE001 - keep the other partitions
                failed.append(f"{name}: {e}")
    if failed:
        raise RuntimeError("; ".join(failed))


# -- build -----------------------------------------------------------------------------------------

URI_RE = re.compile(r"ibe/data/spherex/(\w+)/level2/(\w+)/([\w.-]+)/\d/level2_")


def learn_versions(root: Path = MIRROR) -> dict[str, str]:
    """(release, week folder) -> processing version, from any FITS paths we have seen."""
    versions = {}
    files = sorted(root.glob("uri*.csv")) + sorted((root.parent / "raw" / "exposures").glob("*.json"))
    for f in files:
        with open(f, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = URI_RE.search(line)
                if m:
                    versions[f"{m.group(1)}/{m.group(2)}"] = m.group(3)
    return versions


def derive_url(collection: str, obs_id: str, detector: int, versions: dict[str, str]) -> str | None:
    rel = collection.split("_")[1]                      # spherex_dr1_deep -> dr1
    week = obs_id.rsplit("_", 2)[0]                     # 2025W35_1A_0432_4 -> 2025W35_1A
    ver = versions.get(f"{rel}/{week}")
    if not ver:
        return None
    return (f"{IRSA_ROOT}ibe/data/spherex/{rel}/level2/{week}/{ver}/{detector}/"
            f"level2_{obs_id}D{detector}_spx_{ver}.fits")


def build(root: Path = MIRROR, learn_weeks: bool = True) -> Path:
    cols = {k: [] for k in ("obs_id", "collection", "detector", "t_min", "t_max", "exptime",
                            "em_min", "em_max", "s_ra", "s_dec")}
    for d in range(1, 7):
        with open(root / f"obscore_d{d}.csv", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    vals = [float(row[k]) for k in ("t_min", "t_max", "t_exptime", "em_min", "em_max", "s_ra", "s_dec")]
                except (ValueError, KeyError):
                    continue
                cols["obs_id"].append(row["obs_id"])
                cols["collection"].append(row["obs_collection"])
                cols["detector"].append(d)
                for k, v in zip(("t_min", "t_max", "exptime", "em_min", "em_max", "s_ra", "s_dec"), vals):
                    cols[k].append(v)
    out = root / "index.npz"
    prov = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(root.glob("obscore_d*.prov.json"))]
    tmp = root / "index.npz.part"            # T102: never a half-written index.npz under its final name
    with open(tmp, "wb") as fh:
        np.savez_compressed(
            fh, obs_id=np.array(cols["obs_id"]), collection=np.array(cols["collection"]),
            detector=np.array(cols["detector"], np.int8),
            **{k: np.array(cols[k]) for k in ("t_min", "t_max", "exptime", "em_min", "em_max", "s_ra", "s_dec")},
            provenance=np.array(json.dumps(prov)))
    tmp.replace(out)
    if learn_weeks:
        learn_all_weeks(root, cols)
    print(f"wrote {out}: {len(cols['obs_id'])} images, {len(learn_versions(root))} week folders with known paths")
    return out


def learn_weeks_from_bucket(images, index) -> int:
    """T57: processing versions of unknown week folders from a bucket listing (~0.6 s per week, in
    parallel) instead of TAP (20-145 s per build on 2026-11-14). `images`: (collection, obs_id, detector)
    of images whose week is unknown. Learnt weeks go to index.versions and uri_learned.csv (one
    example path per week, the format learn_versions reads). Returns how many weeks were learnt."""
    from concurrent.futures import ThreadPoolExecutor

    from . import s3
    weeks = {}
    for coll, obs, det in images:
        weeks.setdefault((coll.split("_")[1], obs.rsplit("_", 2)[0]), (obs, det))

    def ask(key):
        try:
            return key, s3.week_version(*key)
        except Exception:  # noqa: BLE001 - TAP is the fallback
            return key, None
    with ThreadPoolExecutor(min(8, len(weeks)) or 1) as pool:
        found = [(k, v) for k, v in pool.map(ask, weeks) if v]
    if found:
        with open(index.path.parent / "uri_learned.csv", "a", encoding="utf-8") as fh:
            for (rel, week), ver in found:
                index.versions[f"{rel}/{week}"] = ver
                obs, det = weeks[(rel, week)]
                fh.write(f"{IRSA_ROOT}ibe/data/spherex/{rel}/level2/{week}/{ver}/{det}/"
                         f"level2_{obs}D{det}_spx_{ver}.fits\n")
    return len(found)


def learn_all_weeks(root: Path = MIRROR, cols: dict | None = None) -> int:
    """Resolve one image per week folder whose processing version we don't know yet (one TAP call
    per 500), so map tiles never wait for TAP (~10 s each on 2026-11-14). Returns weeks learnt."""
    versions = learn_versions(root)
    if cols is None:
        z = np.load(root / "index.npz", allow_pickle=False)
        cols = {"obs_id": z["obs_id"].tolist(), "collection": z["collection"].tolist(), "detector": z["detector"].tolist()}
    todo = {}
    for obs, coll, det in zip(cols["obs_id"], cols["collection"], cols["detector"]):
        key = f"{coll.split('_')[1]}/{obs.rsplit('_', 2)[0]}"
        if key not in versions and key not in todo:
            todo[key] = f"ivo://irsa.ipac/{coll}?{obs}/D{det}"
    if not todo:
        return 0
    found = resolve_urls(list(todo.values()))
    with open(root / "uri_learned.csv", "a", encoding="utf-8") as fh:
        for url in found.values():
            fh.write(url + "\n")
    print(f"learnt the processing version of {len(found)} of {len(todo)} more week folders")
    return len(found)


# -- lookup ----------------------------------------------------------------------------------------

class Index:
    """The mirror in memory (~1.6 M rows, ~60 MB). A search is one matrix-vector product."""

    def __init__(self, path: Path = MIRROR / "index.npz"):
        z = np.load(path, allow_pickle=False)
        self.d = {k: z[k] for k in z.files}
        self.provenance = json.loads(str(self.d.pop("provenance")))
        ra, dec = np.radians(self.d["s_ra"]), np.radians(self.d["s_dec"])
        self.xyz = np.stack([np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)], 1).astype(np.float32)
        self.versions = learn_versions(path.parent)
        self.path = path

    def covering(self, ra_deg: float, dec_deg: float, radius_deg: float = FOOTPRINT_RADIUS_DEG) -> np.ndarray:
        ra, dec = np.radians(ra_deg), np.radians(dec_deg)
        p = np.array([np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)], np.float32)
        return np.nonzero(self.xyz @ p > np.cos(np.radians(radius_deg)))[0]


def resolve_urls(dids: list[str]) -> dict[str, str]:
    """FITS paths for images whose week we haven't seen yet: one TAP query (same as pipeline.query)."""
    from .query import URI_BATCH, URI_QUERY_TEMPLATE
    import pyvo

    tap = pyvo.dal.TAPService(TAP_URL)
    out = {}
    for i in range(0, len(dids), URI_BATCH):
        inlist = ", ".join(f"'{d}'" for d in dids[i:i + URI_BATCH])
        for r in tap.run_sync(" ".join(URI_QUERY_TEMPLATE.format(dids=inlist).split()), maxrec=100000):
            out[str(r["obs_publisher_did"])] = IRSA_ROOT + str(r["uri"]).lstrip("/")
    return out


_INDEX: Index | None = None


_checked: dict = {}


def available(root: Path = MIRROR) -> bool:
    """The index is there and complete. T102: a cut-off file (written by an older version while the server was
    stopped, or on a full disk) is put aside as index.npz.broken, so it is built again instead of failing
    every request for good."""
    import zipfile

    path = root / "index.npz"
    try:
        stamp = (path.stat().st_mtime_ns, path.stat().st_size)
    except OSError:
        return False
    if _checked.get(str(path)) == stamp:
        return True
    if zipfile.is_zipfile(path):
        _checked[str(path)] = stamp
        return True
    print(f"pipeline.mirror: {path} is cut off or damaged, putting it aside and building it again", flush=True)
    try:
        path.replace(path.with_name("index.npz.broken"))
    except OSError:
        pass
    return False


class IndexNotReady(RuntimeError):
    """The local index (data/mirror/index.npz, gitignored) is missing and is being built."""


_building: dict = {"thread": None, "error": None}
_building_lock = threading.Lock()


def ensure_background(root: Path = MIRROR) -> str:
    """Make sure the local index exists: start harvest + build once in a background thread if it
    doesn't (~3 min, IRSA TAP). Returns "ready", "building" or "failed: <reason>"."""
    if available(root):
        return "ready"
    with _building_lock:
        th = _building["thread"]
        if th is None or (not th.is_alive() and _building["error"] is None and not available(root)):
            def run():
                try:
                    print("pipeline.mirror: data/mirror/index.npz missing, building it (~3 min)...", flush=True)
                    harvest(root)
                    build(root)
                except Exception as e:  # noqa: BLE001 - reported via the status
                    _building["error"] = f"{type(e).__name__}: {e}"
                    print(f"pipeline.mirror: building the index failed: {e}", flush=True)
            _building["error"] = None
            _building["thread"] = threading.Thread(target=run, daemon=True, name="mirror-build")
            _building["thread"].start()
    if available(root):
        return "ready"
    return f"failed: {_building['error']}" if _building["error"] else "building"


def find_exposures_local(ra_deg: float, dec_deg: float, index: Index | None = None):
    """Same result shape as pipeline.query.find_exposures, from the local mirror."""
    from astropy.time import Time

    global _INDEX
    if index is None:
        if _INDEX is None:
            _INDEX = Index()
        index = _INDEX
    d = index.d
    sel = index.covering(ra_deg, dec_deg)
    mid = (d["t_min"][sel] + d["t_max"][sel]) / 2
    epochs = assign_epochs(mid)
    times = Time(mid, format="mjd", scale="utc").isot if len(mid) else []
    rows = []
    for i, k in enumerate(sel):
        coll, obs, det = str(d["collection"][k]), str(d["obs_id"][k]), int(d["detector"][k])
        did = f"ivo://irsa.ipac/{coll}?{obs}/D{det}"
        rows.append((i, k, coll, obs, det, did, derive_url(coll, obs, det, index.versions)))
    if any(r[6] is None for r in rows) and learn_weeks_from_bucket(
            {(r[2], r[3], r[4]) for r in rows if r[6] is None}, index):
        rows = [r[:6] + (r[6] or derive_url(r[2], r[3], r[4], index.versions),) for r in rows]
    missing = [r[5] for r in rows if r[6] is None]
    resolved = resolve_urls(missing) if missing else {}
    if resolved:                                       # learn the weeks so the next build skips TAP
        with open(index.path.parent / "uri_learned.csv", "a", encoding="utf-8") as fh:
            for url in resolved.values():
                fh.write(url + "\n")
                m = URI_RE.search(url)
                if m:
                    index.versions[f"{m.group(1)}/{m.group(2)}"] = m.group(3)
    exposures = [Exposure(
        obs_id=obs, collection=coll, detector=det,
        mjd_start=float(d["t_min"][k]), mjd_mid=float(mid[i]), time_utc=str(times[i])[:19] + "Z",
        exptime_s=float(d["exptime"][k]), wave_min_um=round(float(d["em_min"][k]) * 1e6, 4),
        wave_max_um=round(float(d["em_max"][k]) * 1e6, 4), epoch=int(epochs[i]),
        fits_url=url or resolved.get(did, ""), publisher_did=did)
        for i, k, coll, obs, det, did, url in rows]
    from .releases import dedupe
    exposures = dedupe([e for e in exposures if e.fits_url])   # T64: one per exposure across releases
    exposures.sort(key=lambda e: (e.mjd_mid, e.detector))
    harvested = min((p["retrieved_utc"] for p in index.provenance), default="unknown")
    prov = {"service": "local mirror of IRSA SPHEREx ObsCore (pipeline.mirror)",
            "query": f"image centres within {FOOTPRINT_RADIUS_DEG} deg of ({ra_deg}, {dec_deg}) in "
                     f"{index.path.as_posix()}; {len(missing)} FITS paths resolved via TAP; mirror "
                     f"harvested {harvested} with: " + " | ".join(p["query"] for p in index.provenance),
            "retrieved_utc": harvested}
    return exposures, prov


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("harvest")
    sub.add_parser("build")
    sub.add_parser("weeks", help="learn the path of every week folder (part of build)")
    f = sub.add_parser("find")
    f.add_argument("--ra", type=float, required=True)
    f.add_argument("--dec", type=float, required=True)
    args = ap.parse_args(argv)
    if args.cmd == "harvest":
        harvest()
    elif args.cmd == "build":
        build()
    elif args.cmd == "weeks":
        learn_all_weeks()
    else:
        t0 = time.time()
        ex, _ = find_exposures_local(args.ra, args.dec)
        print(f"{len(ex)} images in {time.time() - t0:.2f}s (incl. loading the index)")


if __name__ == "__main__":
    sys.exit(main())
