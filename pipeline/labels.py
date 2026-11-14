"""T19: catalogue labels for a target, propagated to each frame's time (CONTRACTS v0.4 `labels`).

Sources:
- SIMBAD (names, object types, proper motions; positions at J2000). The main CDS host is sometimes
  down, so official mirrors are tried in order.
- Gaia DR3 at ESA (positions at J2016.0 + proper motions), brighter than GAIA_MAX_G.

Every position is moved to the frame time with its proper motion (linear, parallax ignored: at
most ~0.5" for the nearest stars, < 0.1 px). Barnard's Star moves 10.4"/yr, so without this its
J2000 position would be 4.5' off.

    python -m pipeline.labels data/targets/<id>        # adds labels to target.json in place
"""
from __future__ import annotations

import argparse
import io
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import requests

SIMBAD_TAP = (
    "https://simbad.cds.unistra.fr/simbad/sim-tap",
    "https://simbad.cfa.harvard.edu/simbad/sim-tap",
    "https://simbad.idia.ac.za/simbad/sim-tap",
)
GAIA_TAP = "https://gea.esac.esa.int/tap-server/tap"
GAIA_MAX_G = 16.0
J2000_MJD, J2016_MJD = 51544.5, 57388.5
TIMEOUT_S = 60

# SIMBAD otype -> words for the UI. Unknown types pass through unchanged.
KIND = {
    "*": "star", "PM*": "high proper-motion star", "BD*": "brown dwarf", "BD?": "brown dwarf candidate",
    "V*": "variable star", "BY*": "variable star", "RS*": "variable star", "Mi*": "Mira variable",
    "LP*": "long-period variable", "RR*": "RR Lyrae variable", "EB*": "eclipsing binary",
    "SB*": "spectroscopic binary", "**": "double star", "WD*": "white dwarf", "WD?": "white dwarf candidate",
    "Or*": "young variable star", "TT*": "T Tauri star", "Y*O": "young star", "Pe*": "peculiar star",
    "G": "galaxy", "QSO": "quasar", "AGN": "active galaxy", "X": "X-ray source", "Neb": "nebula",
}
SKIP_OTYPES = {"Pl", "Pl?"}  # exoplanets are not separately visible
# Catalogue-number names; everything else counts as a "real" name the UI shows by default.
SURVEY_PREFIXES = ("Gaia", "2MASS", "TYC", "UCAC", "WISE", "[", "SDSS", "GALEX", "LAMOST", "ATO ", "GES ",
                   "USNO", "LEDA", "GAT ", "1RXS", "Z ", "ZTF", "PM ", "UGCA", "NVSS", "FIRST", "APOP", "CRTS")


def _tap(url: str, adql: str) -> list[dict]:
    from astropy.io.votable import parse_single_table

    r = requests.post(url.rstrip("/") + "/sync", timeout=TIMEOUT_S,
                      data={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "votable", "QUERY": adql})
    r.raise_for_status()
    table = parse_single_table(io.BytesIO(r.content)).to_table()
    names = [c.lower() for c in table.colnames]
    rows = []
    for row in table:
        rows.append({n: (None if _masked(v) else (v.item() if hasattr(v, "item") else v))
                     for n, v in zip(names, row)})
    return rows


def _masked(v) -> bool:
    import numpy as np
    return v is np.ma.masked or (isinstance(v, float) and math.isnan(v))


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Grid:
    """The target's common frame grid (CONTRACTS: TAN, north up, east left, centred on `center`)."""

    def __init__(self, target: dict):
        from astropy.wcs import WCS

        self.w, self.h = target["image"]["width"], target["image"]["height"]
        scale = target["image"]["pixel_scale_arcsec"] / 3600
        self.wcs = WCS(naxis=2)
        self.wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
        self.wcs.wcs.crval = [target["center"]["ra_deg"], target["center"]["dec_deg"]]
        self.wcs.wcs.crpix = [(self.w + 1) / 2, (self.h + 1) / 2]
        self.wcs.wcs.cdelt = [-scale, scale]
        self.radius_deg = math.hypot(self.w, self.h) / 2 * scale + 0.01  # corners + room for movers

    def to_xy(self, ra: float, dec: float) -> tuple[float, float]:
        x, y = self.wcs.world_to_pixel_values(ra, dec)
        return float(x), float(self.h - 1 - y)  # contract: y down, origin top-left pixel centre

    def contains(self, x: float, y: float, margin: float = 2) -> bool:
        return -margin <= x <= self.w - 1 + margin and -margin <= y <= self.h - 1 + margin


def _track(grid: Grid, frames: list[dict], ra, dec, pmra, pmdec, epoch_mjd) -> list[dict]:
    pmra, pmdec = pmra or 0.0, pmdec or 0.0
    out = []
    for f in frames:
        yr = (f["mjd"] - epoch_mjd) / 365.25
        r = ra + pmra * yr / 3.6e6 / math.cos(math.radians(dec))
        d = dec + pmdec * yr / 3.6e6
        x, y = grid.to_xy(r, d)
        out.append({"frame_id": f["id"], "ra_deg": round(r, 6), "dec_deg": round(d, 6),
                    "x": round(x, 2), "y": round(y, 2)})
    return out


def simbad_labels(target: dict, grid: Grid) -> tuple[list[dict], dict | None]:
    c = target["center"]
    adql = (f"SELECT main_id, ra, dec, pmra, pmdec, otype FROM basic WHERE "
            f"CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {c['ra_deg']}, {c['dec_deg']}, {grid.radius_deg:.5f})) = 1")
    errors = []
    for url in SIMBAD_TAP:
        try:
            rows = _tap(url, adql)
        except Exception as e:  # a down mirror must not break the build
            errors.append(f"{url}: {str(e)[:80]}")
            continue
        prov = {"service": "SIMBAD TAP " + url, "query": adql, "retrieved_utc": _now()}
        labels = []
        for r in rows:
            if r["otype"] in SKIP_OTYPES or r["ra"] is None:
                continue
            pos = _track(grid, target["frames"], r["ra"], r["dec"], r["pmra"], r["pmdec"], J2000_MJD)
            if not any(grid.contains(p["x"], p["y"]) for p in pos):
                continue
            name = str(r["main_id"]).replace("NAME ", "").replace("V* ", "").strip()
            pm = math.hypot(r["pmra"] or 0, r["pmdec"] or 0) if r["pmra"] is not None else None
            labels.append({"name": name, "kind": KIND.get(r["otype"], r["otype"]), "otype": r["otype"],
                           "source": "simbad", "named": not str(r["main_id"]).startswith(SURVEY_PREFIXES),
                           "mag": None, "pm_mas_yr": None if pm is None else round(pm, 1), "positions": pos})
        return labels, prov
    print("SIMBAD unavailable, no names this time:", "; ".join(errors))
    return [], None


def gaia_labels(target: dict, grid: Grid) -> tuple[list[dict], dict | None]:
    c = target["center"]
    adql = (f"SELECT source_id, ra, dec, pmra, pmdec, phot_g_mean_mag FROM gaiadr3.gaia_source WHERE "
            f"1 = CONTAINS(POINT(ra, dec), CIRCLE({c['ra_deg']}, {c['dec_deg']}, {grid.radius_deg:.5f})) "
            f"AND phot_g_mean_mag < {GAIA_MAX_G}")
    try:
        rows = _tap(GAIA_TAP, adql)
    except Exception as e:
        print("Gaia unavailable:", str(e)[:120])
        return [], None
    prov = {"service": "Gaia DR3 TAP (ESA) " + GAIA_TAP, "query": adql, "retrieved_utc": _now()}
    labels = []
    for r in rows:
        pos = _track(grid, target["frames"], r["ra"], r["dec"], r["pmra"], r["pmdec"], J2016_MJD)
        if not any(grid.contains(p["x"], p["y"]) for p in pos):
            continue
        pm = math.hypot(r["pmra"], r["pmdec"]) if r["pmra"] is not None else None
        labels.append({"name": f"Gaia DR3 {r['source_id']}", "kind": "star", "otype": "*", "source": "gaia_dr3",
                       "named": False, "mag": round(r["phot_g_mean_mag"], 2),
                       "pm_mas_yr": None if pm is None else round(pm, 1), "positions": pos})
    return labels, prov


def add_labels(target: dict) -> dict:
    """Fill target["labels"] (replacing any old ones) and append provenance. Returns the target.

    Synthetic targets get no labels: real catalogue names on simulated frames would mislead."""
    if target.get("synthetic"):
        target["labels"] = []
        return target
    grid = Grid(target)
    labels = []
    for fn in (simbad_labels, gaia_labels):
        found, prov = fn(target, grid)
        labels += found
        if prov:
            target.setdefault("provenance", []).append(prov)
    from .motion import summarize  # T23: motion summary + class per label
    scale = target["image"]["pixel_scale_arcsec"]
    for l in labels:
        l["motion"] = summarize(l["positions"], target["frames"], scale)
    labels.sort(key=lambda l: (not l["named"], l["source"] != "simbad", l["mag"] if l["mag"] is not None else 99))
    for i, l in enumerate(labels):
        l["id"] = f"l{i:03d}"
    target["labels"] = labels
    return target


def main(argv=None):
    ap = argparse.ArgumentParser(description="Add catalogue labels to a target folder's target.json")
    ap.add_argument("target_dir", type=Path)
    args = ap.parse_args(argv)
    path = args.target_dir / "target.json"
    target = add_labels(json.loads(path.read_text()))
    path.write_text(json.dumps(target, indent=1))
    named = [l["name"] for l in target["labels"] if l["named"]]
    print(f"{len(target['labels'])} labels, {len(named)} named: {', '.join(named[:10])}")


if __name__ == "__main__":
    main()
