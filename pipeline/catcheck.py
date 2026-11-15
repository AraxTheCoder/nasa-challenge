"""T128: which catalogues know a spot? For the chemistry candidates (pipeline/chemistry.py candidates()): the user
picks catalogues, each spot gets the nearest source within MATCH_ARCSEC of where SPHEREx saw it.

Catalogue positions are at their own epoch (SIMBAD 2000, Gaia 2016, CatWISE ~2015, AllWISE ~2010, 2MASS ~1999);
the stars worth finding (nearby brown dwarfs) move several ″/yr. So sources are searched in a wider circle and
moved by their proper motion to the SPHEREx date before matching. AllWISE and 2MASS carry no (usable) motion:
fast movers don't match there.

Services: SIMBAD TAP (mirrors as pipeline.labels), Gaia DR3 / CatWISE2020 / AllWISE / 2MASS via VizieR (CfA mirror
first; ESA's Gaia TAP and CDS xMatch did not answer from here on 2026-11-15). A failed catalogue is reported, never
counted as "not there". Answers are cached per field in <target>/chemistry/catcheck.json (position + catalogue).
"""
from __future__ import annotations

import json
import math
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CATALOGUES = {           # id: (name, what it holds)
    "simbad": ("SIMBAD", "named objects with types"),
    "gaia": ("Gaia DR3", "optical, G < 21, motions"),
    "catwise": ("CatWISE2020", "3.4 / 4.6 µm, motions"),
    "allwise": ("AllWISE", "3.4–22 µm"),
    "2mass": ("2MASS", "J H Ks, 1998–2001"),
}
DEFAULT = ("simbad", "gaia", "catwise")
MATCH_ARCSEC = 6.0
SIMBAD_SLOW_ARCSEC = 12.0    # SIMBAD search for any source (0.2″/yr over 26 yr + the match)
SIMBAD_FAST_ARCSEC = 300.0   # ... and for fast movers (pm > 0.2″/yr): Barnard's Star 10″/yr over 26 yr
VIZIER_ARCSEC = {"gaia": 60.0, "catwise": 60.0, "allwise": MATCH_ARCSEC, "2mass": MATCH_ARCSEC}   # 60″: 6″/yr × 10 yr
VIZ = {   # VizieR table, position columns, epoch (year, or a per-row MJD / JD column), motion columns + unit, id, mag
    "gaia": {"src": "I/355/gaiadr3", "ra": "RA_ICRS", "dec": "DE_ICRS", "year": 2016.0, "pm": ("pmRA", "pmDE", 1e-3),
             "id": "Source", "mag": ("Gmag", "G")},
    "catwise": {"src": "II/365/catwise", "ra": "RAPMdeg", "dec": "DEPMdeg", "mjd": "MJD", "pm": ("pmRA", "pmDE", 1.0),
                "id": "Name", "mag": ("W2mproPM", "W2")},
    "allwise": {"src": "II/328/allwise", "ra": "RAJ2000", "dec": "DEJ2000", "year": 2010.5, "pm": None,
                "id": "AllWISE", "mag": ("W2mag", "W2")},
    "2mass": {"src": "II/246/out", "ra": "RAJ2000", "dec": "DEJ2000", "jd": "JD", "pm": None,
              "id": "2MASS", "mag": ("Kmag", "Ks")},
}
_lock = threading.Lock()


def _sep_arcsec(ra1, dec1, ra2, dec2) -> float:
    return 3600 * math.hypot(((ra1 - ra2 + 180) % 360 - 180) * math.cos(math.radians(dec2)), dec1 - dec2)


def _moved(ra, dec, pmra, pmdec, years):
    """Position after `years` of proper motion (pmra includes cos dec, both in ″/yr)."""
    return (ra + pmra * years / 3600 / max(math.cos(math.radians(dec)), 1e-6), dec + pmdec * years / 3600)


def _year_of_mjd(mjd: float) -> float:
    return 2000.0 + (mjd - 51544.5) / 365.25


def _simbad(spots, year):
    """{spot index: best match or None} for all spots in one ADQL query. Raises if every mirror fails."""
    from .labels import KIND, SIMBAD_TAP, _num, _tap
    a = SIMBAD_SLOW_ARCSEC / 3600
    b = SIMBAD_FAST_ARCSEC / 3600
    cond = " OR ".join(
        f"CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {ra:.6f}, {dec:.6f}, {a:.6f}))=1 OR "
        f"(CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {ra:.6f}, {dec:.6f}, {b:.6f}))=1 "
        f"AND pmra*pmra + pmdec*pmdec > 40000)" for ra, dec in spots)
    adql = f"SELECT main_id, ra, dec, pmra, pmdec, otype FROM basic WHERE {cond}"
    err = None
    for url in (SIMBAD_TAP[1], SIMBAD_TAP[0], SIMBAD_TAP[2]):     # the CfA mirror answered first this weekend
        try:
            cols = _tap(url, adql)
            break
        except Exception as e:  # noqa: BLE001 - next mirror
            err = e
    else:
        raise ConnectionError(f"SIMBAD: {err}")
    n = len(cols.get("main_id", []))
    if not n:
        return {i: None for i in range(len(spots))}
    ra, _ = _num(cols["ra"]); dec, _ = _num(cols["dec"])
    pmra, _ = _num(cols["pmra"]); pmdec, _ = _num(cols["pmdec"])
    rows = []
    for k in range(n):
        r2, d2 = _moved(float(ra[k]), float(dec[k]), pmra[k] / 1000, pmdec[k] / 1000, year - 2000.0)
        name = " ".join(str(cols["main_id"][k]).replace("NAME ", "").split())
        otype = str(cols["otype"][k]).strip()
        rows.append((r2, d2, name, otype, KIND.get(otype, otype)))
    out = {}
    for i, (sra, sdec) in enumerate(spots):
        near = sorted((_sep_arcsec(r2, d2, sra, sdec), name.startswith("["), name, otype, kind)
                      for r2, d2, name, otype, kind in rows)
        near = [t for t in near if t[0] <= MATCH_ARCSEC]
        best = min(near, key=lambda t: (t[1], t[0])) if near else None   # "3C 273" before "[CME2001] 3C 273 1"
        out[i] = {"name": best[2], "otype": best[3], "kind": best[4], "sep_arcsec": round(best[0], 1)} if best else None
    return out


def _vizier_one(cat, ra, dec, year):
    """Best match of one VizieR catalogue around one spot, or None. Raises when VizieR does not answer."""
    from .labels import _asu, _float
    v = VIZ[cat]
    rows, _ = _asu({"-source": v["src"], "-c": f"{ra:.6f} {dec:+.6f}", "-c.rs": f"{VIZIER_ARCSEC[cat]:.0f}",
                    "-out.max": "2000", "-out.all": None})
    best = None
    for r in rows:
        r0, d0 = _float(r.get(v["ra"], "")), _float(r.get(v["dec"], ""))
        if r0 is None or d0 is None:
            continue
        if "mjd" in v:
            ep = _year_of_mjd(_float(r.get(v["mjd"], "")) or 57170.0)
        elif "jd" in v:
            ep = _year_of_mjd((_float(r.get(v["jd"], "")) or 2451544.5) - 2400000.5)
        else:
            ep = v["year"]
        if v["pm"]:
            k_ra, k_de, unit = v["pm"]
            r0, d0 = _moved(r0, d0, (_float(r.get(k_ra, "")) or 0.0) * unit, (_float(r.get(k_de, "")) or 0.0) * unit, year - ep)
        sep = _sep_arcsec(r0, d0, ra, dec)
        if sep <= MATCH_ARCSEC and (best is None or sep < best["sep_arcsec"]):
            mag = _float(r.get(v["mag"][0], ""))
            best = {"name": f"{CATALOGUES[cat][0]} {r.get(v['id'], '').strip()}", "sep_arcsec": round(sep, 1),
                    "mag": round(mag, 2) if mag is not None else None, "band": v["mag"][1]}
    return best


def check(target_dir: Path, spots, cats, year: float) -> dict:
    """spots: [(ra, dec)] -> {"matches": [{cat: match | None}], "failed": [cat ids]} (a failed catalogue appears in
    no spot's dict). Cached per field: <target>/chemistry/catcheck.json, key "<cat>:<ra .5f>,<dec .5f>"."""
    cats = [c for c in dict.fromkeys(cats) if c in CATALOGUES]
    path = Path(target_dir) / "chemistry" / "catcheck.json"
    with _lock:
        try:
            cache = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cache = {}
    key = lambda c, s: f"{c}:{s[0]:.5f},{s[1]:.5f}"             # noqa: E731
    matches = [{} for _ in spots]
    failed, todo = [], {}
    for c in cats:
        missing = [i for i, s in enumerate(spots) if key(c, s) not in cache]
        for i, s in enumerate(spots):
            if key(c, s) in cache:
                matches[i][c] = cache[key(c, s)]
        if missing:
            todo[c] = missing
    new = {}

    def run(c, idx):
        if c == "simbad":
            got = _simbad([spots[i] for i in idx], year)
            return {idx[j]: m for j, m in got.items()}
        with ThreadPoolExecutor(6) as pool:
            res = list(pool.map(lambda i: _vizier_one(c, spots[i][0], spots[i][1], year), idx))
        return dict(zip(idx, res))

    with ThreadPoolExecutor(max(1, len(todo))) as pool:
        futs = {c: pool.submit(run, c, idx) for c, idx in todo.items()}
        for c, f in futs.items():
            try:
                for i, m in f.result().items():
                    matches[i][c] = m
                    new[key(c, spots[i])] = m
            except Exception as e:  # noqa: BLE001 - reported, not counted as "not there"
                print(f"catalogue check {c} failed: {str(e)[:160]}", flush=True)
                failed.append(c)
                for m in matches:
                    m.pop(c, None)
    if new:
        with _lock:
            try:
                cache = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                cache = {}
            cache.update(new)
            path.parent.mkdir(exist_ok=True)
            tmp = path.with_suffix(".part")
            tmp.write_text(json.dumps(cache), encoding="utf-8")
            tmp.replace(path)
    return {"matches": matches, "failed": failed}


ORDER = {"new": 0, "other": 1, "untyped": 1, "known": 2}


def tag(items: list, res: dict, expects=None) -> list:
    """T128: each item gets "catalogues" ({cat: match | None}, checked ones only) and "tag": "new" (in none of them),
    "other" (SIMBAD type not among `expects`; any type when there are none), "untyped" (only in Gaia / WISE /
    2MASS: catalogued without a type), "known" (SIMBAD type among `expects`; "galaxies" = every galaxy type).
    Returned in that order (new, other / untyped, known), the strength order kept inside each group."""
    from .chemistry import GALAXY_OTYPES
    exp = set(GALAXY_OTYPES) if expects == "galaxies" else set(expects or ())
    for it, m in zip(items, res["matches"]):
        it["catalogues"] = m
        sim = m.get("simbad")
        it["tag"] = ("known" if sim and sim["otype"] in exp else "other" if sim
                     else "untyped" if any(m.values()) else "new")
    return sorted(items, key=lambda it: ORDER[it["tag"]])
