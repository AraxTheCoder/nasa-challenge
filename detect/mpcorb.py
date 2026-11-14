"""T51: known asteroids from a local copy of the MPC orbit catalogue, no web service per field.

    python -m detect.mpcorb fetch      # download MPCORB.DAT.gz (~95 MB, MPC updates it daily)
    python -m detect.mpcorb build      # -> data/mpcorb/orbits.npz (~1.6 M asteroids)
    python -m detect.mpcorb find data/targets/<id>    # what would be found, with timings

Per field:
1. Coarse: two-body (Kepler) positions of every asteroid at each visit, vectorised; keep those
   within the field radius + COARSE_MARGIN_DEG that could be brighter than the magnitude limit.
   Two-body drifts by arcminutes over a year from the catalogue epoch, hence the wide margin.
2. Fine, candidates only: integrate from the catalogue epoch to every frame time with the Sun and
   the eight planets (RK4, 1-day steps, planet positions from astropy's built-in ephemeris), light
   time, seen from SPHEREx (its geocentric position from JPL Horizons, one request per field; the
   geocentre if that fails). Checked against JPL Horizons: see tasks/T51.
3. Objects with a position inside the field and V <= vmag_lim (H, G magnitude) are kept.

T53: comets from CometEls.txt the same way (perihelion elements, elliptic or hyperbolic two-body for
the start state, then the same n-body step; no non-gravitational forces). Their total magnitude
m = H + 5 log(delta) + 2.5 K log(r) is for the whole coma, so the limit is COMET_MAG_SLACK looser.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path("data/mpcorb")
MPCORB_URL = "https://minorplanetcenter.net/iau/MPCORB/MPCORB.DAT.gz"
COMETS_URL = "https://minorplanetcenter.net/iau/MPCORB/CometEls.txt"
COMET_MARGIN_DEG = 2.0            # comets: two-body search without the per-epoch trick (only ~1000)
COMET_MAG_SLACK = 1.0
# Two-body vs n-body after 388 days (ecliptic field, 3116 objects): median 0.010 deg, 99% 0.027 deg,
# worst 0.73 deg, all near-Earth objects (planet encounters). Margin per object accordingly.
COARSE_MARGIN_DEG = 0.15
COARSE_MARGIN_NEO_DEG = 1.5
NEO_Q_AU = 1.3
GROUP_GAP_DAYS = 30               # visits closer than this (one epoch) share one coarse pass
K_GAUSS = 0.01720209895           # AU^1.5 / day
GM_SUN = K_GAUSS ** 2             # AU^3 / day^2
# Sun / planet mass ratios (IAU 2009 / DE430); the Moon is its own body
MASS_RATIO = {"mercury": 6023657.33, "venus": 408523.719, "earth": 332946.0487, "moon": 27068703.24,
              "mars": 3098703.59, "jupiter": 1047.348644, "saturn": 3497.901768,
              "uranus": 22902.98, "neptune": 19412.26}
OBLIQUITY_J2000 = math.radians(84381.448 / 3600)
C_AU_PER_DAY = 173.1446326846693
KM_PER_AU = 149597870.7
TT_MINUS_UTC_DAYS = 69.184 / 86400   # 37 leap seconds + 32.184 s (valid 2017 to at least 2026)

_cache: dict | None = None


# ---------- catalogue ----------

def _unpack_epoch(s: str) -> float:
    """MPC packed date, e.g. 'K2669' -> JD 2461200.5 (2026-06-09.0 TT)."""
    def v(c: str) -> int:
        return int(c) if c.isdigit() else ord(c) - ord("A") + 10
    year = {"I": 1800, "J": 1900, "K": 2000}[s[0]] + int(s[1:3])
    month, day = v(s[3]), v(s[4])
    a = (14 - month) // 12
    y, m = year + 4800 - a, month + 12 * a - 3
    jdn = day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    return jdn - 0.5


def display_name(readable: str) -> str:
    """'(433) Eros' -> '433 Eros'; '(428715) 2008 RG38' -> '428715 (2008 RG38)'; '2023 UC67' -> '(2023 UC67)'.
    Same forms as JPL sb_ident uses, so detect.known_objects.horizons_command understands them."""
    readable = readable.strip()
    if readable.startswith("("):
        num, _, rest = readable[1:].partition(")")
        rest = rest.strip()
        if rest[:4].isdigit() and " " in rest:   # provisional designation, no name
            return f"{num} ({rest})"
        return f"{num} {rest}".strip()
    return f"({readable})"


def build(src: Path = ROOT / "MPCORB.DAT.gz", out: Path = ROOT / "orbits.npz") -> int:
    cols = {k: [] for k in ("H", "G", "epoch", "M", "w", "node", "inc", "e", "n", "a")}
    names = []
    started = False
    with gzip.open(src, "rt", encoding="ascii", errors="replace") as f:
        for line in f:
            if not started:
                started = line.startswith("-----")
                continue
            if len(line) < 103 or not line[8:13].strip():
                continue   # blank separator lines; objects without H are useless here
            try:
                row = (float(line[8:13]), float(line[14:19] or 0.15), _unpack_epoch(line[20:25]),
                       float(line[26:35]), float(line[37:46]), float(line[48:57]), float(line[59:68]),
                       float(line[70:79]), float(line[80:91]), float(line[92:103]))
            except (ValueError, KeyError):
                continue
            for k, v in zip(cols, row):
                cols[k].append(v)
            names.append(display_name(line[166:194]))
    arrays = {k: np.asarray(v, dtype=np.float64) for k, v in cols.items()}
    arrays["G"][~np.isfinite(arrays["G"])] = 0.15
    retrieved = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(src.stat().st_mtime))
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + ".part.npz")   # replaced atomically: a running server may be reading
    np.savez(tmp, name=np.asarray(names, dtype="S"), retrieved_utc=np.asarray(retrieved), **arrays)
    tmp.replace(out)
    reload()
    return len(names)


def _calendar_jd(year: int, month: int, day: float) -> float:
    a = (14 - month) // 12
    y, m = year + 4800 - a, month + 12 * a - 3
    return int(day) + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045 - 0.5 + (day - int(day))


def build_comets(src: Path = ROOT / "CometEls.txt", out: Path = ROOT / "comets.npz") -> int:
    """MPC one-line comet elements -> npz (q, e, perihelion JD, angles, epoch, H, K, name)."""
    cols = {k: [] for k in ("q", "e", "tp", "w", "node", "inc", "epoch", "H", "K")}
    names = []
    for line in src.read_text(encoding="ascii", errors="replace").splitlines():
        if len(line) < 103:
            continue
        try:
            tp = _calendar_jd(int(line[14:18]), int(line[19:21]), float(line[22:29]))
            ep = line[81:89].strip()
            epoch = _calendar_jd(int(ep[:4]), int(ep[4:6]), float(ep[6:8])) if ep else tp
            row = (float(line[30:39]), float(line[41:49]), tp, float(line[51:59]), float(line[61:69]),
                   float(line[71:79]), epoch, float(line[91:95] or 99), float(line[96:100] or 4.0))
        except ValueError:
            continue
        for k, v in zip(cols, row):
            cols[k].append(v)
        names.append(line[102:158].strip())
    tmp = out.with_name(out.stem + ".part.npz")
    np.savez(tmp, name=np.asarray(names, dtype="S"), **{k: np.asarray(v, float) for k, v in cols.items()})
    tmp.replace(out)
    reload()
    return len(names)


_comets: dict | None = None


def load_comets(root: Path = ROOT) -> dict | None:
    global _comets
    if _comets is None and (root / "comets.npz").is_file():
        with np.load(root / "comets.npz") as z:
            d = {k: z[k] for k in z.files}
        d["P"], d["Q"] = _rotation(d["w"], d["node"], d["inc"])
        _comets = d
    return _comets


def comet_state(c: dict, idx, jd_tt: float, velocity: bool = False):
    """Heliocentric equatorial position (3, N) [and velocity] of comets, two-body from perihelion."""
    q, e, dt = c["q"][idx], c["e"][idx], jd_tt - c["tp"][idx]
    P, Q = c["P"][:, idx], c["Q"][:, idx]
    x, y = np.zeros(len(q)), np.zeros(len(q))
    vx, vy = np.zeros(len(q)), np.zeros(len(q))
    ell = e < 1
    if ell.any():                                       # elliptic: Kepler
        a = q[ell] / (1 - e[ell]); ee = e[ell]
        n = K_GAUSS / a ** 1.5
        M = np.remainder(n * dt[ell] + np.pi, 2 * np.pi) - np.pi
        E = M + ee * np.sin(M)
        for _ in range(30):
            E = E - (E - ee * np.sin(E) - M) / (1 - ee * np.cos(E))
        b = a * np.sqrt(1 - ee * ee)
        x[ell], y[ell] = a * (np.cos(E) - ee), b * np.sin(E)
        edot = n / (1 - ee * np.cos(E))
        vx[ell], vy[ell] = -a * np.sin(E) * edot, b * np.cos(E) * edot
    hyp = ~ell
    if hyp.any():                                       # hyperbolic (and e = 1, nudged): e sinh H - H = M
        ee = np.maximum(e[hyp], 1 + 1e-9)
        a = q[hyp] / (ee - 1)
        n = K_GAUSS / a ** 1.5
        M = n * dt[hyp]
        H = np.arcsinh(M / ee)
        for _ in range(50):
            H = H - (ee * np.sinh(H) - H - M) / (ee * np.cosh(H) - 1)
        b = a * np.sqrt(ee * ee - 1)
        x[hyp], y[hyp] = a * (ee - np.cosh(H)), b * np.sinh(H)
        hdot = n / (ee * np.cosh(H) - 1)
        vx[hyp], vy[hyp] = -a * np.sinh(H) * hdot, b * np.cosh(H) * hdot
    r = P * x + Q * y
    return (r, P * vx + Q * vy) if velocity else r


def reload() -> None:
    """Forget the in-memory catalogues; the next lookup loads the files again (after a refresh)."""
    global _cache, _comets
    _cache = _comets = None


def fetch(root: Path = ROOT) -> None:
    """Download MPCORB.DAT.gz and CometEls.txt into root (each replaced atomically)."""
    root.mkdir(parents=True, exist_ok=True)
    for url, name in ((MPCORB_URL, "MPCORB.DAT.gz"), (COMETS_URL, "CometEls.txt")):
        part = root / (name + ".part")
        urllib.request.urlretrieve(url, part)
        part.replace(root / name)


def age_days(root: Path = ROOT) -> float | None:
    f = root / "orbits.npz"
    return (time.time() - f.stat().st_mtime) / 86400 if f.is_file() else None


def available(root: Path = ROOT) -> bool:
    return (root / "orbits.npz").is_file()


def load(root: Path = ROOT) -> dict:
    global _cache
    if _cache is None:
        with np.load(root / "orbits.npz") as z:
            d = {k: z[k] for k in z.files}
        d["q"] = d["a"] * (1 - d["e"])
        d["P"], d["Q"] = _rotation(d["w"], d["node"], d["inc"])   # once, not per time
        _cache = d
    return _cache


# ---------- two-body ----------

def _rotation(w, node, inc):
    """Columns P, Q of the orbit -> ecliptic rotation, then -> equatorial (J2000)."""
    w, node, inc = np.radians(w), np.radians(node), np.radians(inc)
    cw, sw, cn, sn, ci, si = np.cos(w), np.sin(w), np.cos(node), np.sin(node), np.cos(inc), np.sin(inc)
    P = np.stack([cw * cn - sw * sn * ci, cw * sn + sw * cn * ci, sw * si])
    Q = np.stack([-sw * cn - cw * sn * ci, -sw * sn + cw * cn * ci, cw * si])
    ce, se = math.cos(OBLIQUITY_J2000), math.sin(OBLIQUITY_J2000)
    to_eq = np.array([[1, 0, 0], [0, ce, -se], [0, se, ce]])
    return to_eq @ P, to_eq @ Q


def kepler_state(el: dict, idx, jd_tt: float, velocity: bool = False):
    """Heliocentric equatorial position (3, N) in AU [and velocity, AU/day] at jd_tt, two-body."""
    a, e, n = el["a"][idx], el["e"][idx], np.radians(el["n"][idx])
    M = np.radians(el["M"][idx]) + n * (jd_tt - el["epoch"][idx])
    M = np.remainder(M + np.pi, 2 * np.pi) - np.pi
    E = M + e * np.sin(M)
    for _ in range(5):
        E = E - (E - e * np.sin(E) - M) / (1 - e * np.cos(E))
    hi = np.flatnonzero(e > 0.6)               # the few very eccentric orbits converge slower
    if len(hi):
        Eh, eh, Mh = E[hi], e[hi], M[hi]
        for _ in range(15):
            Eh = Eh - (Eh - eh * np.sin(Eh) - Mh) / (1 - eh * np.cos(Eh))
        E[hi] = Eh
    cE, sE = np.cos(E), np.sin(E)
    b = a * np.sqrt(1 - e * e)
    P, Q = (el["P"][:, idx], el["Q"][:, idx]) if "P" in el else _rotation(el["w"][idx], el["node"][idx], el["inc"][idx])
    r = P * (a * (cE - e)) + Q * (b * sE)
    if not velocity:
        return r
    edot = n / (1 - e * cE)
    v = P * (-a * sE * edot) + Q * (b * cE * edot)
    return r, v


# ---------- planets + n-body ----------

def _planet_table(jd_lo: float, jd_hi: float, step: float = 0.25):
    """Heliocentric equatorial positions of the perturbers on a time grid, for interpolation."""
    from astropy.time import Time
    from astropy.coordinates import get_body_barycentric
    grid = np.arange(jd_lo - 1, jd_hi + 1 + step, step)
    t = Time(grid, format="jd", scale="tt")
    sun = get_body_barycentric("sun", t).xyz.to_value("AU")
    pos = {b: get_body_barycentric(b, t).xyz.to_value("AU") - sun for b in MASS_RATIO}
    return grid, pos


class Perturbers:
    def __init__(self, jd_lo: float, jd_hi: float):
        self.grid, self.pos = _planet_table(jd_lo, jd_hi)
        self.gm = {b: GM_SUN / r for b, r in MASS_RATIO.items()}

    def at(self, jd: float) -> dict:
        i = int(np.clip(np.searchsorted(self.grid, jd) - 1, 0, len(self.grid) - 2))
        f = (jd - self.grid[i]) / (self.grid[i + 1] - self.grid[i])
        return {b: p[:, i] * (1 - f) + p[:, i + 1] * f for b, p in self.pos.items()}

    def accel(self, r: np.ndarray, jd: float) -> np.ndarray:
        """Heliocentric acceleration (3, N): Sun + planets, with the indirect term."""
        acc = -GM_SUN * r / np.sum(r * r, axis=0) ** 1.5
        for b, rp in self.at(jd).items():
            d = rp[:, None] - r
            acc += self.gm[b] * (d / np.sum(d * d, axis=0) ** 1.5 - (rp / np.dot(rp, rp) ** 1.5)[:, None])
        return acc


def _rk4(r, v, jd, h, pert: Perturbers):
    k1v = pert.accel(r, jd); k1r = v
    k2v = pert.accel(r + 0.5 * h * k1r, jd + 0.5 * h); k2r = v + 0.5 * h * k1v
    k3v = pert.accel(r + 0.5 * h * k2r, jd + 0.5 * h); k3r = v + 0.5 * h * k2v
    k4v = pert.accel(r + h * k3r, jd + h); k4r = v + h * k3v
    return r + h / 6 * (k1r + 2 * k2r + 2 * k3r + k4r), v + h / 6 * (k1v + 2 * k2v + 2 * k3v + k4v)


def propagate(r0: np.ndarray, v0: np.ndarray, epoch: float, jds_tt: list[float], step: float = 1.0) -> dict:
    """n-body (Sun + planets) from heliocentric states (3, N) at `epoch` to each jd_tt: {jd: (r, v)}."""
    pert = Perturbers(min(min(jds_tt), epoch), max(max(jds_tt), epoch))
    out = {}
    for direction in (1, -1):
        targets = sorted((j for j in jds_tt if (j - epoch) * direction >= 0), key=lambda j: (j - epoch) * direction)
        r, v, jd = r0.copy(), v0.copy(), epoch
        for target in targets:
            while (target - jd) * direction > 1e-9:
                h = direction * min(step, abs(target - jd))
                r, v = _rk4(r, v, jd, h, pert)
                jd += h
            out[target] = (r.copy(), v.copy())
    return out


def integrate(el: dict, idx, jds_tt: list[float], step: float = 1.0) -> dict[float, tuple]:
    """Heliocentric (r, v) of asteroids idx at each jd_tt, n-body from their catalogue epochs
    (grouped: nearly all of MPCORB shares one epoch, a few hundred objects do not)."""
    idx = np.asarray(idx)
    out = {jd: (np.zeros((3, len(idx))), np.zeros((3, len(idx)))) for jd in jds_tt}
    for epoch in np.unique(el["epoch"][idx]):
        sel = np.flatnonzero(el["epoch"][idx] == epoch)
        r0, v0 = kepler_state(el, idx[sel], float(epoch), velocity=True)
        for jd, (r, v) in propagate(r0, v0, float(epoch), jds_tt, step).items():
            out[jd][0][:, sel], out[jd][1][:, sel] = r, v
    return out


def _earth_helio(jds_tt) -> np.ndarray:
    from astropy.time import Time
    from astropy.coordinates import get_body_barycentric
    t = Time(np.atleast_1d(jds_tt), format="jd", scale="tt")
    return (get_body_barycentric("earth", t).xyz - get_body_barycentric("sun", t).xyz).to_value("AU")


def _vmag(H, G, r_helio, delta):
    """IAU H, G magnitude; r_helio and delta as (3, N) vectors in AU (object - Sun, object - observer)."""
    r, d = np.linalg.norm(r_helio, axis=0), np.linalg.norm(delta, axis=0)
    cos_a = np.clip(np.sum(r_helio * delta, axis=0) / (r * d), -1, 1)
    ta = np.tan(np.arccos(cos_a) / 2)
    phi1, phi2 = np.exp(-3.33 * ta ** 0.63), np.exp(-1.87 * ta ** 1.22)
    return H + 5 * np.log10(r * d) - 2.5 * np.log10((1 - G) * phi1 + G * phi2)


def _radec(vec):
    ra = np.degrees(np.arctan2(vec[1], vec[0])) % 360
    dec = np.degrees(np.arctan2(vec[2], np.hypot(vec[0], vec[1])))
    return ra, dec


def _unit(ra_deg, dec_deg):
    ra, dec = np.radians(ra_deg), np.radians(dec_deg)
    return np.array([np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)])


# ---------- the step ----------

def candidates(el: dict, centre: np.ndarray, radius_deg: float, visit_jds_tt: list[float],
               vmag_lim: float) -> np.ndarray:
    """Indices of asteroids that may be in the field at some visit (two-body, wide margin)."""
    # Brightest an object can ever get: perihelion, and as close to Earth as that allows.
    q = el["q"]
    dmin = np.maximum(q - 1.0167, 0.003)
    bright_enough = el["H"] + 5 * np.log10(np.maximum(q, 0.05) * dmin) <= vmag_lim + 0.5
    idx = np.flatnonzero(bright_enough)
    # 1. One pass per group of visits (an epoch): search radius widened by how far each object
    #    can move in half the group's span; magnitude without phase (a lower bound) at that time.
    jds = sorted(visit_jds_tt)
    groups, cur = [], [jds[0]]
    for j in jds[1:]:
        if j - cur[-1] > GROUP_GAP_DAYS:
            groups.append(cur)
            cur = []
        cur.append(j)
    groups.append(cur)
    keep = np.zeros(len(idx), bool)
    for g in groups:
        mid, half = (g[0] + g[-1]) / 2, (g[-1] - g[0]) / 2
        r, v = kepler_state(el, idx, mid, velocity=True)
        d = r - _earth_helio([mid])[:, :1]
        dist = np.linalg.norm(d, axis=0)
        ang = np.degrees(np.arccos(np.clip(centre @ d / dist, -1, 1)))
        rate = np.degrees((np.linalg.norm(v, axis=0) + 0.0175) / dist)        # deg/day, upper bound
        margin = np.where(el["q"][idx] < NEO_Q_AU, COARSE_MARGIN_NEO_DEG, COARSE_MARGIN_DEG)
        near = ang <= radius_deg + margin + rate * half
        vmin = el["H"][idx] + 5 * np.log10(np.linalg.norm(r, axis=0) * np.maximum(dist - rate * half * 0, 1e-3))
        keep |= near & (vmin <= vmag_lim + 1.0)
    idx = idx[keep]
    # 2. Exact two-body at every visit for the few left.
    margin = np.where(el["q"][idx] < NEO_Q_AU, COARSE_MARGIN_NEO_DEG, COARSE_MARGIN_DEG)
    cos_lim = np.cos(np.radians(radius_deg + margin))
    keep = np.zeros(len(idx), bool)
    earth = _earth_helio(visit_jds_tt)
    for k, jd in enumerate(visit_jds_tt):
        d = kepler_state(el, idx, jd) - earth[:, k:k + 1]
        keep |= (centre @ d) / np.linalg.norm(d, axis=0) >= cos_lim
    return idx[keep]


def _name(arr, i: int) -> str:
    n = arr[i]
    return n.decode() if isinstance(n, bytes) else str(n)


def _track(frames, frame_jd, states, earth, observer_km, grid, mag_fn, vmag_lim, names) -> list[dict]:
    """Positions inside the field per object, light time + observer; kept if bright enough once."""
    tracks: dict[int, list[dict]] = {}
    bright: set[int] = set()
    for f in frames:
        jd = frame_jd[f["id"]]
        r, v = states[jd]
        obs = earth[jd].copy()
        if observer_km and f["mjd"] in observer_km:
            obs = obs + np.asarray(observer_km[f["mjd"]]) / KM_PER_AU
        d = r - obs[:, None]
        tau = np.linalg.norm(d, axis=0) / C_AU_PER_DAY      # light time: where it was when the light left
        d = d - v * tau
        ra, dec = _radec(d)
        x, y = grid.to_xy(ra, dec)
        x, y = np.asarray(x, float), np.asarray(y, float)
        vm = mag_fn(r - v * tau, d)
        for k in np.flatnonzero(np.isfinite(x) & np.isfinite(y)):
            if not grid.contains(float(x[k]), float(y[k])):
                continue
            tracks.setdefault(k, []).append(
                {"frame_id": f["id"], "ra_deg": round(float(ra[k]), 6), "dec_deg": round(float(dec[k]), 6),
                 "x": round(float(x[k]), 2), "y": round(float(y[k]), 2)})
            if vm[k] <= vmag_lim:
                bright.add(k)
    return [{"name": names(k), "source": "mpcorb", "synthetic": False, "positions": pos}
            for k, pos in tracks.items() if k in bright]


def comet_candidates(c: dict, centre: np.ndarray, radius_deg: float, visit_jds_tt: list[float]) -> np.ndarray:
    idx = np.arange(len(c["q"]))
    keep = np.zeros(len(idx), bool)
    earth = _earth_helio(visit_jds_tt)
    cos_lim = math.cos(math.radians(radius_deg + COMET_MARGIN_DEG))
    for k, jd in enumerate(visit_jds_tt):
        d = comet_state(c, idx, jd) - earth[:, k:k + 1]
        keep |= (centre @ d) / np.linalg.norm(d, axis=0) >= cos_lim
    return idx[keep]


def find(target: dict, vmag_lim: float, observer_km: dict[float, list[float]] | None = None,
         grid=None) -> list[dict]:
    """known_objects for a target dict from the local catalogues (same format as known_objects.py).

    observer_km: SPHEREx geocentric position (km) per frame mjd (UTC); missing -> geocentre."""
    from pipeline.labels import Grid
    from .known_objects import group_visits

    el = load()
    grid = grid or Grid(target)
    frames = target["frames"]
    c = target["center"]
    centre = _unit(c["ra_deg"], c["dec_deg"])
    visits = group_visits(frames)
    visit_jds = [(v[0]["mjd"] + v[-1]["mjd"]) / 2 + 2400000.5 + TT_MINUS_UTC_DAYS for v in visits]
    frame_jd = {f["id"]: f["mjd"] + 2400000.5 + TT_MINUS_UTC_DAYS for f in frames}
    jds = sorted(set(frame_jd.values()))
    earth = dict(zip(jds, _earth_helio(jds).T))
    found = []

    idx = candidates(el, centre, grid.radius_deg, visit_jds, vmag_lim)
    if len(idx):
        states = integrate(el, idx, jds)
        found += _track(frames, frame_jd, states, earth, observer_km, grid,
                        lambda rh, d: _vmag(el["H"][idx], el["G"][idx], rh, d), vmag_lim,
                        lambda k: _name(el["name"], int(idx[k])))

    co = load_comets()
    cidx = comet_candidates(co, centre, grid.radius_deg, visit_jds) if co is not None else []
    for epoch in np.unique(co["epoch"][cidx]) if len(cidx) else []:
        sel = cidx[co["epoch"][cidx] == epoch]
        r0, v0 = comet_state(co, sel, float(epoch), velocity=True)
        states = propagate(r0, v0, float(epoch), jds)
        found += _track(frames, frame_jd, states, earth, observer_km, grid,
                        lambda rh, d, sel=sel: co["H"][sel] + 5 * np.log10(np.linalg.norm(d, axis=0))
                        + 2.5 * co["K"][sel] * np.log10(np.linalg.norm(rh, axis=0)),
                        vmag_lim + COMET_MAG_SLACK, lambda k, sel=sel: _name(co["name"], int(sel[k])))
    return sorted(found, key=lambda o: o["name"])


def provenance() -> dict:
    el = load()
    co = load_comets()
    n_comets = f" + {len(co['name'])} comets ({COMETS_URL})" if co is not None else ""
    return {"service": "MPC orbit catalogue MPCORB.DAT (local copy; n-body to frame times, T51)",
            "query": f"{MPCORB_URL}; {len(el['name'])} asteroids{n_comets}; coarse two-body search, then Sun + 8 planets RK4",
            "retrieved_utc": str(el["retrieved_utc"])}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m detect.mpcorb", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch")
    sub.add_parser("build")
    f = sub.add_parser("find")
    f.add_argument("target_dir", type=Path)
    f.add_argument("--vmag", type=float, default=20.0)
    args = ap.parse_args(argv)
    ROOT.mkdir(parents=True, exist_ok=True)
    if args.cmd == "fetch":
        fetch()
        for name in ("MPCORB.DAT.gz", "CometEls.txt"):
            print(f"downloaded {name}: {(ROOT / name).stat().st_size / 1e6:.1f} MB")
    elif args.cmd == "build":
        t0 = time.time()
        print(f"{build()} asteroids -> {ROOT / 'orbits.npz'} in {time.time() - t0:.0f} s")
        if (ROOT / "CometEls.txt").is_file():
            print(f"{build_comets()} comets -> {ROOT / 'comets.npz'}")
    else:
        t = json.loads((args.target_dir / "target.json").read_text(encoding="utf-8"))
        t0 = time.time()
        load()
        t1 = time.time()
        objs = find(t, args.vmag)
        print(f"load {t1 - t0:.2f} s, find {time.time() - t1:.2f} s: {len(objs)} object(s)")
        for o in objs:
            print(f"  {o['name']:<32} {len(o['positions'])} frame(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
