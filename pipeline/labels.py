"""T19: catalogue labels for a target, propagated to each frame's time (CONTRACTS v0.4 `labels`).

Sources:
- SIMBAD (names, object types, proper motions; positions at J2000). The main CDS host is sometimes
  down, so official mirrors are tried in order.
- Gaia DR3 at ESA (positions at J2016.0 + proper motions), brighter than GAIA_MAX_G.
- T52: VSX (AAVSO variable-star index, via VizieR): variable type, period and range as `note`.
- T52: CatWISE2020 (IRSA): sources red in W1-W2 (brown dwarfs) or with a significant proper motion,
  each moved from its own mean epoch.
- T52: planets and bright moons: astropy positions decide whether one is near; JPL Horizons gives
  its position seen from SPHEREx (the Moon is ~1 deg off from Earth's centre in low Earth orbit).

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
TIMEOUT_S = 15  # per mirror; a hanging host must not eat the build (T38)
VIZIER_ASU = ("https://vizier.cfa.harvard.edu/viz-bin/asu-tsv",   # CDS answered 'page unavailable' 2026-11-14
              "https://vizier.cds.unistra.fr/viz-bin/asu-tsv")
VSX_CAP = 150
VSX_MAX_MAG = 17.0            # SPHEREx single frames reach roughly here for point sources
CATWISE_CAP = 150
CATWISE_RED_W1W2 = 1.0        # brown dwarf colours; quasars reach ~1 too, but they do not move
CATWISE_MIN_PM = 0.1          # arcsec/yr, and at least CATWISE_PM_SIGMA sigma: nearby brown dwarfs all move
CATWISE_PM_SIGMA = 5
# Bright stars leave fake CatWISE sources with fake motions around them (Barnard's Star: dozens, 1-6"/yr):
# none within min(GLARE_MAX_ARCSEC, GLARE_ARCSEC * 10**((GLARE_G - G) / 5)) of a Gaia star with G < GLARE_G.
GLARE_G, GLARE_ARCSEC, GLARE_MAX_ARCSEC = 10.0, 45.0, 150.0
GLARE_W2 = 9.0                # the same around sources bright in WISE (Eps Ind B is faint for Gaia)
CATWISE_TWIN_ARCSEC = 30.0    # CatWISE splits fast movers into several sources; one label per object
# ... and around a fast star (Barnard's: 9 fake "brown dwarfs" moving 7-9"/yr within 3') it finds
# copies moving at a similar rate: dropped within this distance if the rate is within a factor 2.
CATWISE_ECHO_ARCSEC = 180.0
# Real sources are seen in most WISE visits with a clean motion fit; the fakes around Barnard's Star in
# 4-5 of 12 (nW2/mW2), the one near Eps Ind B has chi2pm = 208.
CATWISE_MIN_SEEN = 0.5
CATWISE_MAX_CHI2PM = 10.0
# Planets (Horizons IDs) and moons bright enough to see, by host; SEARCH: how close the host must be
PLANETS = {"moon": ("301", "Moon"), "mercury": ("199", "Mercury"), "venus": ("299", "Venus"), "mars": ("499", "Mars"),
           "jupiter": ("599", "Jupiter"), "saturn": ("699", "Saturn"), "uranus": ("799", "Uranus"),
           "neptune": ("899", "Neptune")}
MOONS = {"jupiter": [("501", "Io"), ("502", "Europa"), ("503", "Ganymede"), ("504", "Callisto")],
         "saturn": [("602", "Enceladus"), ("603", "Tethys"), ("604", "Dione"), ("605", "Rhea"), ("606", "Titan"),
                    ("608", "Iapetus")],
         "uranus": [("703", "Titania"), ("704", "Oberon")], "neptune": [("801", "Triton")],
         "mars": [("401", "Phobos"), ("402", "Deimos")]}
PLANET_SEARCH_DEG = 1.5       # Moon parallax from low Earth orbit (~1.1 deg) + moons' distance from host
# VSX type -> words (prefix match, longest first)
VSX_TYPES = {"M": "Mira variable", "SR": "semiregular variable", "L": "irregular variable", "EA": "eclipsing binary",
             "EB": "eclipsing binary", "EW": "eclipsing binary", "E": "eclipsing binary", "RR": "RR Lyrae variable",
             "DCEP": "Cepheid", "CEP": "Cepheid", "CW": "type II Cepheid", "DSCT": "delta Scuti variable",
             "HADS": "delta Scuti variable", "ROT": "rotating variable", "BY": "rotating variable (spots)",
             "RS": "RS CVn variable", "INS": "young irregular variable", "INT": "T Tauri variable",
             "IN": "young irregular variable", "TTS": "T Tauri variable", "YSO": "young star", "UV": "flare star",
             "UG": "dwarf nova", "NL": "nova-like variable", "N": "nova", "ZZ": "pulsating white dwarf",
             "GDOR": "gamma Doradus variable", "ACV": "alpha2 CVn variable", "ELL": "ellipsoidal variable",
             "S": "short-period variable", "VAR": "variable star", "MISC": "variable star", "LPV": "long-period variable",
             "RV": "RV Tauri variable", "GCAS": "gamma Cas variable", "BE": "Be star variable", "SXPHE": "SX Phe variable"}
VSX_SURVEY_PREFIXES = ("ASASSN", "ZTF", "ATO ", "CSS_", "NSVS", "ROTSE", "MASTER", "OGLE", "KIC", "TIC", "EPIC",
                       "PS1", "WISE", "Gaia", "2MASS", "SDSS", "TCP", "GDS", "SWASP", "HAT", "KELT", "ASAS ",
                       "NSV ", "USNO", "UCAC", "LINEAR", "CRTS", "CzeV", "MGAB", "VSX ")

# SIMBAD otype -> words for the UI. Unknown types pass through unchanged.
KIND = {
    "*": "star", "PM*": "high proper-motion star", "BD*": "brown dwarf", "BD?": "brown dwarf candidate",
    "V*": "variable star", "BY*": "variable star", "RS*": "variable star", "Mi*": "Mira variable",
    "LP*": "long-period variable", "RR*": "RR Lyrae variable", "EB*": "eclipsing binary",
    "SB*": "spectroscopic binary", "**": "double star", "WD*": "white dwarf", "WD?": "white dwarf candidate",
    "Or*": "young variable star", "TT*": "T Tauri star", "Y*O": "young star", "Pe*": "peculiar star",
    "G": "galaxy", "QSO": "quasar", "AGN": "active galaxy", "X": "X-ray source", "Neb": "nebula",
    "LM*": "low-mass star", "LM?": "low-mass star candidate", "LSB": "low-surface-brightness galaxy",
    "IR": "infrared source", "Em*": "emission-line star", "Ce*": "Cepheid variable", "dS*": "delta Scuti variable",
    "C*": "carbon star", "S*": "S-type star", "RG*": "red giant", "AB*": "AGB star", "HB*": "horizontal-branch star",
    "Be*": "Be star", "HS*": "hot subdwarf", "s*b": "blue supergiant", "s*r": "red supergiant",
    "GiG": "galaxy in a group", "GiC": "galaxy in a cluster", "GrG": "group of galaxies", "ClG": "galaxy cluster",
    "SyG": "Seyfert galaxy", "Sy1": "Seyfert 1 galaxy", "Sy2": "Seyfert 2 galaxy", "bCG": "blue compact galaxy",
    "EmG": "emission-line galaxy", "rG": "radio galaxy", "Rad": "radio source", "mR": "radio source",
    "HH": "Herbig-Haro object", "MoC": "molecular cloud", "DNe": "dark nebula", "RNe": "reflection nebula",
    "HII": "HII region", "PN": "planetary nebula", "OpC": "open cluster", "GlC": "globular cluster",
    "Cl*": "star cluster", "As*": "stellar association", "UV": "UV source", "gam": "gamma-ray source",
    "Mas": "maser", "OH*": "OH/IR star", "CV*": "cataclysmic variable", "No*": "nova", "SN*": "supernova",
    "Psr": "pulsar", "XB*": "X-ray binary", "Ae*": "Herbig Ae/Be star", "Ro*": "rotating variable",
    "Pu*": "pulsating variable", "Ir*": "irregular variable", "El*": "ellipsoidal variable",
    "FIR": "far-infrared source", "MIR": "mid-infrared source", "NIR": "near-infrared source",
    "smm": "submillimetre source", "mm": "millimetre source", "cm": "radio source", "Opt": "optical source",
    "blu": "blue object", "EmO": "emission-line object", "PoC": "part of a cloud", "SFR": "star-forming region",
    "PoG": "part of a galaxy", "IG": "interacting galaxies", "PaG": "pair of galaxies", "BiC": "brightest galaxy in a cluster",
}
# Types worth a name on the image even when the SIMBAD name looks like a catalogue number.
NOTABLE_OTYPES = {"BD*", "BD?", "PM*", "WD*", "Mi*", "LP*", "Ce*", "RR*", "TT*", "Or*", "Y*O", "QSO", "AGN",
                  "SN*", "No*", "CV*", "XB*", "Psr", "PN", "HH", "Ae*", "Sy1", "Sy2", "SyG"}
FIELD_OBJECT_ARCSEC = 15.0   # the SIMBAD object nearest the requested centre within this = "the field's object"
MERGE_ARCSEC = 3.0           # labels closer than this (~0.5 px) are one object on the image
SIMBAD_CAP = 400             # T38: SIMBAD objects kept per field, ranked (deep fields have ~30,000)
# Classic designations that read as names (stars and bright galaxies), ranked above survey names.
CLASSIC_PREFIXES = ("NAME ", "V* ", "* ", "HD ", "HIP ", "HR ", "BD", "CD-", "CPD", "GJ ", "LHS ", "LP ", "Ross ",
                    "Wolf ", "G ", "NGC ", "IC ", "M ", "UGC ", "PGC ", "Mrk ", "3C ", "PN ", "HH ", "IRAS ")
GAIA_CAP = 400               # T38: brightest Gaia stars kept per field
SKIP_OTYPES = {"Pl", "Pl?"}  # exoplanets are not separately visible
# Catalogue-number names; everything else counts as a "real" name the UI shows by default.
SURVEY_PREFIXES = ("Gaia", "2MASS", "TYC", "UCAC", "WISE", "[", "SDSS", "GALEX", "LAMOST", "ATO ", "GES ",
                   "USNO", "LEDA", "GAT ", "1RXS", "Z ", "ZTF", "PM ", "UGCA", "NVSS", "FIRST", "APOP", "CRTS",
                   # T72: more survey numbers that crowded the map
                   "2dFGRS", "6dFGS", "2MASX", "GALEX", "SSS_", "4FGL", "3FGL", "2E ", "1E ", "PMN ", "SUMSS",
                   "WISEA", "CWISE", "UCAC4", "UCAC2", "GSC", "NSV ", "2XMM", "4XMM", "XMMU", "CXOU", "RX J",
                   "PS1", "Pan-STARRS", "DES ", "SSTSL2", "IRAS ", "AKARI", "MCG", "ESO ", "APMUKS", "HIPASS")


def _tap(url: str, adql: str) -> dict:
    """Run an ADQL query, return {column: numpy masked array} (columns lower-case).
    Column arrays, not row dicts: deep fields return ~30,000 SIMBAD rows (T38)."""
    import numpy as np
    from astropy.io.votable import parse_single_table

    r = requests.post(url.rstrip("/") + "/sync", timeout=TIMEOUT_S,
                      data={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "votable", "QUERY": adql})
    r.raise_for_status()
    table = parse_single_table(io.BytesIO(r.content)).to_table()
    return {c.lower(): np.ma.asarray(table[c]) for c in table.colnames}


def _num(a):
    """Masked/NaN -> 0.0 float array, plus a 'had a value' mask."""
    import numpy as np
    a = np.ma.asarray(a, dtype=float)
    ok = ~np.ma.getmaskarray(a) & np.isfinite(a.filled(np.nan))
    return np.where(ok, a.filled(0.0), 0.0), ok


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

    def to_xy(self, ra, dec):
        """Scalars or arrays; contract pixels: y down, origin at the top-left pixel centre."""
        x, y = self.wcs.world_to_pixel_values(ra, dec)
        return x, self.h - 1 - y

    def contains(self, x, y, margin: float = 2):
        return (x >= -margin) & (x <= self.w - 1 + margin) & (y >= -margin) & (y <= self.h - 1 + margin)


def _tracks(grid: Grid, frames: list[dict], ra, dec, pmra, pmdec, epoch_mjd):
    """All objects x all frames at once: positions moved by proper motion (linear, parallax ignored).
    epoch_mjd: one epoch for all, or one per object (CatWISE).
    Returns (RA, Dec, x, y) arrays of shape (n_objects, n_frames) and the 'inside the field' mask."""
    import numpy as np
    epoch = np.asarray(epoch_mjd, float)
    epoch = epoch[:, None] if epoch.ndim else epoch
    yrs = (np.array([f["mjd"] for f in frames])[None, :] - epoch) / 365.25      # (F,) or (N, F)
    ra, dec = np.asarray(ra, float)[:, None], np.asarray(dec, float)[:, None]   # (N, 1)
    R = ra + np.asarray(pmra, float)[:, None] * yrs / 3.6e6 / np.cos(np.radians(dec))
    D = dec + np.asarray(pmdec, float)[:, None] * yrs / 3.6e6
    X, Y = grid.to_xy(R.ravel(), D.ravel())
    X, Y = X.reshape(R.shape), Y.reshape(R.shape)
    inside = grid.contains(X, Y).any(axis=1)
    return R, D, X, Y, inside


def _positions(frames, R, D, X, Y, i) -> list[dict]:
    return [{"frame_id": f["id"], "ra_deg": round(float(R[i, k]), 6), "dec_deg": round(float(D[i, k]), 6),
             "x": round(float(X[i, k]), 2), "y": round(float(Y[i, k]), 2)} for k, f in enumerate(frames)]


def simbad_labels(target: dict, grid: Grid) -> tuple[list[dict], dict | None]:
    import numpy as np
    c = target["center"]
    adql = (f"SELECT main_id, ra, dec, pmra, pmdec, otype FROM basic WHERE "
            f"CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {c['ra_deg']}, {c['dec_deg']}, {grid.radius_deg:.5f})) = 1")
    errors = []
    for url in SIMBAD_TAP:
        try:
            cols = _tap(url, adql)
        except Exception as e:  # a down mirror must not break the build
            errors.append(f"{url}: {str(e)[:80]}")
            continue
        prov = {"service": "SIMBAD TAP " + url, "query": adql, "retrieved_utc": _now()}
        if not len(cols.get("main_id", [])):
            return [], prov
        ids = np.array([str(x) for x in cols["main_id"].filled("")])
        otype = np.array([str(x) for x in cols["otype"].filled("")])
        ra, ok_pos = _num(cols["ra"]); dec, _ = _num(cols["dec"])
        pmra, has_pm = _num(cols["pmra"]); pmdec, _ = _num(cols["pmdec"])
        keep = ok_pos & ~np.isin(otype, list(SKIP_OTYPES))
        idx = np.nonzero(keep)[0]
        R, D, X, Y, inside = _tracks(grid, target["frames"], ra[idx], dec[idx], pmra[idx], pmdec[idx], J2000_MJD)
        idx, R, D, X, Y = idx[inside], R[inside], D[inside], X[inside], Y[inside]
        named = np.array([not n.startswith(SURVEY_PREFIXES) for n in ids[idx]], dtype=bool)
        notable = np.isin(otype[idx], list(NOTABLE_OTYPES))
        pm = np.hypot(pmra[idx], pmdec[idx])
        classic = np.array([n.startswith(CLASSIC_PREFIXES) for n in ids[idx]], dtype=bool)
        d2 = (X[:, 0] - (grid.w - 1) / 2) ** 2 + (Y[:, 0] - (grid.h - 1) / 2) ** 2
        centre_px = FIELD_OBJECT_ARCSEC / target["image"]["pixel_scale_arcsec"]
        # T38 ranking + cap: deep fields return ~30,000 objects (COSMOS), most of them faint galaxies
        # with survey names. Always kept: notable proper motion, the object at the centre. Then by tier,
        # nearest the centre first, up to SIMBAD_CAP in total.
        tier = np.select([(has_pm[idx] & (pm >= 100)) | (d2 <= centre_px ** 2), notable, classic, named],
                         [0, 1, 2, 3], default=4)
        order = np.lexsort((d2, tier))
        rows = order[(tier[order] == 0) | (np.arange(len(order)) < SIMBAD_CAP)]
        labels = []
        for j in rows:
            i = idx[j]
            name = ids[i].replace("NAME ", "").replace("V* ", "").strip()
            labels.append({"name": name, "kind": KIND.get(otype[i], otype[i]), "otype": otype[i],
                           "source": "simbad", "named": bool(named[j]), "mag": None,
                           "pm_mas_yr": round(float(pm[j]), 1) if has_pm[i] else None,
                           "positions": _positions(target["frames"], R, D, X, Y, j)})
        prov["note"] = f"{len(idx)} SIMBAD objects in the field, {len(labels)} kept (cap {SIMBAD_CAP}, ranked)"
        return labels, prov
    print("SIMBAD unavailable, no names this time:", "; ".join(errors))
    return [], None


def gaia_labels(target: dict, grid: Grid) -> tuple[list[dict], dict | None]:
    import numpy as np
    c = target["center"]
    adql = (f"SELECT TOP {GAIA_CAP * 3} source_id, ra, dec, pmra, pmdec, phot_g_mean_mag FROM gaiadr3.gaia_source WHERE "
            f"1 = CONTAINS(POINT(ra, dec), CIRCLE({c['ra_deg']}, {c['dec_deg']}, {grid.radius_deg:.5f})) "
            f"AND phot_g_mean_mag < {GAIA_MAX_G} ORDER BY phot_g_mean_mag")
    try:
        cols = _tap(GAIA_TAP, adql)
    except Exception as e:
        print("Gaia unavailable:", str(e)[:120])
        return [], None
    prov = {"service": "Gaia DR3 TAP (ESA) " + GAIA_TAP, "query": adql, "retrieved_utc": _now()}
    if not len(cols.get("source_id", [])):
        return [], prov
    ra, _ = _num(cols["ra"]); dec, _ = _num(cols["dec"])
    pmra, has_pm = _num(cols["pmra"]); pmdec, _ = _num(cols["pmdec"])
    gmag, _ = _num(cols["phot_g_mean_mag"])
    sid = cols["source_id"].filled(0)
    R, D, X, Y, inside = _tracks(grid, target["frames"], ra, dec, pmra, pmdec, J2016_MJD)
    rows = np.nonzero(inside)[0][:GAIA_CAP]  # already sorted by brightness
    labels = []
    for i in rows:
        labels.append({"name": f"Gaia DR3 {int(sid[i])}", "kind": "star", "otype": "*", "source": "gaia_dr3",
                       "named": False, "mag": round(float(gmag[i]), 2),
                       "_at_epoch": {"ra_deg": float(ra[i]), "dec_deg": float(dec[i])},   # J2016, for _drop_glare
                       "pm_mas_yr": round(float(np.hypot(pmra[i], pmdec[i])), 1) if has_pm[i] else None,
                       "positions": _positions(target["frames"], R, D, X, Y, i)})
    return labels, prov


def _asu(params: dict) -> tuple[list[dict], str]:
    """VizieR ASU tab-separated query, mirrors in order. Rows as dicts of strings, plus the URL used.
    A value of None sends a bare flag (`-out.all`; `-out.all=` returns no rows)."""
    from urllib.parse import urlencode
    query = "&".join([urlencode({k: v for k, v in params.items() if v is not None})]
                     + [k for k, v in params.items() if v is None])
    errors = []
    for url in VIZIER_ASU:
        try:
            r = requests.get(f"{url}?{query}", timeout=TIMEOUT_S)
            r.raise_for_status()
            if "<html" in r.text[:200].lower():
                raise ValueError("HTML instead of a table (host down)")
        except Exception as e:  # noqa: BLE001 - next mirror
            errors.append(f"{url}: {str(e)[:80]}")
            continue
        lines = [ln for ln in r.text.splitlines() if ln and not ln.startswith("#")]
        if len(lines) < 3:
            return [], url
        head = [h.strip() for h in lines[0].split("\t")]
        rows = [dict(zip(head, (c.strip() for c in ln.split("\t")))) for ln in lines[3:]]   # 1: units, 2: dashes
        return rows, url
    raise ConnectionError("; ".join(errors))


def _simbad_by_id(names: list[str]) -> dict[str, tuple[float, float, float, float]]:
    """name -> (ra, dec, pmra, pmdec) at J2000 from SIMBAD, trying 'V* name' and 'name'. {} if down."""
    import numpy as np
    if not names:
        return {}
    ids = {}
    for n in names:
        ids[f"V* {n}"] = n
        ids[n] = n
    quoted = ", ".join("'" + i.replace("'", "''") + "'" for i in ids)
    adql = (f"SELECT i.id, b.ra, b.dec, b.pmra, b.pmdec FROM ident AS i JOIN basic AS b ON i.oidref = b.oid "
            f"WHERE i.id IN ({quoted})")
    for url in SIMBAD_TAP:
        try:
            cols = _tap(url, adql)
        except Exception:  # noqa: BLE001 - next mirror
            continue
        out = {}
        found = [str(x) for x in cols.get("id", np.ma.array([])).filled("")]
        ra, ok = _num(cols["ra"]) if found else ([], [])
        if not found:
            return out
        dec, _ = _num(cols["dec"]); pmra, _ = _num(cols["pmra"]); pmdec, _ = _num(cols["pmdec"])
        for k, i in enumerate(found):
            if ok[k] and ids.get(i):
                out[ids[i]] = (float(ra[k]), float(dec[k]), float(pmra[k]), float(pmdec[k]))
        return out
    return {}


def _vsx_kind(vtype: str) -> str:
    t = vtype.upper().lstrip(":").split("|")[0].split("+")[0].rstrip(":")
    for k in sorted(VSX_TYPES, key=len, reverse=True):
        if t.startswith(k):
            return VSX_TYPES[k]
    return "variable star"


def _float(s: str):
    try:
        return float(s.strip("()<>: "))
    except (ValueError, AttributeError):
        return None


def vsx_labels(target: dict, grid: Grid) -> tuple[list[dict], dict | None]:
    """T52: variable stars from VSX. No proper motions in VSX: positions are J2000 (the SIMBAD twin,
    which has them, wins in merge_duplicates and keeps this label's note)."""
    import numpy as np
    c = target["center"]
    params = {"-source": "B/vsx/vsx", "-c": f"{c['ra_deg']:.6f} {c['dec_deg']:+.6f}", "-c.rd": f"{grid.radius_deg:.5f}",
              "-out": "Name,RAJ2000,DEJ2000,Type,max,n_max,f_min,min,Period", "-out.max": str(VSX_CAP * 4), "-sort": "max"}
    try:
        rows, url = _asu(params)
    except Exception as e:  # noqa: BLE001
        print("VSX unavailable:", str(e)[:160])
        return [], None
    prov = {"service": "VSX (AAVSO) via VizieR " + url, "query": json.dumps(params), "retrieved_utc": _now()}
    rows = [r for r in rows if _float(r.get("RAJ2000")) is not None]
    rows = [r for r in rows if (_float(r.get("max")) or 99) <= VSX_MAX_MAG or not r["Name"].startswith(VSX_SURVEY_PREFIXES)]
    if not rows:
        return [], prov
    ra = np.array([_float(r["RAJ2000"]) for r in rows]); dec = np.array([_float(r["DEJ2000"]) for r in rows])
    pmra, pmdec = np.zeros(len(rows)), np.zeros(len(rows))
    # VSX has no proper motions: Barnard's Star (V2500 Oph) would sit 4.5' from where it is now.
    # SIMBAD knows most VSX names (GCVS ones as 'V* <name>'): its J2000 position + proper motion.
    sim = _simbad_by_id([r["Name"].strip() for r in rows])
    for i, r in enumerate(rows):
        hit = sim.get(r["Name"].strip())
        if hit:
            ra[i], dec[i], pmra[i], pmdec[i] = hit
    R, D, X, Y, inside = _tracks(grid, target["frames"], ra, dec, pmra, pmdec, J2000_MJD)
    labels = []
    for i in np.nonzero(inside)[0][:VSX_CAP]:
        r = rows[i]
        kind = _vsx_kind(r.get("Type", ""))
        hi, lo, per = _float(r.get("max")), r.get("min", ""), _float(r.get("Period"))
        bits = [kind + (f" ({r['Type']})" if r.get("Type") else "")]
        if per:
            bits.append(f"period {per:.4g} d")
        if hi is not None and lo:
            lo_v = _float(lo)
            if lo.startswith("(") or r.get("f_min", "").strip() in ("Y", "("):   # VSX: min is an amplitude
                bits.append(f"max {hi:g} mag, amplitude {lo_v:g}" if lo_v is not None else f"max {hi:g} mag")
            elif lo_v is not None:
                bits.append(f"range {hi:g} to {lo_v:g} mag")
        name = r["Name"].strip()
        labels.append({"name": name, "kind": kind, "otype": "V*", "source": "vsx",
                       "named": not name.startswith(VSX_SURVEY_PREFIXES), "mag": hi,
                       "mag_band": (r.get("n_max") or "V").strip() or "V",
                       "pm_mas_yr": None, "note": ", ".join(bits),
                       "positions": _positions(target["frames"], R, D, X, Y, i)})
    return labels, prov


def catwise_labels(target: dict, grid: Grid) -> tuple[list[dict], dict | None]:
    """T52: CatWISE2020 sources that are very red in W1-W2 (brown dwarf colours) or move measurably;
    each is moved from its own mean observation epoch (~2015) to the frame times. Via VizieR (the IRSA
    TAP query took over 15 s on 2026-11-14, VizieR ~2 s); the colour/motion cut is applied here."""
    import numpy as np
    c = target["center"]
    params = {"-source": "II/365/catwise", "-c": f"{c['ra_deg']:.6f} {c['dec_deg']:+.6f}",
              "-c.rd": f"{grid.radius_deg:.5f}", "W2mproPM": "<16", "-out.max": "3000",
              "-out.all": None}   # a column list (-out=...) returns no rows for this table on the CfA mirror
    try:
        rows, url = _asu(params)
    except Exception as e:  # noqa: BLE001
        print("CatWISE unavailable:", str(e)[:160])
        return [], None
    prov = {"service": "CatWISE2020 (II/365) via VizieR " + url, "query": json.dumps(params), "retrieved_utc": _now()}
    vals = []
    for r in rows:
        ra, dec, mjd, w2 = (_float(r.get(k)) for k in ("RAPMdeg", "DEPMdeg", "MJD", "W2mproPM"))
        if None in (ra, dec, mjd, w2):
            continue
        pmra, pmde = _float(r.get("pmRA")) or 0.0, _float(r.get("pmDE")) or 0.0      # arcsec/yr
        sig = math.hypot(_float(r.get("e_pmRA")) or 9, _float(r.get("e_pmDE")) or 9)
        w1 = _float(r.get("W1mproPM"))
        colour = None if w1 is None else w1 - w2
        pm = math.hypot(pmra, pmde)
        red = colour is None or colour >= CATWISE_RED_W1W2
        moving = pm >= CATWISE_MIN_PM and pm >= CATWISE_PM_SIGMA * sig
        artefact = any(ch.isupper() for ch in r.get("ccf", "")) or r.get("abf", "00").strip() not in ("", "00")
        n_seen, n_max, chi2 = _float(r.get("nW2")), _float(r.get("mW2")), _float(r.get("chi2pm"))
        if n_seen is not None and n_max and n_seen < CATWISE_MIN_SEEN * n_max:
            artefact = True
        if chi2 is not None and chi2 > CATWISE_MAX_CHI2PM:
            artefact = True
        if not artefact and (w2 < GLARE_W2 or (moving and red)):   # bright ones only for the glare test
            vals.append((r["Name"].strip(), ra, dec, mjd, pmra, pmde, pm, w2, colour, red and moving))
    if not vals:
        return [], prov
    ra, dec, ep, pmra, pmde = (np.array([v[k] for v in vals]) for k in (1, 2, 3, 4, 5))
    R, D, X, Y, inside = _tracks(grid, target["frames"], ra, dec, pmra * 1000, pmde * 1000, ep)
    labels = []
    for i in np.nonzero(inside)[0][:CATWISE_CAP]:
        name, ra0, dec0, _, _, _, pm, w2, colour, red = vals[i]
        if not red:   # only kept as a glare source (see _drop_glare)
            labels.append({"source": "catwise2020-glare", "mag": w2, "_at_epoch": {"ra_deg": ra0, "dec_deg": dec0}})
            continue
        kind = "brown dwarf candidate (red in WISE, moving)"
        note = f"W2 = {w2:.1f}" + (f", W1-W2 = {colour:.1f}" if colour is not None else ", not seen in W1")
        if pm >= CATWISE_MIN_PM:
            note += f", moves {pm:.2f}\u2033/yr"
        labels.append({"name": f"CWISE {name}", "kind": kind, "otype": "BD?" if red else "PM*",
                       "source": "catwise2020", "named": bool(red) or pm >= 0.5,
                       "mag": round(w2, 2), "mag_band": "W2", "pm_mas_yr": round(pm * 1000, 1),
                       "note": note, "positions": _positions(target["frames"], R, D, X, Y, i),
                       "_at_epoch": {"ra_deg": ra0, "dec_deg": dec0}})
    return labels, prov


def planet_labels(target: dict, grid: Grid) -> tuple[list[dict], dict | None]:
    """T52: planets and bright moons. astropy (geocentric) says which hosts are near the field at any
    frame; only those are asked from JPL Horizons, seen from SPHEREx (CENTER 500@-163182)."""
    import numpy as np
    from astropy.coordinates import get_body_barycentric
    from astropy.time import Time

    frames = target["frames"]
    t = Time([f["mjd"] for f in frames], format="mjd", scale="utc")
    earth = get_body_barycentric("earth", t).xyz.to_value("AU")
    c = target["center"]
    centre = np.array([math.cos(math.radians(c["dec_deg"])) * math.cos(math.radians(c["ra_deg"])),
                       math.cos(math.radians(c["dec_deg"])) * math.sin(math.radians(c["ra_deg"])),
                       math.sin(math.radians(c["dec_deg"]))])
    near = []
    for body in PLANETS:
        d = get_body_barycentric(body, t).xyz.to_value("AU") - earth
        ang = np.degrees(np.arccos(np.clip(centre @ d / np.linalg.norm(d, axis=0), -1, 1)))
        if ang.min() <= grid.radius_deg + PLANET_SEARCH_DEG:
            near.append(body)
    if not near:
        return [], None
    from detect.known_objects import MJD_TO_JD, Jpl
    jpl = Jpl()
    jds = [round(f["mjd"] + MJD_TO_JD, 6) for f in frames]
    labels = []
    for body in near:
        for hid, name in [PLANETS[body]] + MOONS.get(body, []):
            try:
                radec = jpl.positions_id(hid, jds)
            except Exception as e:  # noqa: BLE001
                print(f"Horizons: no position for {name}: {str(e)[:100]}")
                continue
            ra = np.array([[p[0] for p in radec]]); dec = np.array([[p[1] for p in radec]])
            X, Y = grid.to_xy(ra.ravel(), dec.ravel())
            X, Y = np.asarray(X).reshape(ra.shape), np.asarray(Y).reshape(ra.shape)
            if not grid.contains(X, Y).any():
                continue
            kind = "planet" if hid.endswith("99") else ("Moon" if hid == "301" else f"moon of {PLANETS[body][1]}")
            labels.append({"name": name, "kind": kind, "otype": "Pla" if kind == "planet" else "Moon",
                           "source": "horizons", "named": True, "mag": None, "pm_mas_yr": None,
                           "note": "position seen from SPHEREx (JPL Horizons)",
                           "positions": _positions(frames, ra, dec, X, Y, 0)})
    prov = {"service": "JPL Horizons (planets and moons, observer: SPHEREx)",
            "query": f"bodies near the field (astropy): {', '.join(near)}; {len(jpl.log)} request(s)",
            "retrieved_utc": _now()}
    return labels, prov


def _drop_glare(labels: list[dict]) -> list[dict]:
    """T52: CatWISE brown-dwarf labels that are artefacts or duplicates. Compared at the catalogue
    epochs (Gaia 2016, CatWISE ~2015), not at frame time: fake motions would scatter them.
    - in the glare of a Gaia star with G < GLARE_G or a WISE source with W2 < GLARE_W2;
    - near a labelled star that moves >= 1"/yr (CatWISE splits fast movers into several sources);
    - near a brighter CatWISE label (the same split)."""
    glare = [(l["_at_epoch"], min(GLARE_MAX_ARCSEC, GLARE_ARCSEC * 10 ** ((lim - l["mag"]) / 5)))
             for l, lim in ((l, GLARE_G if l["source"] == "gaia_dr3" else GLARE_W2) for l in labels
                            if l["source"] in ("gaia_dr3", "catwise2020-glare") and "_at_epoch" in l)
             if l.get("mag") is not None and l["mag"] < lim]
    fast = [(l["positions"][0], l["pm_mas_yr"]) for l in labels if l["source"] in ("simbad", "gaia_dr3")
            and (l.get("pm_mas_yr") or 0) >= 1000]
    out, kept_cw = [], []
    for l in sorted(labels, key=lambda l: (l["source"] == "catwise2020", l.get("mag") or 99)):
        if l["source"] == "catwise2020-glare":
            continue
        if l["source"] == "catwise2020":
            if any(_sep(p, l["_at_epoch"]) <= r for p, r in glare if p is not l["_at_epoch"]):
                continue
            p0, pm = l["positions"][0], l.get("pm_mas_yr") or 0
            if any(_sep(p, p0) <= CATWISE_TWIN_ARCSEC for p in kept_cw):
                continue
            if any(_sep(p, p0) <= CATWISE_ECHO_ARCSEC and 0.5 <= pm / fpm <= 2 for p, fpm in fast):
                continue
            kept_cw.append(l["positions"][0])
        out.append(l)
    for l in out:
        l.pop("_at_epoch", None)
    return out


def _sep(p, q) -> float:
    d = math.radians
    a = (math.sin(d(q["dec_deg"] - p["dec_deg"]) / 2) ** 2 + math.cos(d(p["dec_deg"])) * math.cos(d(q["dec_deg"]))
         * math.sin(d(q["ra_deg"] - p["ra_deg"]) / 2) ** 2)
    return math.degrees(2 * math.asin(min(1.0, math.sqrt(a)))) * 3600


def merge_duplicates(labels: list[dict]) -> list[dict]:
    """One label per object on the image: SIMBAD components (RW Aur, RW Aur A, RW Aur B) and an object's
    Gaia twin closer than MERGE_ARCSEC become `aliases` of the best label (SIMBAD over Gaia, named over
    catalogue numbers, shorter name). The kept label takes the Gaia magnitude if it had none."""
    pref = {"horizons": 0, "simbad": 1, "vsx": 2, "catwise2020": 3, "gaia_dr3": 4}
    order = sorted(labels, key=lambda l: (pref.get(l["source"], 5), not l["named"], len(l["name"])))
    kept: list[dict] = []
    cell = MERGE_ARCSEC / 3600  # bucket size in degrees: only neighbouring buckets can hold a duplicate
    buckets: dict[tuple[int, int], list[dict]] = {}
    for l in order:
        p = l["positions"][0]
        bx = int(math.floor(p["ra_deg"] * math.cos(math.radians(p["dec_deg"])) / cell))
        by = int(math.floor(p["dec_deg"] / cell))
        near = (k for dx in (-1, 0, 1) for dy in (-1, 0, 1) for k in buckets.get((bx + dx, by + dy), ()))
        host = next((k for k in near if _sep(k["positions"][0], p) < MERGE_ARCSEC), None)
        if host is None:
            l.setdefault("aliases", [])
            kept.append(l)
            buckets.setdefault((bx, by), []).append(l)
            continue
        if l["name"] != host["name"] and l["name"] not in host["aliases"]:
            host["aliases"].append(l["name"])
        if host.get("mag") is None and l.get("mag") is not None:
            host["mag"] = l["mag"]
            if l.get("mag_band"):
                host["mag_band"] = l["mag_band"]
        if l.get("note") and not host.get("note"):   # T52: e.g. VSX type/period on the SIMBAD star
            host["note"] = l["note"]
        if not host["named"] and l["named"] and l["source"] in ("simbad", "vsx", "horizons"):  # readable name in front
            if l["name"] in host["aliases"]:
                host["aliases"].remove(l["name"])
            host["aliases"].append(host["name"])
            host["name"], host["named"] = l["name"], True
    return kept


def rank_importance(labels: list[dict], target: dict) -> None:
    """`importance`: 0 = the field's object (nearest SIMBAD object to the requested centre), 1 = notable
    motion, 2 = notable type or a real name, 3 = catalogue-number SIMBAD object, 4 = Gaia-only star.
    The viewer always names the most important few and shows the rest on hover (T34)."""
    c = {"ra_deg": target["center"]["ra_deg"], "dec_deg": target["center"]["dec_deg"]}
    sim = [l for l in labels if l["source"] == "simbad"]
    near = min(sim, key=lambda l: _sep(c, l["positions"][0]), default=None)
    for l in labels:
        moving = (l.get("motion") or {}).get("class") not in (None, "still")
        if l is near and _sep(c, near["positions"][0]) <= FIELD_OBJECT_ARCSEC:
            l["importance"] = 0
        elif moving or l["source"] == "horizons":
            l["importance"] = 1
        elif l["source"] != "gaia_dr3" and (l["named"] or l["otype"] in NOTABLE_OTYPES):
            l["importance"] = 2
        elif l["source"] != "gaia_dr3":
            l["importance"] = 3
        else:
            l["importance"] = 4


def add_labels(target: dict, sources=None) -> dict:
    """Fill target["labels"] (replacing any old ones) and append provenance. Returns the target.

    Synthetic targets get no labels: real catalogue names on simulated frames would mislead."""
    if target.get("synthetic"):
        target["labels"] = []
        return target
    grid = Grid(target)
    labels = []
    from concurrent.futures import ThreadPoolExecutor
    sources = sources or (simbad_labels, gaia_labels, vsx_labels, catwise_labels, planet_labels)   # T52: + VSX, CatWISE, planets
    with ThreadPoolExecutor(len(sources)) as pool:  # all at the same time: total = the slowest one (T38)
        results = list(pool.map(lambda fn: fn(target, grid), sources))
    for found, prov in results:
        labels += found
        if prov:
            target.setdefault("provenance", []).append(prov)
    labels = _drop_glare(labels)
    from .motion import summarize  # T23: motion summary + class per label
    scale = target["image"]["pixel_scale_arcsec"]
    for l in labels:
        l["motion"] = summarize(l["positions"], target["frames"], scale)
    labels = merge_duplicates(labels)
    rank_importance(labels, target)
    labels.sort(key=lambda l: (l["importance"], l["mag"] if l["mag"] is not None else 99, l["name"]))
    for i, l in enumerate(labels):
        l["id"] = f"l{i:03d}"
    target["labels"] = labels
    return target


# ---------- T72: labels for any patch of the sky map (no field built) ----------

SKY_CELL_DEG = 0.25           # requests snap to this grid, so nearby views share one cache entry
SKY_RADII = (0.25, 0.5, 1.0)  # degrees
SKY_MJD = 61041.0             # 2026-01-01, the middle of the SPHEREx survey so far; the map combines epochs


def sky_region(ra: float, dec: float, radius: float) -> tuple[float, float, float]:
    """Snap a request to the cache grid: (ra, dec, radius)."""
    r = next((x for x in SKY_RADII if x >= radius), SKY_RADII[-1])
    dec_s = max(-90.0, min(90.0, round(dec / SKY_CELL_DEG) * SKY_CELL_DEG))
    step = SKY_CELL_DEG / max(math.cos(math.radians(dec_s)), 0.05)
    return round((round(ra / step) * step) % 360, 4), round(dec_s, 4), r


def sky_labels(ra: float, dec: float, radius: float) -> dict:
    """Labels around (ra, dec) for the map: SIMBAD, Gaia (only to merge and filter, not returned),
    VSX and CatWISE, at SKY_MJD. Compact rows instead of per-frame positions."""
    scale = 6.15
    npix = int(radius * 2 ** 0.5 * 3600 / scale)          # Grid radius = half the diagonal = radius
    t = {"id": "sky", "synthetic": False, "center": {"ra_deg": ra, "dec_deg": dec},
         "image": {"width": npix, "height": npix, "pixel_scale_arcsec": scale},
         "frames": [{"id": "s0", "mjd": SKY_MJD, "epoch": 1}], "labels": [], "provenance": []}
    add_labels(t, sources=(simbad_labels, gaia_labels, vsx_labels, catwise_labels))
    rows = []
    for l in t["labels"]:
        if l["source"] == "gaia_dr3":
            continue
        p = l["positions"][0]
        # Drawing order on the map (the client names the first ones that fit): famous objects and fast
        # movers, then other real names, then catalogue numbers; brighter first within each.
        name = " ".join(l["name"].split())              # SIMBAD pads: "M  31"
        pm = l.get("pm_mas_yr") or 0
        notable = ((l["otype"] in NOTABLE_OTYPES or pm >= 100) and l["named"]) or pm >= 1000 \
            or name.startswith("* ") or l["source"] == "catwise2020"
        tier = 0 if name.startswith(("M ", "NGC ", "IC ")) else 1 if notable else 2 if l["named"] else 3
        rows.append({k: v for k, v in {
            "name": name, "kind": l["kind"], "otype": l["otype"], "source": l["source"],
            "importance": tier, "named": l["named"], "_mag": l.get("mag") if l.get("mag") is not None else 99, "ra_deg": p["ra_deg"], "dec_deg": p["dec_deg"],
            "mag": l.get("mag"), "mag_band": l.get("mag_band"), "pm_mas_yr": l.get("pm_mas_yr"),
            "note": l.get("note"), "aliases": l.get("aliases") or None}.items() if v is not None})
    rows.sort(key=lambda r: (r["importance"], r.pop("_mag")))
    return {"center": {"ra_deg": ra, "dec_deg": dec}, "radius_deg": radius, "mjd": SKY_MJD,
            "labels": rows, "provenance": t["provenance"]}


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
