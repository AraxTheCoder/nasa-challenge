"""T93: chemistry maps. Where in a field does a chemical feature absorb or emit?

    python -m pipeline.chemistry data/targets/<id> h2o_ice      # writes <target>/chemistry/h2o_ice.png + .json

For a feature (water ice at 3.05 µm, PAH at 3.3 µm, Brackett-α at 4.05 µm, ...): the image at the feature's
wavelength minus the continuum, interpolated from images just below and just above it. Ordinary stars and smooth
spectra cancel; what is left is the feature: darker = less light than the neighbouring wavelengths (absorption),
brighter = more (emission). Visualization only (Decision 2026-11-14): nothing is classified.

From the SPHEREx exposures themselves, not the display images: every exposure covering the field whose detector
reaches the feature (field-sized cutouts, cached on disk like T85's), IMAGE − ZODI in MJy/sr, flagged pixels left
out, resampled onto the field's north-up grid. SPHEREx's linear variable filters give every *pixel* its own
wavelength (WCS-WAVE), so pixels are sorted per exposure:

- on the feature:  |λ − λ0| <= w_on       (w_on = max(the feature's half-width, half a channel))
- continuum:       w_on + bw/2 <= |λ − λ0| <= w_on + 3 bw    (bw = the channel width there), below and above,
                   leaving out the bright emission features (PAH, hydrogen lines)

Per pixel the median of each group (robust against cosmic rays and passing asteroids), the continuum linearly
interpolated between the medians below and above to λ0 (one side only: that side), then D = on − continuum.
The map shows D in units of its own robust noise over the field: grey 128 = like the continuum, ±5 sigma = black /
white (asinh, so faint structure stays visible).
"""
from __future__ import annotations

import json
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

import numpy as np

# id: (name, centre µm, half-width µm, kind, what it is). Centres as web/spectrum.js FEATURES (T63) + water bands.
FEATURES = {
    "pa_beta": ("Pa-β", 1.282, 0.0, "line", "hydrogen emission: hot gas around young or hot stars, emission nebulae"),
    "h2o_14": ("H₂O 1.4 µm", 1.40, 0.05, "band", "water in cool atmospheres (M/L/T dwarfs), absorption"),
    "h2o_19": ("H₂O 1.9 µm", 1.90, 0.06, "band", "water in cool atmospheres (M/L/T dwarfs), absorption"),
    "br_gamma": ("Br-γ", 2.166, 0.0, "line", "hydrogen emission: hot gas around young or hot stars, emission nebulae"),
    "h2o_ice": ("H₂O ice", 3.05, 0.08, "ice", "water ice on cold dust grains, seen against the stars behind a cold "
                "cloud. Inside bright nebulae the broad PAH emission (3.2–3.6 µm) raises the continuum: dark there "
                "can mean PAH, not ice"),
    "pah": ("PAH / CH₄", 3.29, 0.03, "band", "PAH molecules glowing in UV light (star-forming regions); methane absorption in cool brown dwarfs"),
    "ch3oh_ice": ("CH₃OH ice", 3.53, 0.03, "ice", "methanol ice on cold dust grains"),
    "br_alpha": ("Br-α", 4.052, 0.0, "line", "hydrogen emission: hot gas around young or hot stars, emission nebulae"),
    "co2_ice": ("CO₂ ice", 4.27, 0.03, "ice", "carbon-dioxide ice on cold dust grains (one of SPHEREx's main science goals)"),
    "co_ice": ("CO", 4.67, 0.03, "ice", "carbon-monoxide ice on very cold grains; CO gas absorbs here in cool atmospheres"),
}
# T107: ready-made combinations for kinds of places, each tried on real fields (tasks/T107). Visualization only
# (Decision 2026-11-14): `looks_for` says where to look, `read` what the colours mean, `caveats` what fools it;
# nothing is classified. Features in wavelength order = colour order (blue, green, red).
PRESETS = [
    {"id": "ionised_gas", "name": "Ionised gas", "features": ["pa_beta", "br_gamma", "br_alpha"],
     "looks_for": "hot hydrogen gas around young or hot stars: emission nebulae, H II regions",
     "read": "Three hydrogen lines. White = gas in the open. Dust dims the short wavelengths most, so the more dust "
             "lies in front, the redder: red alone (Br-α) = gas deep inside a cloud, invisible to the eye.",
     "caveats": "A one-colour halo around a very bright star is the star's light, not gas; the brightest nebula "
                "cores saturate (black).",
     "try": {"name": "Orion Nebula (M42 and M43)", "ra": 83.8221, "dec": -5.3911, "size": 20},
     "tested": "Orion: M42 white, M43 redder; ρ Oph: only Br-α (red) around the embedded star S1"},
    {"id": "cloud_ices", "name": "Ices in cold clouds", "features": ["h2o_ice", "co2_ice", "co_ice"],
     "looks_for": "ice on dust grains in dark clouds, seen against the light behind them",
     "read": "Brighter = deeper absorption. CO₂ (green) and CO (red) together = yellow: the cold dense parts of a "
             "cloud; white = all three ices.",
     "caveats": "Blue alone (water ice) inside a bright nebula is the PAH glow, not ice: trust it where green or "
                "red show too. Straight stripes are exposure edges. A cloud with nothing bright behind it shows nothing.",
     "try": {"name": "ρ Ophiuchi dark cloud (L1688)", "ra": 246.79, "dec": -24.54, "size": 30},
     "tested": "ρ Oph: green/yellow along the dense filaments of the dark cloud; Orion and NGC 7023: blue or green "
               "over the bright nebula (PAH, the caveat)"},
    {"id": "cloud_edge", "name": "Lit cloud edges", "features": ["pah", "br_alpha", "co2_ice"],
     "looks_for": "the layers where starlight meets a cloud: the glowing surface, ionised gas, the icy inside",
     "read": "Blue = PAH glowing in UV light on the lit surfaces, green = ionised gas (Br-α), red = CO₂ ice in the "
             "shielded inside. Blue + green = cyan close to the stars.",
     "caveats": "In the bright cores of big H II regions (Orion) the colours mix and saturate.",
     "try": {"name": "Iris Nebula (NGC 7023)", "ra": 315.40, "dec": 68.17, "size": 20},
     "tested": "NGC 7023: PAH (blue) fills the reflection nebula, ice (red) in the cloud beside it; ρ Oph: ice "
               "inside the cloud, PAH on the side facing the bright stars; Orion: unclear"},
]
# T109: a receding source's features arrive at λ(1 + z). A map can be made at a redshift: the feature window, its
# continuum and the bright lines kept out of it all move. Milky Way objects (|cz| < ~300 km/s) need none; galaxies
# from cz ≈ 1 300 km/s on (Br-α; ~4 000 km/s for PAH and Pa-β) miss the rest-wavelength window without it.
Z_MAX = 1.0
Z_STEP = 1e-4                # z is kept to 4 decimals (30 km/s): the file key, the cache, the layer name
SPHEREX_MAX_UM = 5.02        # the longest wavelength SPHEREx sees (band 6 ends at 5.0 µm)
CONT_CHANNELS = 3.0          # continuum reaches this many channel widths beyond the feature (+ half a channel gap)
SIGMA_SPAN = 5.0             # ±this many sigma = black / white
THREADS = 8
VERSION = 1


def _grid(target: dict):
    from .build import output_wcs
    c = target["center"]
    return output_wcs(c["ra_deg"], c["dec_deg"], int(target["image"]["width"])), int(target["image"]["width"])


def sample_exposure(path: Path, out_w, npix: int):
    """(flux MJy/sr, wavelength µm, bandwidth µm) on the field grid (rows top-down, NaN = no data)."""
    from astropy.io import fits
    from astropy.wcs import WCS
    from scipy.ndimage import map_coordinates

    from .build import HW_MASK, wavelengths_at
    with fits.open(path) as hd:
        img = hd["IMAGE"].data.astype(float)
        if "ZODI" in hd:
            img = img - hd["ZODI"].data
        bad = ((hd["FLAGS"].data.astype(np.int64) & HW_MASK) != 0) | ~np.isfinite(img)
        in_w = WCS(hd["IMAGE"].header)
        yy, xx = np.mgrid[0:npix, 0:npix]
        sra, sdec = out_w.all_pix2world(xx, npix - 1 - yy, 0)
        ix, iy = in_w.all_world2pix(sra, sdec, 0)
        inside = (ix >= 0) & (iy >= 0) & (ix <= img.shape[1] - 1) & (iy <= img.shape[0] - 1)
        wl = np.full(ix.shape, np.nan)
        bw = np.full(ix.shape, np.nan)
        if inside.any():
            w, b = wavelengths_at(hd, ix[inside], iy[inside])
            wl[inside], bw[inside] = w, b
    data = np.where(bad, 0.0, img)
    out = map_coordinates(data, [iy, ix], order=1, mode="constant", cval=np.nan)
    badout = map_coordinates(bad.astype(float), [iy, ix], order=1, mode="constant", cval=1.0) > 0.25
    out[badout | ~inside] = np.nan
    return out, wl, bw


def _other_features(lam0: float, z: float = 0.0):
    """(centre, half-width) of the bright emission features (PAH, hydrogen lines): another feature's continuum
    must not include them (Orion, 2026-11-14: PAH 3.3 µm in the continuum above 3.05 µm painted the PAH filaments
    dark on the water-ice map). Excluding every feature left rows without continuum; ices are weak enough.
    lam0 is observed (shifted) like these, by (1 + z) (T109: the galaxy's own lines move with it)."""
    k = 1.0 + z
    return [(um * k, hw * k) for fid, (_, um, hw, kind, _) in FEATURES.items()
            if abs(um * k - lam0) > 1e-6 and (kind == "line" or fid == "pah")]   # bright emission only


def z_of(z) -> float:
    """z rounded to Z_STEP; ValueError outside 0..Z_MAX."""
    z = float(z or 0.0)
    if not math.isfinite(z) or not 0.0 <= z <= Z_MAX:       # T113: inf / nan before rounding (OverflowError)
        raise ValueError(f"redshift z must be 0 to {Z_MAX:g}")
    z = round(z / Z_STEP) * Z_STEP
    if not 0.0 <= z <= Z_MAX:
        raise ValueError(f"redshift z must be 0 to {Z_MAX:g}")
    return round(z, 4)


def map_key(feature: str, z: float = 0.0) -> str:
    """T109: name of a map's files and layer: the feature id, + "_z<z × 10⁴>" when made at a redshift."""
    zi = round(z_of(z) / Z_STEP)
    return feature if zi == 0 else f"{feature}_z{zi}"


def parse_key(key: str) -> tuple[str, float]:
    """(feature, z) of a map key; ValueError if it names no feature."""
    import re
    m = re.match(r"^([a-z0-9_]+?)(?:_z(\d{1,5}))?$", key or "")
    if not m or m.group(1) not in FEATURES:
        raise ValueError(f"unknown chemistry map {key!r}")
    z = int(m.group(2)) * Z_STEP if m.group(2) else 0.0
    if m.group(2) is not None and (int(m.group(2)) == 0 or z > Z_MAX):
        raise ValueError(f"unknown chemistry map {key!r}")
    return m.group(1), round(z, 4)


def combine(samples, lam0: float, half: float, z: float = 0.0):
    """samples: [(flux, wl, bw)] on one grid -> dict of per-pixel maps: on, cont, diff, n_on, n_blue, n_red.
    lam0, half: the feature as observed (at redshift z, T109)."""
    shape = samples[0][0].shape
    on, blue, red, lb, lr = [], [], [], [], []
    others = _other_features(lam0, z)
    for f, wl, bw in samples:
        ok = np.isfinite(f) & np.isfinite(wl) & np.isfinite(bw)
        w_on = np.maximum(half, bw / 2)
        d = wl - lam0
        is_on = ok & (np.abs(d) <= w_on)
        cont = ok & (np.abs(d) >= w_on + bw / 2) & (np.abs(d) <= w_on + CONT_CHANNELS * bw)
        for um, hw in others:
            cont &= np.abs(wl - um) > np.maximum(hw, bw / 2) + bw / 2
        on.append(np.where(is_on, f, np.nan))
        blue.append(np.where(cont & (d < 0), f, np.nan))
        lb.append(np.where(cont & (d < 0), wl, np.nan))
        red.append(np.where(cont & (d > 0), f, np.nan))
        lr.append(np.where(cont & (d > 0), wl, np.nan))
    with np.errstate(all="ignore"), __import__("warnings").catch_warnings():
        __import__("warnings").simplefilter("ignore", RuntimeWarning)
        med = lambda a: np.nanmedian(np.array(a, np.float32), axis=0) if a else np.full(shape, np.nan)  # noqa: E731
        m_on, m_b, m_r, w_b, w_r = med(on), med(blue), med(red), med(lb), med(lr)
        n = lambda a: np.isfinite(np.array(a, np.float32)).sum(axis=0) if a else np.zeros(shape, int)  # noqa: E731
        n_on, n_b, n_r = n(on), n(blue), n(red)
        both = np.isfinite(m_b) & np.isfinite(m_r) & (w_r > w_b)
        t = np.where(both, (lam0 - w_b) / np.where(both, w_r - w_b, 1), 0.5)
        cont = np.where(both, m_b + t * (m_r - m_b), np.where(np.isfinite(m_b), m_b, m_r))
        diff = m_on - cont
    return {"on": m_on, "cont": cont, "diff": diff, "n_on": n_on, "n_blue": n_b, "n_red": n_r}


def to_grey(diff: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """(grey 0-255, coverage mask, sigma): 128 = like the continuum, darker = absorption, brighter = emission."""
    ok = np.isfinite(diff)
    grey = np.full(diff.shape, 128.0, np.float32)
    if ok.sum() < 20:
        return grey, ok, float("nan")
    v = diff[ok]
    centre, sigma = float(np.median(v)), float(np.std(v)) or 1.0
    for _ in range(5):                                  # clipped: nebulae / bright regions don't set the zero
        keep = np.abs(v - centre) < 3 * sigma
        if keep.sum() < 20:
            break
        centre = float(np.median(v[keep]))
        sigma = float(1.4826 * np.median(np.abs(v[keep] - centre))) or sigma
    z = (diff[ok] - centre) / sigma
    grey[ok] = np.clip(128 + 127 * np.arcsinh(z) / math.asinh(SIGMA_SPAN), 0, 255)
    return grey, ok, sigma


SMOOTH_PX = 0.8              # T121: Gaussian sigma (field pixels, 6.15″) after a 3 × 3 median
HOLE_FILL = 0.6              # T121: a pixel without data is filled when this much of its Gaussian neighbourhood has data


def smooth(grey: np.ndarray, cov: np.ndarray, sigma: float = SMOOTH_PX) -> tuple[np.ndarray, np.ndarray]:
    """T121: a grey map (128 = like the continuum) without its pixel speckle, for display: a 3 × 3 median (single
    hot / cold pixels, star residuals; outside the coverage counts as 128) and a light Gaussian normalised over the
    covered pixels, so edges stay where they are. Holes of a pixel or two inside the coverage are filled from their
    neighbours; big ones (saturated nebula cores) stay empty. Returns (grey, coverage); ~0.4 s for an 86′ field."""
    from scipy.ndimage import gaussian_filter, median_filter
    if sigma <= 0 or not cov.any():
        return grey, cov
    med = median_filter(np.where(cov, grey, 128.0).astype(np.float32), 3, mode="nearest")
    num = gaussian_filter(np.where(cov, med - 128.0, 0.0).astype(np.float32), sigma)
    den = gaussian_filter(cov.astype(np.float32), sigma)
    out_cov = cov | (den >= HOLE_FILL)
    # values also just past the coverage (from the covered neighbours): the map tiles sample bilinearly, and a
    # neutral 128 there would draw a grey rim around holes and edges
    out = np.where(den > 1e-3, 128.0 + num / np.maximum(den, 1e-3), 128.0).astype(np.float32)
    return out, out_cov


def load_map(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """T121: a saved grey map as shown (smoothed): (grey float32, coverage bool); kept in memory per file version."""
    path = Path(path)
    return _load_map(str(path), path.stat().st_mtime, SMOOTH_PX)


@lru_cache(maxsize=32)
def _load_map(path: str, mtime: float, sigma: float):
    from PIL import Image
    a = np.asarray(Image.open(path).convert("LA"), np.float32)
    grey, cov = smooth(a[..., 0], a[..., 1] > 0, sigma)
    grey.flags.writeable = cov.flags.writeable = False          # shared between callers
    return grey, cov


def relevant(exposures, lam0: float, half: float):
    """Exposures whose detector reaches the feature and its continuum (channel ~ λ/40, generous)."""
    reach = half + (CONT_CHANNELS + 1) * lam0 / 35
    return [e for e in exposures if e.wave_min_um - reach <= lam0 <= e.wave_max_um + reach]


def compute(target_dir: Path, feature: str, progress=None, refresh: bool = False, z: float = 0.0) -> dict:
    """Make (or reuse) <target_dir>/chemistry/<key>.png + .json (key = map_key(feature, z)). Returns the stats dict.
    T109: at redshift z every wavelength used is the rest one times (1 + z)."""
    from PIL import Image

    from . import build, photometry
    z = z_of(z)
    key = map_key(feature, z)
    name, lam_rest, half_rest, kind, what = FEATURES[feature]
    lam0, half = lam_rest * (1 + z), half_rest * (1 + z)
    if lam0 - half > SPHEREX_MAX_UM:
        raise LookupError(f"{name} ({lam_rest} µm) arrives at {lam0:.2f} µm at z = {z:g}: beyond SPHEREx's 5 µm")
    out_dir = Path(target_dir) / "chemistry"
    png, meta = out_dir / f"{key}.png", out_dir / f"{key}.json"
    target = json.loads((Path(target_dir) / "target.json").read_text(encoding="utf-8"))
    if not refresh and png.is_file() and meta.is_file():
        old = json.loads(meta.read_text(encoding="utf-8"))
        if old.get("version") == VERSION:
            return old
    t0 = time.time()
    c = target["center"]
    ra, dec = round(c["ra_deg"] % 360, 4), round(c["dec_deg"], 4)
    size_deg = round(target.get("size_arcmin", 15) / 60 + 0.06, 4)
    exposures, prov = build.cached_exposures(ra, dec)
    todo = relevant(exposures, lam0, half)
    out_w, npix = _grid(target)
    samples, used, failed, done = [], [], 0, 0

    def one(e):
        path = photometry._spectrum_cutout(e.fits_url, ra, dec, size_deg)
        return e, sample_exposure(path, out_w, npix)

    with ThreadPoolExecutor(THREADS) as pool:
        for fut in [pool.submit(one, e) for e in todo]:
            try:
                e, s = fut.result()
                if np.isfinite(s[1]).any() and np.nanmin(np.abs(s[1] - lam0)) <= half + (CONT_CHANNELS + 1) * np.nanmax(s[2]):
                    samples.append(s)
                    used.append(e)
            except Exception:  # noqa: BLE001 - a missing / moved image shouldn't stop the map
                failed += 1
            done += 1
            if progress:
                progress(done, len(todo))
    if not samples:
        raise LookupError(f"no SPHEREx exposure reaches {name} ({lam0:.3f} µm) here")
    m = combine(samples, lam0, half, z)
    grey, cov, sigma = to_grey(m["diff"])
    out_dir.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.dstack([grey.round().astype(np.uint8), np.where(cov, 255, 0).astype(np.uint8)]), "LA").save(png)
    epochs = sorted({e.epoch for e in used})
    stats = {
        "version": VERSION, "feature": feature, "key": key, "z": z, "um_observed": round(lam0, 4),
        "name": name, "um": lam_rest, "half_width_um": half_rest, "kind": kind,
        "what": what, "sigma_mjy_sr": round(sigma, 5) if math.isfinite(sigma) else None,
        "coverage": round(float(cov.mean()), 3), "exposures_read": len(todo), "exposures_used": len(used),
        "failed": failed, "epochs": epochs,
        "median_on": int(np.median(m["n_on"][cov])) if cov.any() else 0,
        "median_continuum": int(np.median((m["n_blue"] + m["n_red"])[cov])) if cov.any() else 0,
        "both_sides": round(float(((m["n_blue"] > 0) & (m["n_red"] > 0))[cov].mean()), 3) if cov.any() else 0.0,
        "seconds": round(time.time() - t0, 1), "image": f"chemistry/{key}.png",
        "provenance": [prov, {"service": "SPHEREx level-2 images (field cutouts, AWS S3 / IRSA)",
                              "query": f"{len(todo)} exposures whose detector reaches {lam0:.4f} µm"
                                       f"{f' ({lam_rest} µm at z = {z:g})' if z else ''}; IMAGE − ZODI, "
                                       f"flags out, per-pixel wavelength (WCS-WAVE)",
                              "retrieved_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0))}],
    }
    meta.write_text(json.dumps(stats, indent=1, ensure_ascii=False), encoding="utf-8")
    return stats


# ---------- T109: redshift of the galaxies in a field (SIMBAD) ----------

Z_MIN_GALAXY = 0.001         # below this (cz < 300 km/s) a redshift is a Milky Way velocity: no shift needed
Z_LIST = 8


REDSHIFT_VERSION = 2     # T112: 2 = galaxies only (cached answers of version 1 are asked again)
# SIMBAD object types that are galaxies, quasars or groups / clusters of galaxies (condensed otype codes)
GALAXY_OTYPES = {"G", "G?", "GiC", "GiG", "GiP", "BiC", "IG", "PaG", "PoG", "SBG", "SyG", "Sy1", "Sy2", "AGN", "AG?",
                 "LIN", "QSO", "Q?", "Bla", "Bz?", "BLL", "BL?", "rG", "H2G", "LSB", "bCG", "EmG", "ClG", "C?G", "GrG",
                 "CGG", "LeG", "LeQ", "LeI", "LI?"}


def galaxy_redshifts(target: dict) -> dict:
    """Galaxies with a measured redshift in the field, biggest first (they dominate the map), from SIMBAD
    `basic.rvz_redshift`: {"galaxies": [{name, otype, z, cz_km_s, quality, major_arcmin, sep_arcmin, ra_deg,
    dec_deg}], "provenance": {...} | None}. Network errors: empty list, provenance None."""
    import numpy as np

    from .labels import SIMBAD_TAP, _num, _now, _tap
    c = target["center"]
    r = target.get("size_arcmin", 15) / 60 / math.sqrt(2)
    adql = (f"SELECT TOP 200 main_id, ra, dec, otype, rvz_redshift, rvz_qual, galdim_majaxis FROM basic WHERE "
            f"CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {c['ra_deg']}, {c['dec_deg']}, {r:.5f})) = 1 "
            f"AND rvz_redshift >= {Z_MIN_GALAXY} AND rvz_redshift <= {Z_MAX}")
    for url in SIMBAD_TAP:
        try:
            cols = _tap(url, adql)
        except Exception:  # noqa: BLE001 - next mirror
            continue
        prov = {"service": "SIMBAD TAP " + url, "query": adql, "retrieved_utc": _now()}
        # T112: galaxies only. SIMBAD gives velocities to Milky Way objects too (on ρ Oph the "Ophiuchus Molecular
        # Cloud", otype SFR, z = 0.028 quality D, set z for the whole field and shifted every chemistry map by 2.8 %)
        keep = [i for i, o in enumerate(cols.get("otype", [])) if str(o).strip() in GALAXY_OTYPES]
        cols = {k: v[keep] for k, v in cols.items()}
        n = len(cols.get("main_id", []))
        if not n:
            return {"galaxies": [], "provenance": prov}
        ra, _ = _num(cols["ra"]); dec, _ = _num(cols["dec"])
        z, _ = _num(cols["rvz_redshift"]); maj, has_maj = _num(cols["galdim_majaxis"])
        qual = [str(q) for q in cols["rvz_qual"].filled("")]
        dra = (ra - c["ra_deg"] + 180) % 360 - 180
        sep = 60 * np.hypot(dra * np.cos(np.radians(c["dec_deg"])), dec - c["dec_deg"])
        order = sorted(range(n), key=lambda i: (-(maj[i] if has_maj[i] else 0.0), sep[i]))[:Z_LIST]
        gal = [{"name": " ".join(str(cols["main_id"][i]).replace("NAME ", "").split()), "otype": str(cols["otype"][i]),
                "z": round(float(z[i]), 5), "cz_km_s": round(float(z[i]) * 299792.458),
                "quality": qual[i] or None, "major_arcmin": round(float(maj[i]), 2) if has_maj[i] else None,
                "sep_arcmin": round(float(sep[i]), 2), "ra_deg": round(float(ra[i]), 5),
                "dec_deg": round(float(dec[i]), 5)} for i in order]
        return {"galaxies": gal, "provenance": prov}
    return {"galaxies": [], "provenance": None}


# ---------- T96: several features as one colour picture ----------

# The direction that matters for each feature in a combined picture: the hydrogen lines and PAH glow (emission),
# the ices and the water bands absorb.
SHOWS = {k: "emission" if v[3] == "line" or k == "pah" else "absorption" for k, v in FEATURES.items()}
COMBINE_MAX = len(FEATURES)   # T108: any number (was 3, Mati 2026-11-15)


def _hue_colours(n: int) -> tuple:
    """n colours by wavelength, shortest first. 2 = cyan + red, 3 = blue + green + red (T96): independent, so every
    mix can be read back (red + green = yellow). From 4 on: hues evenly from blue (240°) through cyan, green and
    yellow to red (0°), full brightness; then a mix can look like another feature's own colour."""
    import colorsys
    if n == 2:
        return ((0, 1, 1), (1, 0, 0))
    return tuple(tuple(round(v, 3) for v in colorsys.hsv_to_rgb((240 - 240 * i / (n - 1)) / 360, 1, 1)) for i in range(n))


# Colours by wavelength, shortest first, as in narrow-band images (and T89's false colour: blue short, red long).
COMBINE_COLOURS = {n: _hue_colours(n) for n in range(2, COMBINE_MAX + 1)}
_FLOOR = math.asinh(1.0) / math.asinh(SIGMA_SPAN)    # 1 noise level in the grey maps' stretch: weaker = black


def combo(features) -> list[str]:
    """2 or more distinct known map keys (features, T109: at one redshift) in wavelength order (the order of their
    colours); ValueError otherwise."""
    fs = list(dict.fromkeys(features))
    parsed = [parse_key(f) for f in fs]                   # ValueError for unknown names
    if not 2 <= len(fs) <= COMBINE_MAX or len({p[0] for p in parsed}) != len(fs):
        raise ValueError(f"combine 2 to {COMBINE_MAX} different features of: {', '.join(FEATURES)}")
    if len({p[1] for p in parsed}) != 1:
        raise ValueError("one picture, one redshift: all its maps must be made at the same z")
    return sorted(fs, key=lambda f: FEATURES[parse_key(f)[0]][1])


def strength(grey: np.ndarray, shows: str) -> np.ndarray:
    """0-1 from a grey map (128 = like the continuum): how far the feature emits (shows = "emission") or absorbs
    ("absorption") beyond 1 noise level, in the map's asinh stretch (1 = SIGMA_SPAN noise levels or more)."""
    s = (grey - 128.0) / 127.0 if shows == "emission" else (128.0 - grey) / 128.0
    return np.clip((s - _FLOOR) / (1.0 - _FLOOR), 0.0, 1.0)


def combined_map(target_dir: Path, features) -> tuple[np.ndarray, np.ndarray]:
    """(RGB uint8 (h, w, 3), coverage) of 2 or more features' maps, which compute() made first (LookupError if not).
    Each feature adds its colour times its strength; coverage = where all of them have data. T121: from the
    smoothed maps (load_map)."""
    fs = combo(features)
    rgb = cov = None
    for f, colour in zip(fs, COMBINE_COLOURS[len(fs)]):
        p = Path(target_dir) / "chemistry" / f"{f}.png"
        feat = parse_key(f)[0]
        if not p.is_file():
            raise LookupError(f"no {FEATURES[feat][0]} map made yet")
        grey, has = load_map(p)
        s = strength(grey, SHOWS[feat])
        if rgb is None:
            rgb, cov = np.zeros(s.shape + (3,), np.float32), np.ones(s.shape, bool)
        if s.shape != cov.shape:
            raise LookupError("the maps were made on different grids (field rebuilt?): make them again")
        rgb += s[..., None] * np.asarray(colour, np.float32)
        cov &= has
    return np.clip(rgb * 255.0, 0, 255).round().astype(np.uint8), cov


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2 or args[1] not in FEATURES:
        print(f"usage: python -m pipeline.chemistry data/targets/<id> <{'|'.join(FEATURES)}>", file=sys.stderr)
        return 2
    s = compute(Path(args[0]), args[1], progress=lambda d, t: print(f"\r{d}/{t}", end="", flush=True), refresh=True)
    print(f"\n{s['name']}: {s['exposures_used']} exposures (median {s['median_on']} on the feature, "
          f"{s['median_continuum']} continuum per pixel), sigma {s['sigma_mjy_sr']} MJy/sr, {s['seconds']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
