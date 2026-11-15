"""T135: sources in SPHEREx's own images, for the unusual-spectra measurement (T85/T86), which otherwise measures
only the field's catalogue labels and so could never flag anything uncatalogued (Mati, 2026-11-15).

One pass over the field's exposures (the same field cutouts pipeline/fieldspectra.py reads anyway): each image
(IMAGE − ZODI, flagged pixels out) resampled onto the field grid and added to a running mean per detector group
(D1–3 = 0.75–2.4 µm, D4 = 2.4–3.8, D5 = 3.8–4.4, D6 = 4.4–5.0 µm) and epoch; the deep image of a group is the
median of its epoch means (an asteroid or a transient in one epoch doesn't make a source). Large-scale background
(16 px block medians) removed, lightly smoothed, peaks >= DETECT_SIGMA in any group. Left out: catalogued sources
(a label within CAT_ARCSEC), the glow around bright stars, the coverage edge. The strongest MAX_NEW stay.
Memory: running sums only (groups × epochs × 2 arrays of the field grid; ~60 MB for an 82′ field).

    spherex_sources(target, catalogue_sources, compute=False)   -> stored ones only (cheap, for cache checks)
    spherex_sources(target, catalogue_sources, compute=True)    -> found now if not stored (the measurement job)

Cached as data/field_spectra/<target id>.sources.json. Sources come in pipeline.fieldspectra's shape, with
"source": "spherex", ids "x001"…, "snr" per group, and "red": seen only at >= 3.8 µm (cold brown dwarfs).
"""
from __future__ import annotations

import json
import math
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

VERSION = 1
GROUPS = ("0.75–2.4 µm", "2.4–3.8 µm", "3.8–4.4 µm", "4.4–5.0 µm")
GROUP_OF_DETECTOR = {1: 0, 2: 0, 3: 0, 4: 1, 5: 2, 6: 3}
DETECT_SIGMA = 5.0
FAINT_SIGMA = 3.0            # "red": >= DETECT_SIGMA at 3.8–5 µm and below this at 0.75–2.4 µm
CAT_ARCSEC = 8.0             # a catalogue label this close: not SPHEREx-only
BRIGHT_MAG, BRIGHT_ARCSEC = 9.0, 40.0   # peaks this close to a star this bright are its glow
EDGE_PX = 3
BLOCK_PX = 16
MAX_NEW = 150
THREADS = 4
_lock = threading.Lock()


def cache_path(target_id: str) -> Path:
    from .fieldspectra import ROOT
    return ROOT / f"{target_id}.sources.json"


def _on_grid(path: Path, sky_ra, sky_dec, npix: int) -> np.ndarray:
    """One exposure's IMAGE − ZODI (MJy/sr) on the field grid, NaN where flagged or outside."""
    from astropy.io import fits
    from astropy.wcs import WCS
    from scipy.ndimage import map_coordinates

    from .build import HW_MASK
    with fits.open(path) as hd:
        img = hd["IMAGE"].data.astype(np.float32)
        if "ZODI" in hd:
            img = img - hd["ZODI"].data
        bad = ((hd["FLAGS"].data.astype(np.int64) & HW_MASK) != 0) | ~np.isfinite(img)
        ix, iy = WCS(hd["IMAGE"].header).all_world2pix(sky_ra, sky_dec, 0)
    inside = (ix >= 0) & (iy >= 0) & (ix <= img.shape[1] - 1) & (iy <= img.shape[0] - 1)
    out = map_coordinates(np.where(bad, 0.0, img), [iy, ix], order=1, mode="constant", cval=np.nan).astype(np.float32)
    badout = map_coordinates(bad.astype(np.float32), [iy, ix], order=1, mode="constant", cval=1.0) > 0.25
    out[badout | ~inside] = np.nan
    return out.reshape(npix, npix)


def deep_images(sums: dict, counts: dict) -> tuple[list, list]:
    """Per detector group: (deep image = median over epochs of the epoch means, coverage). sums / counts:
    {(group, epoch): array}."""
    import warnings
    imgs, covs = [], []
    shape = next(iter(sums.values())).shape if sums else (1, 1)
    for g in range(len(GROUPS)):
        means = [np.where(counts[k] > 0, sums[k] / np.maximum(counts[k], 1), np.nan) for k in sums if k[0] == g]
        if not means:
            imgs.append(np.full(shape, np.nan, np.float32)); covs.append(np.zeros(shape, bool))
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            d = np.nanmedian(np.stack(means), axis=0).astype(np.float32)
        imgs.append(d)
        covs.append(np.isfinite(d))
    return imgs, covs


def _background(d: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """Large-scale background: medians in BLOCK_PX blocks, bilinearly interpolated."""
    import warnings

    from scipy.ndimage import zoom
    h, w = d.shape
    bh, bw = max(1, math.ceil(h / BLOCK_PX)), max(1, math.ceil(w / BLOCK_PX))
    pad = np.full((bh * BLOCK_PX, bw * BLOCK_PX), np.nan, np.float32)
    pad[:h, :w] = np.where(cov, d, np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        blocks = np.nanmedian(pad.reshape(bh, BLOCK_PX, bw, BLOCK_PX), axis=(1, 3))
    fill = np.nanmedian(blocks) if np.isfinite(blocks).any() else 0.0
    blocks = np.where(np.isfinite(blocks), blocks, fill)
    if blocks.size == 1:
        return np.full(d.shape, float(blocks.ravel()[0]), np.float32)
    return zoom(blocks, (bh * BLOCK_PX / bh, bw * BLOCK_PX / bw), order=1, mode="nearest")[:h, :w].astype(np.float32)


def snr_map(d: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """Background-subtracted, lightly smoothed image in units of its own robust noise (0 outside the coverage)."""
    from scipy.ndimage import gaussian_filter
    if cov.sum() < 50:
        return np.zeros(d.shape, np.float32)
    r = np.where(cov, d - _background(d, cov), 0.0)
    c = cov.astype(np.float32)
    sm = gaussian_filter(r, 1.0) / np.maximum(gaussian_filter(c, 1.0), 1e-3)
    v = sm[cov]
    sigma = 1.4826 * float(np.median(np.abs(v - np.median(v)))) or 1.0
    return np.where(cov, sm / sigma, 0.0).astype(np.float32)


def find_peaks(snrs: list, covs: list) -> list[dict]:
    """Peaks >= DETECT_SIGMA in any group, merged across groups (within 2 px): [{"x", "y", "snr": [per group]}],
    strongest first. x, y: field pixels (sub-pixel centroid), y counted from the top row."""
    from scipy.ndimage import binary_erosion, maximum_filter
    found = []
    for g, (s, cov) in enumerate(zip(snrs, covs)):
        if not cov.any():
            continue
        inner = binary_erosion(cov, iterations=EDGE_PX)
        pk = (s >= DETECT_SIGMA) & (s >= maximum_filter(s, size=5)) & inner
        for r, c in zip(*np.nonzero(pk)):
            found.append((float(s[r, c]), int(r), int(c)))
    found.sort(reverse=True)
    out: list[dict] = []
    for _, r, c in found:
        if any((r - o["_r"]) ** 2 + (c - o["_c"]) ** 2 <= 4 for o in out):
            continue
        best = int(np.argmax([s[r, c] for s in snrs]))
        s = snrs[best]
        r0, r1, c0, c1 = max(r - 1, 0), r + 2, max(c - 1, 0), c + 2
        win = np.clip(s[r0:r1, c0:c1], 0, None)
        yy, xx = np.mgrid[r0:r1, c0:c1]
        tot = float(win.sum()) or 1.0
        out.append({"_r": r, "_c": c, "x": float((xx * win).sum() / tot), "y": float((yy * win).sum() / tot),
                    "snr": [round(float(sn[r, c]), 1) for sn in snrs]})
    for o in out:
        del o["_r"], o["_c"]
    return out


def _name(ra: float, dec: float) -> str:
    h = ra / 15
    hh, mm = int(h), int((h % 1) * 60)
    ss = ((h * 60) % 1) * 60
    sg = "+" if dec >= 0 else "-"
    a = abs(dec)
    dd, dm = int(a), int((a % 1) * 60)
    ds = int(((a * 60) % 1) * 60)
    return f"SPHEREx J{hh:02d}{mm:02d}{ss:04.1f}{sg}{dd:02d}{dm:02d}{ds:02d}"


def _keep(peaks, target, catalogue_sources, mjd) -> list[dict]:
    """Field pixels -> sky; catalogued ones, the glow of bright stars and the weakest left out."""
    from .build import output_wcs
    from .fieldspectra import positions_at
    c = target["center"]
    npix = int(target["image"]["width"])
    w = output_wcs(c["ra_deg"], c["dec_deg"], npix)
    cat = positions_at(catalogue_sources, mjd) if catalogue_sources else []
    bright = [p for p, s in zip(cat, catalogue_sources) if s.get("mag") is not None and s["mag"] <= BRIGHT_MAG]
    cos = math.cos(math.radians(c["dec_deg"]))

    def near(ra, dec, pts, arcsec):
        return any(3600 * math.hypot(((ra - a + 180) % 360 - 180) * cos, dec - d) <= arcsec for a, d in pts)

    out = []
    for p in peaks:
        ra, dec = (float(v) for v in w.all_pix2world(p["x"], npix - 1 - p["y"], 0))
        ra %= 360
        if near(ra, dec, cat, CAT_ARCSEC) or near(ra, dec, bright, BRIGHT_ARCSEC):
            continue
        snr = dict(zip(GROUPS, p["snr"]))
        red = max(p["snr"][2], p["snr"][3]) >= DETECT_SIGMA and p["snr"][0] < FAINT_SIGMA
        out.append({"name": _name(ra, dec), "source": "spherex",
                    "kind": "SPHEREx-only source" + (", only at 3.8–5 µm" if red else ""),
                    "otype": None, "mag": None, "mag_band": None, "named": False, "red": red, "snr": snr,
                    "ra_deg": round(ra, 7), "dec_deg": round(dec, 7), "mjd0": round(mjd, 5),
                    "dra_deg_day": 0.0, "ddec_deg_day": 0.0, "aliases": []})
        if len(out) >= MAX_NEW:
            break
    for k, s in enumerate(out):
        s["id"] = f"x{k + 1:03d}"
    return out


def _find(target: dict, catalogue_sources: list[dict], progress=None) -> dict:
    from . import build, photometry
    from .build import output_wcs
    from .fieldspectra import MARGIN_DEG
    c = target["center"]
    ra, dec = round(c["ra_deg"] % 360, 4), round(c["dec_deg"], 4)
    size_deg = round(target.get("size_arcmin", 15) / 60 + 2 * MARGIN_DEG, 4)   # = the measurement's cutouts
    npix = int(target["image"]["width"])
    w = output_wcs(c["ra_deg"], c["dec_deg"], npix)
    yy, xx = np.mgrid[0:npix, 0:npix]
    sky_ra, sky_dec = w.all_pix2world(xx.ravel(), (npix - 1 - yy).ravel(), 0)
    exposures, _ = build.cached_exposures(ra, dec)
    sums, counts, done, used = {}, {}, 0, 0

    def one(e):
        try:
            path = photometry._spectrum_cutout(e.fits_url, ra, dec, size_deg)
            return e, _on_grid(path, sky_ra, sky_dec, npix)
        except Exception:  # noqa: BLE001 - a missing / moved image: the others still find the sources
            return e, None

    with ThreadPoolExecutor(THREADS) as pool:
        for e, img in pool.map(one, exposures):
            done += 1
            if progress:
                progress(done, len(exposures))
            g = GROUP_OF_DETECTOR.get(int(e.detector))
            if img is None or g is None:
                continue
            k = (g, int(e.epoch))
            ok = np.isfinite(img)
            if k not in sums:
                sums[k], counts[k] = np.zeros(img.shape, np.float32), np.zeros(img.shape, np.uint16)
            sums[k] += np.where(ok, img, 0.0)
            counts[k] += ok
            used += 1
    if not sums:
        return {"sources": [], "exposures_used": 0}
    imgs, covs = deep_images(sums, counts)
    snrs = [snr_map(d, cov) for d, cov in zip(imgs, covs)]
    mjds = sorted(f["mjd"] for f in target.get("frames", []) if f.get("mjd"))
    mjd = mjds[len(mjds) // 2] if mjds else 61000.0
    peaks = find_peaks(snrs, covs)
    return {"sources": _keep(peaks, target, catalogue_sources, mjd), "peaks": len(peaks), "exposures_used": used}


def spherex_sources(target: dict, catalogue_sources: list[dict], compute: bool = False, progress=None) -> list[dict]:
    """SPHEREx-only sources of the field: stored ones (compute=False: never reads an image), or found now and
    stored (compute=True). Found again when the catalogue sources changed."""
    from .fieldspectra import _key
    path = cache_path(target["id"])
    key = _key(catalogue_sources)
    try:
        hit = json.loads(path.read_text(encoding="utf-8"))
        if hit.get("version") == VERSION and hit.get("catalogue_key") == key:
            return hit["sources"]
    except (OSError, ValueError):
        pass
    if not compute or not (target.get("image") or {}).get("width"):
        return []                                           # nothing stored / no field grid (a bare test target)
    import time
    t0 = time.time()
    res = _find(target, catalogue_sources, progress)
    out = {"version": VERSION, "target_id": target["id"], "catalogue_key": key, "groups": list(GROUPS),
           "detect_sigma": DETECT_SIGMA, "seconds": round(time.time() - t0, 1), **res}
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{threading.get_ident()}.part")
        tmp.write_text(json.dumps(out), encoding="utf-8")
        tmp.replace(path)
    return out["sources"]


def tag_items(items: list, target_dir: Path, sources: list[dict], year: float, cats=None) -> list:
    """T135: the flagged SPHEREx-only sources looked up in the catalogues (T128, motion-corrected); each gets
    "catalogues" and "tag" ("new" = in none of them, "untyped", "other"); SPHEREx-only and uncatalogued first.
    Items of catalogue sources are left as they are. A catalogue that fails is skipped (no tag claims it)."""
    from . import catcheck
    by_id = {s.get("id"): s for s in sources}
    mine = [it for it in items if (by_id.get(it.get("id")) or {}).get("source") == "spherex"]
    if not mine:
        return items
    pos = [(by_id[it["id"]]["ra_deg"], by_id[it["id"]]["dec_deg"]) for it in mine]
    res = catcheck.check(target_dir, pos, list(cats or catcheck.DEFAULT), year)
    catcheck.tag(mine, res, None)
    for it in mine:
        it["catalogues_failed"] = res["failed"]
    return sorted(items, key=lambda it: 0 if it.get("tag") == "new" else 1)
