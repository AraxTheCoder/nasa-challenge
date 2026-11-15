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


def _other_features(lam0: float):
    """(centre, half-width) of the bright emission features (PAH, hydrogen lines): another feature's continuum
    must not include them (Orion, 2026-11-14: PAH 3.3 µm in the continuum above 3.05 µm painted the PAH filaments
    dark on the water-ice map). Excluding every feature left rows without continuum; ices are weak enough."""
    return [(um, hw) for fid, (_, um, hw, kind, _) in FEATURES.items()
            if abs(um - lam0) > 1e-6 and (kind == "line" or fid == "pah")]   # bright emission only


def combine(samples, lam0: float, half: float):
    """samples: [(flux, wl, bw)] on one grid -> dict of per-pixel maps: on, cont, diff, n_on, n_blue, n_red."""
    shape = samples[0][0].shape
    on, blue, red, lb, lr = [], [], [], [], []
    others = _other_features(lam0)
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


def relevant(exposures, lam0: float, half: float):
    """Exposures whose detector reaches the feature and its continuum (channel ~ λ/40, generous)."""
    reach = half + (CONT_CHANNELS + 1) * lam0 / 35
    return [e for e in exposures if e.wave_min_um - reach <= lam0 <= e.wave_max_um + reach]


def compute(target_dir: Path, feature: str, progress=None, refresh: bool = False) -> dict:
    """Make (or reuse) <target_dir>/chemistry/<feature>.png + .json. Returns the stats dict."""
    from PIL import Image

    from . import build, photometry
    name, lam0, half, kind, what = FEATURES[feature]
    out_dir = Path(target_dir) / "chemistry"
    png, meta = out_dir / f"{feature}.png", out_dir / f"{feature}.json"
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
        raise LookupError(f"no SPHEREx exposure reaches {name} ({lam0} µm) here")
    m = combine(samples, lam0, half)
    grey, cov, sigma = to_grey(m["diff"])
    out_dir.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.dstack([grey.round().astype(np.uint8), np.where(cov, 255, 0).astype(np.uint8)]), "LA").save(png)
    epochs = sorted({e.epoch for e in used})
    stats = {
        "version": VERSION, "feature": feature, "name": name, "um": lam0, "half_width_um": half, "kind": kind,
        "what": what, "sigma_mjy_sr": round(sigma, 5) if math.isfinite(sigma) else None,
        "coverage": round(float(cov.mean()), 3), "exposures_read": len(todo), "exposures_used": len(used),
        "failed": failed, "epochs": epochs,
        "median_on": int(np.median(m["n_on"][cov])) if cov.any() else 0,
        "median_continuum": int(np.median((m["n_blue"] + m["n_red"])[cov])) if cov.any() else 0,
        "both_sides": round(float(((m["n_blue"] > 0) & (m["n_red"] > 0))[cov].mean()), 3) if cov.any() else 0.0,
        "seconds": round(time.time() - t0, 1), "image": f"chemistry/{feature}.png",
        "provenance": [prov, {"service": "SPHEREx level-2 images (field cutouts, AWS S3 / IRSA)",
                              "query": f"{len(todo)} exposures whose detector reaches {lam0} µm; IMAGE − ZODI, "
                                       f"flags out, per-pixel wavelength (WCS-WAVE)",
                              "retrieved_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0))}],
    }
    meta.write_text(json.dumps(stats, indent=1, ensure_ascii=False), encoding="utf-8")
    return stats


# ---------- T96: several features as one colour picture ----------

# The direction that matters for each feature in a combined picture: the hydrogen lines and PAH glow (emission),
# the ices and the water bands absorb.
SHOWS = {k: "emission" if v[3] == "line" or k == "pah" else "absorption" for k, v in FEATURES.items()}
COMBINE_MAX = 3
# Colours by wavelength, shortest first, as in narrow-band images (and T89's false colour: blue short, red long):
# two = cyan + red, three = blue + green + red. Overlaps mix: red + green = yellow, all three = white.
COMBINE_COLOURS = {2: ((0, 1, 1), (1, 0, 0)), 3: ((0, 0, 1), (0, 1, 0), (1, 0, 0))}
_FLOOR = math.asinh(1.0) / math.asinh(SIGMA_SPAN)    # 1 noise level in the grey maps' stretch: weaker = black


def combo(features) -> list[str]:
    """2-3 distinct known features in wavelength order (the order of their colours); ValueError otherwise."""
    fs = list(dict.fromkeys(features))
    if not 2 <= len(fs) <= COMBINE_MAX or any(f not in FEATURES for f in fs):
        raise ValueError(f"combine 2 to {COMBINE_MAX} different features of: {', '.join(FEATURES)}")
    return sorted(fs, key=lambda f: FEATURES[f][1])


def strength(grey: np.ndarray, shows: str) -> np.ndarray:
    """0-1 from a grey map (128 = like the continuum): how far the feature emits (shows = "emission") or absorbs
    ("absorption") beyond 1 noise level, in the map's asinh stretch (1 = SIGMA_SPAN noise levels or more)."""
    s = (grey - 128.0) / 127.0 if shows == "emission" else (128.0 - grey) / 128.0
    return np.clip((s - _FLOOR) / (1.0 - _FLOOR), 0.0, 1.0)


def combined_map(target_dir: Path, features) -> tuple[np.ndarray, np.ndarray]:
    """(RGB uint8 (h, w, 3), coverage) of 2-3 features' maps, which compute() made first (LookupError if not).
    Each feature adds its colour times its strength; coverage = where all of them have data."""
    from PIL import Image

    fs = combo(features)
    rgb = cov = None
    for f, colour in zip(fs, COMBINE_COLOURS[len(fs)]):
        p = Path(target_dir) / "chemistry" / f"{f}.png"
        if not p.is_file():
            raise LookupError(f"no {FEATURES[f][0]} map made yet")
        a = np.asarray(Image.open(p).convert("LA"), np.float32)
        s = strength(a[..., 0], SHOWS[f])
        if rgb is None:
            rgb, cov = np.zeros(s.shape + (3,), np.float32), np.ones(s.shape, bool)
        if s.shape != cov.shape:
            raise LookupError("the maps were made on different grids (field rebuilt?): make them again")
        rgb += s[..., None] * np.asarray(colour, np.float32)
        cov &= a[..., 1] > 0
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
