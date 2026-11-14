"""Build web/discover.json (T65): fields where something visibly moves, as quick picks next to the five official ones.

    python web/make_discover.py            # from the repo root; needs the local SPHEREx index (data/mirror, T31)

Two lists from SIMBAD (TAP; the Harvard mirror first, CDS has been unreliable), each position checked against
the local SPHEREx image index (at least two epochs):

- Fastest-moving stars: the fastest proper motions, kept if they move >= MIN_SHIFT_PX within SPHEREx's
  coverage there (DR1 spans about a year, so only stars faster than ~5"/yr qualify). Bright ones are kept:
  their saturated core shows as a moving gap, as for Barnard's Star.
- Brown dwarfs: nearby ones (object type BD*, proper motion > 1"/yr) bright enough for a spectrum (K <= 13.5).
  They move too little to see in a blink here (0.2-0.5 px); the point is their spectrum (T63).

Not one of the five official fields, one entry per multiple system (10'). Positions are moved to epoch 2026.0
like web/presets.json, so the object sits near the field centre.
"""
from __future__ import annotations

import csv
import io
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

SIMBAD = ["https://simbad.cfa.harvard.edu/simbad/sim-tap/sync", "https://simbad.idia.ac.za/simbad/sim-tap/sync",
          "https://simbad.cds.unistra.fr/simbad/sim-tap/sync"]
PIXEL_ARCSEC = 6.15
EPOCH = 2026.0
SIZE_ARCMIN = 10
MIN_SHIFT_PX = 0.75
BD_MAX_K = 13.5
PER_CLASS = 10
QUERY = """SELECT TOP {n} b.main_id, b.ra, b.dec, b.pmra, b.pmdec, b.otype, b.plx_value,
 (b.pmra*b.pmra + b.pmdec*b.pmdec) AS pm2, fk.flux AS k
FROM basic AS b LEFT OUTER JOIN flux AS fk ON fk.oidref = b.oid AND fk.filter = 'K'
WHERE {where} ORDER BY pm2 DESC"""
CLASSES = [
    ("fast", "Fastest-moving stars", 150, "b.pmra*b.pmra + b.pmdec*b.pmdec > 9000000 AND b.otype NOT IN ('Pl', 'Pl?', 'err')"),
    ("bd", "Brown dwarfs: look at the spectrum", 150, "b.otype IN ('BD*', 'BD?') AND b.pmra*b.pmra + b.pmdec*b.pmdec > 1000000"),
]
# Common names SIMBAD has no "NAME" identifier for (checked 2026-11-14)
WELL_KNOWN = {"HD 103095": "Groombridge 1830", "HD 225213": "Gliese 1", "HD 95735": "Lalande 21185", "61 Cyg A": "61 Cygni A"}
KIND = {"BD*": "brown dwarf", "LM*": "low-mass star", "Lm*": "low-mass star", "BD?": "brown dwarf candidate", "WD*": "white dwarf", "PM*": "high proper-motion star",
        "BY*": "flare/spotted red dwarf", "Er*": "flare star", "Fl*": "flare star", "Pe*": "chemically peculiar star",
        "**": "double star", "*": "star", "Em*": "emission-line star", "RS*": "active binary star"}


def simbad(adql: str) -> tuple[list[dict], str]:
    last = None
    for url in SIMBAD:
        try:
            r = requests.post(url, data={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": adql}, timeout=90)
            if r.status_code == 200 and not r.text.lstrip().startswith("<"):
                return list(csv.DictReader(io.StringIO(r.text))), url
            last = f"{url}: HTTP {r.status_code}"
        except requests.RequestException as e:
            last = f"{url}: {e}"
    raise RuntimeError(f"SIMBAD unreachable ({last})")


def to_epoch(ra: float, dec: float, pmra: float, pmdec: float, years: float) -> tuple[float, float]:
    """J2000 ICRS + proper motion (pmra includes cos dec, mas/yr), linear; parallax ignored (< 1")."""
    dec2 = dec + pmdec * years / 3.6e6
    ra2 = ra + pmra * years / 3.6e6 / math.cos(math.radians((dec + dec2) / 2))
    return round(ra2 % 360, 4), round(dec2, 4)


def sep_deg(a: tuple[float, float], b: tuple[float, float]) -> float:
    ra1, d1, ra2, d2 = map(math.radians, (*a, *b))
    c = math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(ra1 - ra2)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def coverage(ra: float, dec: float) -> dict | None:
    from pipeline import mirror
    exps = mirror.find_exposures_local(ra, dec)[0]
    if not exps:
        return None
    epochs = sorted({e.epoch for e in exps})
    t0, t1 = min(e.mjd_mid for e in exps), max(e.mjd_mid for e in exps)
    return {"epochs": len(epochs), "images": len(exps), "span_days": round(t1 - t0, 1),
            "first": exps[0].time_utc[:10], "last": max(exps, key=lambda e: e.mjd_mid).time_utc[:10]}


def clean(main_id: str) -> str:
    """'* 61 Cyg A' -> '61 Cyg A', 'V* AX Mic' -> 'AX Mic', 'HD  33793' -> 'HD 33793'."""
    n = " ".join(main_id.removeprefix("NAME ").split())
    for p in ("V* ", "* "):
        n = n.removeprefix(p)
    return n


def common_names(ids: list[str]) -> tuple[dict[str, str], dict]:
    """SIMBAD 'NAME …' identifiers (Kapteyn's Star for HD 33793), {main_id: name}."""
    quoted = ", ".join("'" + i.replace("'", "''") + "'" for i in ids)
    adql = (f"SELECT j.id AS main, i.id AS name FROM ident AS i JOIN ident AS j ON i.oidref = j.oidref "
            f"WHERE j.id IN ({quoted}) AND i.id LIKE 'NAME %'")
    rows, url = simbad(adql.replace("SELECT j.id", "SELECT TOP 500 j.id"))
    out: dict[str, str] = {}
    rank = lambda n: (0 if "'s star" in n.lower() else 1 if "star" in n.lower() else 2, len(n))  # noqa: E731
    for r in rows:   # several names: "Kapteyn's star" before "Kapteyn Star" before "Kapteyn's"
        n = r["name"].removeprefix("NAME ").strip()
        if r["main"] not in out or rank(n) < rank(out[r["main"]]):
            out[r["main"]] = n
    return out, {"service": f"SIMBAD TAP {url}", "query": adql,
                 "retrieved_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def why(row: dict) -> str:
    dist = f", {3261.56 / row['plx_mas']:.0f} light-years away" if row.get("plx_mas") else ""
    cov = f"({row['coverage']['first']} → {row['coverage']['last']}, {row['coverage']['epochs']} epochs)"
    if row["class"] == "fast":
        sat = " It is bright, so its saturated core shows as a gap that moves with it." if row["k_mag"] < 6 else ""
        return (f"{row['kind'].capitalize()}{dist}. Moves {row['pm_arcsec_per_yr']:.1f}″ a year: about "
                f"{row['shift_px']:.1f} SPHEREx pixels between the first and last epoch here {cov}. Small: blink the "
                f"first against the last epoch, the name and its path show where it goes.{sat}")
    return (f"{row['kind'].capitalize()}{dist}. Moves {row['pm_arcsec_per_yr']:.1f}″ a year, only {row['shift_px']:.1f} px "
            f"in SPHEREx's coverage here {cov}: too little to see in a blink (the name shows its path). Look at its "
            f"spectrum instead: a brown dwarf doesn't follow a star's shape (water and methane absorb) and is "
            f"bright at 4–5 µm.")


def main() -> int:
    from pipeline import mirror
    if not mirror.available():
        print("needs the local SPHEREx index: python -m pipeline.mirror harvest && python -m pipeline.mirror build", file=sys.stderr)
        return 1
    official = [(f["ra_deg"], f["dec_deg"]) for f in json.loads((REPO / "web" / "presets.json").read_text())["fields"]]
    years = EPOCH - 2000.0
    fields, provenance = [], []
    for cls, group, n, where in CLASSES:
        adql = QUERY.format(n=n, where=where)
        rows, url = simbad(adql)
        provenance.append({"service": f"SIMBAD TAP {url}", "query": " ".join(adql.split()),
                           "retrieved_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
        kept: list[dict] = []
        for r in rows:
            try:
                ra, dec, pmra, pmdec = (float(r[c]) for c in ("ra", "dec", "pmra", "pmdec"))
            except ValueError:
                continue
            k = float(r["k"]) if r["k"] else None
            if k is None or (cls == "bd" and k > BD_MAX_K):
                continue
            pos = to_epoch(ra, dec, pmra, pmdec, years)
            if any(sep_deg(pos, o) < 10 / 60 for o in official + [(f["ra_deg"], f["dec_deg"]) for f in fields + kept]):
                continue                     # an official field, or another member of a system already listed
            cov = coverage(*pos)
            if not cov or cov["epochs"] < 2:
                continue
            pm = math.hypot(pmra, pmdec) / 1000
            row = {"name": clean(r["main_id"]), "group": group, "class": cls,
                   "simbad_id": r["main_id"], "kind": KIND.get(r["otype"], r["otype"]), "otype": r["otype"],
                   "k_mag": round(k, 2), "plx_mas": round(float(r["plx_value"]), 2) if r["plx_value"] else None,
                   "pm_arcsec_per_yr": round(pm, 2), "ra_deg": pos[0], "dec_deg": pos[1], "size_arcmin": SIZE_ARCMIN,
                   "coverage": cov, "shift_px": round(pm * cov["span_days"] / 365.25 / PIXEL_ARCSEC, 2)}
            if cls == "fast" and row["shift_px"] < MIN_SHIFT_PX:
                continue
            row["why"] = why(row)
            kept.append(row)
            print(f"  {group[:12]:<12} {row['name']:<28} pm {pm:5.2f}\"/yr K {k:5.1f} {cov['epochs']} epochs  shift {row['shift_px']:.2f} px")
        kept.sort(key=lambda f: -f["shift_px"] if cls == "fast" else f["k_mag"])
        fields += kept[:PER_CLASS]
    names, prov = common_names([f["simbad_id"] for f in fields])
    provenance.append(prov)
    for f in fields:
        nice = names.get(f["simbad_id"]) or WELL_KNOWN.get(f["name"])
        if nice and nice != f["name"]:
            f["catalogue_id"], f["name"] = f["name"], nice
    provenance.append({"service": "local SPHEREx image index (pipeline.mirror, T31)", "query": "exposures covering each position",
                       "retrieved_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    out = {
        "description": "Quick picks next to the five official fields (T65): stars that visibly move within SPHEREx's coverage, "
                       "and nearby brown dwarfs whose spectrum is the interesting part. Built by web/make_discover.py; the "
                       "official fields are in presets.json.",
        "method": f"SIMBAD J2000 ICRS + proper motion propagated linearly to epoch {EPOCH}, rounded to 1e-4 deg; one per "
                  f"system (10'); shift_px = proper motion x (last - first SPHEREx exposure there) / {PIXEL_ARCSEC}\"; moving "
                  f"stars need shift_px >= {MIN_SHIFT_PX}, brown dwarfs K (Vega) <= {BD_MAX_K}, sorted by K",
        "provenance": provenance,
        "fields": fields,
    }
    (REPO / "web" / "discover.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote web/discover.json: {len(fields)} fields")
    return 0


if __name__ == "__main__":
    sys.exit(main())
