"""T07: catalogued asteroids and comets in a target's field → `known_objects` (CONTRACTS "Known object").

Positions are as seen from SPHEREx (Horizons ID -163182), not from the geocentre:

1. Frames are grouped into visits (bursts of exposures minutes apart; a main-belt asteroid crosses a
   15' field in under a day, so each visit needs its own search).
2. JPL Horizons: SPHEREx's geocentric state vector (ICRF, km, km/s) at each visit's mid time.
3. JPL SB Identification (`sb_ident.api`), first pass, with that state vector as the observer
   (`xobs`): the candidate small bodies near the field, down to `vmag_lim`. The first pass is fast
   (~20 s) and good to ~20" here; the precise second pass takes minutes per call.
4. JPL Horizons again, observer = SPHEREx itself (`CENTER='500@-163182'`): astrometric RA/Dec of
   each candidate at every frame time of the visits it was found in.
5. Sky → pixel with the target grid (`pipeline.labels.Grid`); objects with at least one position in
   the field become `known_objects`.

    python -m detect.known_objects data/targets/<id> [--vmag 20]     # updates target.json in place

Only `known_objects` and `provenance` are written. Each API request is recorded in provenance with
its query and UTC time, so the result can be reproduced.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests

HORIZONS = "https://ssd.jpl.nasa.gov/api/horizons.api"
SB_IDENT = "https://ssd-api.jpl.nasa.gov/sb_ident.api"
SPHEREX = "-163182"
MJD_TO_JD = 2400000.5
VISIT_GAP_DAYS = 0.25      # frames closer than this belong to one visit
SEARCH_MARGIN_DEG = 0.1    # widen the candidate search: first-pass error + motion within a visit
DEFAULT_VMAG = 20.0        # SPHEREx single exposures reach roughly V ~ 19-20 for asteroids
TIMEOUT = 180
RETRIES = (3, 10, 30)    # seconds to wait after a 503 / timeout before trying again


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------- small pure helpers (unit-tested) ----------

def group_visits(frames: list[dict], gap_days: float = VISIT_GAP_DAYS) -> list[list[dict]]:
    """Frames sorted by time, split wherever two consecutive frames are more than gap_days apart."""
    visits: list[list[dict]] = []
    for f in sorted(frames, key=lambda f: f["mjd"]):
        if visits and f["mjd"] - visits[-1][-1]["mjd"] <= gap_days:
            visits[-1].append(f)
        else:
            visits.append([f])
    return visits


def sexagesimal(value_deg: float, hours: bool) -> str:
    """sb_ident wants hh-mm-ss.ss / dd-mm-ss.ss, with M instead of a minus sign."""
    v = value_deg / 15 if hours else value_deg
    sign = "M" if v < 0 else ""
    v = abs(v)
    d = int(v)
    m = int((v - d) * 60)
    s = (v - d - m / 60) * 3600
    if s >= 59.995:  # rounding carry
        s, m = 0.0, m + 1
    if m == 60:
        m, d = 0, d + 1
    return f"{sign}{d:02d}-{m:02d}-{s:05.2f}"


def horizons_command(name: str) -> str:
    """Horizons COMMAND for an sb_ident object name.

    '6779 Perrine (1990 DM1)' -> '6779;'      numbered asteroid
    '(2000 YJ34)'             -> 'DES=2000 YJ34;'
    'C/2020 F3 (NEOWISE)'     -> 'DES=C/2020 F3;CAP;'   comet: closest apparition
    '29P/Schwassmann-Wachmann 1' -> 'DES=29P;CAP;NOFRAG;'
    """
    name = name.strip()
    m = re.match(r"^(\d+)(?:\s|$)", name)
    if m and "/" not in name.split()[0]:
        return f"{m.group(1)};"
    m = re.match(r"^(\d+[PDCXI])(?:/|$)", name)  # periodic comet number, e.g. 29P/...
    if m:
        return f"DES={m.group(1)};CAP;NOFRAG;"  # fragmented comets match several records otherwise
    m = re.match(r"^([PDCXAI]/\d{4} [A-Z]{1,2}\d*)", name)  # comet / interstellar designation
    if m:
        return f"DES={m.group(1)};CAP;"
    m = re.search(r"\((\d{4} [A-Z]{2}\d*)\)", name)  # provisional designation in parentheses
    if m:
        return f"DES={m.group(1)};"
    return f"{name};"


def parse_horizons_table(result: str) -> list[list[str]]:
    """CSV rows between $$SOE and $$EOE of a Horizons text result."""
    i, j = result.find("$$SOE"), result.find("$$EOE")
    if i < 0 or j < 0:
        raise ValueError(f"no ephemeris in Horizons answer: {result[-300:]!r}")
    rows = []
    for line in result[i + 5:j].strip().splitlines():
        rows.append([c.strip() for c in line.split(",")])
    return rows


# ---------- JPL requests ----------

class Jpl:
    """Thin client; every request is remembered for provenance."""

    def __init__(self, session: requests.Session | None = None):
        self.s = session or requests.Session()
        self.s.headers.setdefault("User-Agent", "spherex-blink (NASA Space Apps 2026)")
        self.log: list[dict] = []

    def _get(self, url: str, params: dict, service: str) -> dict:
        for wait in (*RETRIES, None):
            try:
                r = self.s.get(url, params=params, timeout=TIMEOUT)
                if r.status_code not in (429, 502, 503, 504):
                    break
            except (requests.ConnectionError, requests.Timeout):
                if wait is None:
                    raise
            if wait is None:
                break
            time.sleep(wait)  # JPL asks for one request at a time and answers 503 when busy
        r.raise_for_status()
        self.log.append({"service": service, "query": f"{url}?" + "&".join(f"{k}={v}" for k, v in params.items()),
                         "retrieved_utc": _now()})
        return r.json()

    def spherex_states(self, jds: list[float]) -> dict[float, list[float]]:
        """Geocentric ICRF state vectors of SPHEREx: jd -> [x, y, z, vx, vy, vz] (km, km/s)."""
        params = {
            "format": "json", "COMMAND": f"'{SPHEREX}'", "OBJ_DATA": "'NO'", "MAKE_EPHEM": "'YES'",
            "EPHEM_TYPE": "'VECTORS'", "CENTER": "'500@399'", "REF_PLANE": "'FRAME'", "VEC_TABLE": "'2'",
            "OUT_UNITS": "'KM-S'", "CSV_FORMAT": "'YES'", "TIME_TYPE": "'UT'", "TLIST_TYPE": "'JD'",
            "TLIST": " ".join(f"'{jd:.6f}'" for jd in jds),
        }
        rows = parse_horizons_table(self._get(HORIZONS, params, "JPL Horizons (SPHEREx state vectors)")["result"])
        if len(rows) != len(jds):
            raise ValueError(f"Horizons returned {len(rows)} state vectors for {len(jds)} times")
        states = {}
        for jd, row in zip(jds, rows):
            states[jd] = [float(v) for v in row[2:8]]
        return states

    def candidates(self, jd: float, state: list[float], ra_deg: float, dec_deg: float,
                   half_width_deg: float, vmag_lim: float) -> list[str]:
        """Names of small bodies near the field at jd, seen from `state` (sb_ident first pass)."""
        params = {
            "xobs": ",".join(f"{v:.9f}" for v in state), "obs-time": f"{jd:.6f}",
            "fov-ra-center": sexagesimal(ra_deg, hours=True), "fov-dec-center": sexagesimal(dec_deg, hours=False),
            "fov-ra-hwidth": f"{half_width_deg:.3f}", "fov-dec-hwidth": f"{half_width_deg:.3f}",
            "two-pass": "false", "vmag-lim": f"{vmag_lim:g}",
        }
        d = self._get(SB_IDENT, params, "JPL SB Identification (sb_ident, first pass)")
        fields = d.get("fields_first") or []
        rows = d.get("data_first_pass") or []
        if not rows:
            return []
        col = fields.index("Object name") if "Object name" in fields else 0
        return [r[col] for r in rows]

    def positions(self, name: str, jds: list[float]) -> list[tuple[float, float]]:
        """Astrometric (ICRF) RA/Dec in degrees of a small body seen from SPHEREx, one per jd.

        Frames from two detectors share a time; Horizons rejects repeated times ("Bad dates"), so each
        time is asked once and mapped back."""
        unique = sorted(set(jds))
        params = {
            "format": "json", "COMMAND": f"'{horizons_command(name)}'", "OBJ_DATA": "'NO'", "MAKE_EPHEM": "'YES'",
            "EPHEM_TYPE": "'OBSERVER'", "CENTER": f"'500@{SPHEREX}'", "QUANTITIES": "'1'", "ANG_FORMAT": "'DEG'",
            "CSV_FORMAT": "'YES'", "TIME_TYPE": "'UT'", "TLIST_TYPE": "'JD'",
            "TLIST": " ".join(f"'{jd:.6f}'" for jd in unique),
        }
        rows = parse_horizons_table(self._get(HORIZONS, params, "JPL Horizons (observer: SPHEREx)")["result"])
        if len(rows) != len(unique):
            raise ValueError(f"Horizons returned {len(rows)} rows for {len(unique)} times")
        # columns: date, solar flag, lunar flag, RA, Dec (ANG_FORMAT=DEG)
        at = {jd: (float(r[3]), float(r[4])) for jd, r in zip(unique, rows)}
        return [at[jd] for jd in jds]


# ---------- the step ----------

def find_known_objects(target: dict, jpl: Jpl | None = None, vmag_lim: float = DEFAULT_VMAG) -> list[dict]:
    """known_objects for a target dict (does not modify it)."""
    from pipeline.labels import Grid

    jpl = jpl or Jpl()
    grid = Grid(target)
    frames = target["frames"]
    visits = group_visits(frames)
    mid_jds = [round((v[0]["mjd"] + v[-1]["mjd"]) / 2 + MJD_TO_JD, 6) for v in visits]
    states = jpl.spherex_states(mid_jds)

    half = grid.radius_deg + SEARCH_MARGIN_DEG
    ra0, dec0 = target["center"]["ra_deg"], target["center"]["dec_deg"]
    with ThreadPoolExecutor(max_workers=2) as pool:  # sb_ident takes ~20 s per call; two at a time
        found = list(pool.map(lambda jd: jpl.candidates(jd, states[jd], ra0, dec0, half, vmag_lim), mid_jds))

    # candidate name -> frames of the visits it was found in
    wanted: dict[str, list[dict]] = {}
    for visit, names in zip(visits, found):
        for name in names:
            wanted.setdefault(name, []).extend(visit)

    def track(item):
        name, fs = item
        jds = [round(f["mjd"] + MJD_TO_JD, 6) for f in fs]
        try:
            radec = jpl.positions(name, jds)
        except (requests.RequestException, ValueError) as e:
            print(f"known_objects: no Horizons positions for {name!r}: {e}", file=sys.stderr)
            return None
        pos = []
        for f, (ra, dec) in zip(fs, radec):
            x, y = grid.to_xy(ra, dec)
            if grid.contains(x, y):
                pos.append({"frame_id": f["id"], "ra_deg": round(ra, 6), "dec_deg": round(dec, 6),
                            "x": round(x, 2), "y": round(y, 2)})
        if not pos:
            return None
        return {"name": name, "source": "jpl-sbident", "synthetic": False, "positions": pos}

    # Horizons: strictly one request at a time (JPL's rule; parallel requests got 503s)
    return [o for o in map(track, sorted(wanted.items())) if o]


def add_known_objects(target: dict, jpl: Jpl | None = None, vmag_lim: float = DEFAULT_VMAG) -> dict:
    """Fill target["known_objects"] and append the JPL requests to provenance. Returns the target."""
    jpl = jpl or Jpl()
    target["known_objects"] = find_known_objects(target, jpl, vmag_lim)
    calls = jpl.log
    if calls:
        # One provenance entry per service (all its queries), so the list stays readable.
        by_service: dict[str, list[dict]] = {}
        for c in calls:
            by_service.setdefault(c["service"], []).append(c)
        for service, cs in by_service.items():
            target.setdefault("provenance", []).append({
                "service": service,
                "query": f"{len(cs)} request(s); vmag-lim {vmag_lim:g}; first: {cs[0]['query']}",
                "retrieved_utc": max(c["retrieved_utc"] for c in cs),
            })
    return target


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m detect.known_objects", description=__doc__.split("\n\n")[0])
    ap.add_argument("target_dir", type=Path)
    ap.add_argument("--vmag", type=float, default=DEFAULT_VMAG, help="faintest V magnitude to look for")
    args = ap.parse_args(argv)
    path = args.target_dir / "target.json"
    target = json.loads(path.read_text(encoding="utf-8"))
    add_known_objects(target, vmag_lim=args.vmag)
    path.write_text(json.dumps(target, indent=2), encoding="utf-8")
    ko = target["known_objects"]
    print(f"{len(ko)} known object(s) in {path}")
    for o in ko:
        print(f"  {o['name']:<36} {len(o['positions'])} frame(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
