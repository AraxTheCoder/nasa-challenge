"""T02-T04: build a target folder from live SPHEREx data (CONTRACTS "target.json", v0.3 Live API).

query (T01) -> download cutouts with a cache (T02) -> resample onto one north-up grid and read the
wavelength at the centre (T03) -> render PNGs + write target.json, labels via T19 (T04).

    python -m pipeline.build --id barnard --ra 269.4486 --dec 4.7397 --size 15 [--out data/targets]
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np

from .query import find_exposures

PIXEL_SCALE_ARCSEC = 6.15
RAW_ROOT = Path("data/raw")
# Hardware/bad-pixel bits (TEAM.md Log, T01). SOURCE (21) and OUTLIER (19) are deliberately kept.
HW_MASK = sum(1 << b for b in (0, 1, 2, 6, 9, 10, 11, 14, 17, 25, 26, 27, 28))
PER_GROUP = 2        # images per (epoch, detector); 3 epochs x 6 detectors x 2 = 36 cutouts
THREADS = 8
TIMEOUT_S = 180

Progress = Callable[..., None]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# -- T02: choose + download ------------------------------------------------------------------------

def select(exposures, per_group: int = PER_GROUP):
    """Up to per_group images per (epoch, detector), spread evenly in time."""
    groups: dict[tuple[int, int], list] = {}
    for e in exposures:
        groups.setdefault((e.epoch, e.detector), []).append(e)
    chosen = []
    for key in sorted(groups):
        g = sorted(groups[key], key=lambda e: e.mjd_mid)
        if len(g) <= per_group:
            chosen += g
        else:
            idx = np.unique(np.linspace(0, len(g) - 1, per_group).round().astype(int))
            chosen += [g[i] for i in idx]
    return sorted(chosen, key=lambda e: (e.mjd_mid, e.detector))


def cutout_url(fits_url: str, ra: float, dec: float, size_deg: float) -> str:
    return f"{fits_url}?center={ra:.6f},{dec:.6f}&size={size_deg:.4f}deg"


def fetch(url: str, raw_root: Path = RAW_ROOT) -> Path:
    """Download once; later calls hit the cache (data/raw/<hash>.fits)."""
    import requests

    raw_root.mkdir(parents=True, exist_ok=True)
    path = raw_root / (hashlib.sha1(url.encode()).hexdigest()[:20] + ".fits")
    if path.exists() and path.stat().st_size > 0:
        return path
    r = requests.get(url, timeout=TIMEOUT_S)
    r.raise_for_status()
    tmp = path.with_suffix(".part")
    tmp.write_bytes(r.content)
    tmp.replace(path)
    return path


# -- T03: align + wavelength -------------------------------------------------------------------------

def output_wcs(ra: float, dec: float, npix: int):
    """CONTRACTS grid: TAN, north up, east left, centred. Same convention as pipeline.labels.Grid."""
    from astropy.wcs import WCS

    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [ra, dec]
    w.wcs.crpix = [(npix + 1) / 2, (npix + 1) / 2]
    s = PIXEL_SCALE_ARCSEC / 3600
    w.wcs.cdelt = [-s, s]
    return w


def wavelength_at(hdul, x0: float, y0: float) -> tuple[float, float]:
    """(wavelength, bandwidth) in um at 0-based cutout pixel (x0, y0), from the WCS-WAVE table.

    The table is a grid on 1-based detector pixels; cutout -> detector via CRPIXnW (WAVE-TAB):
    detector_1based = (x0 + 1 - CRPIX1W) + CRVAL1W."""
    from scipy.interpolate import RegularGridInterpolator

    h = hdul["IMAGE"].header
    t = hdul["WCS-WAVE"].data
    gx, gy = np.asarray(t["X"][0], float), np.asarray(t["Y"][0], float)
    vals = np.asarray(t["VALUES"][0], float)          # (ny, nx, 2): wavelength, bandwidth
    dx = x0 + 1 - h.get("CRPIX1W", h.get("CRPIX1A")) + h.get("CRVAL1W", 1)
    dy = y0 + 1 - h.get("CRPIX2W", h.get("CRPIX2A")) + h.get("CRVAL2W", 1)
    dx, dy = float(np.clip(dx, gx.min(), gx.max())), float(np.clip(dy, gy.min(), gy.max()))
    out = [RegularGridInterpolator((gy, gx), vals[..., k])((dy, dx)) for k in (0, 1)]
    return float(out[0]), float(out[1])


def resample(path: Path, out_w, npix: int, ra: float, dec: float):
    """Return (image on the output grid, rows top-down, NaN = no data; wavelength; bandwidth)."""
    from astropy.io import fits
    from astropy.wcs import WCS
    from scipy.ndimage import map_coordinates

    with fits.open(path) as hd:
        img = hd["IMAGE"].data.astype(float)
        if "ZODI" in hd:
            img = img - hd["ZODI"].data
        bad = ((hd["FLAGS"].data.astype(np.int64) & HW_MASK) != 0) | ~np.isfinite(img)
        in_w = WCS(hd["IMAGE"].header)
        cx, cy = in_w.all_world2pix(ra, dec, 0)
        wave, bw = wavelength_at(hd, float(cx), float(cy))

    yy, xx = np.mgrid[0:npix, 0:npix]
    # Output row 0 is the top (north): FITS y = npix - 1 - row.
    sra, sdec = out_w.all_pix2world(xx, npix - 1 - yy, 0)
    ix, iy = in_w.all_world2pix(sra, sdec, 0)
    data = np.where(bad, 0.0, img)
    out = map_coordinates(data, [iy, ix], order=1, mode="constant", cval=np.nan)
    badout = map_coordinates(bad.astype(float), [iy, ix], order=1, mode="constant", cval=1.0) > 0.25
    out[badout] = np.nan
    return out, wave, bw


# -- T04: render + target.json -------------------------------------------------------------------------

def render_png(img: np.ndarray, path: Path) -> None:
    """asinh stretch per frame, 8-bit grey + alpha (alpha 0 = no data, CONTRACTS v0.2)."""
    from PIL import Image

    finite = np.isfinite(img)
    grey = np.zeros(img.shape, np.uint8)
    if finite.sum() > 10:
        v = img[finite]
        lo, hi = np.percentile(v, 5), np.percentile(v, 99.7)
        if hi <= lo:
            hi = lo + 1e-6
        s = np.clip((img - lo) / (hi - lo), 0, 1)
        s = np.arcsinh(10 * s) / np.arcsinh(10)
        grey = np.where(finite, (s * 255).round(), 0).astype(np.uint8)
    alpha = np.where(finite, 255, 0).astype(np.uint8)
    Image.fromarray(np.dstack([grey, alpha]), "LA").save(path, optimize=True)


def build_target(target_id: str, ra_deg: float, dec_deg: float, size_arcmin: float,
                 out_root: Path = Path("data/targets"), progress: Progress | None = None,
                 per_group: int = PER_GROUP, name: str | None = None) -> Path:
    """Query, download, align, render. Returns the target folder with a valid target.json."""
    def report(step, done=None, total=None, message=""):
        if progress:
            progress(step, done, total, message)

    report("query", message="searching IRSA for SPHEREx images")
    exposures, prov_query = find_exposures(ra_deg, dec_deg)
    if not exposures:
        raise LookupError(f"no SPHEREx images cover RA {ra_deg} Dec {dec_deg}")
    chosen = select(exposures, per_group)

    npix = max(16, int(round(size_arcmin * 60 / PIXEL_SCALE_ARCSEC)))
    cut_deg = size_arcmin / 60 * 1.5 + 0.01   # room for the rotation of the original frames
    urls = [cutout_url(e.fits_url, ra_deg, dec_deg, cut_deg) for e in chosen]
    downloads_started = _now()
    paths: list[Path | None] = [None] * len(urls)
    errors = []
    report("download", 0, len(urls), f"downloading {len(urls)} of {len(exposures)} SPHEREx images")
    with ThreadPoolExecutor(THREADS) as pool:
        futs = {pool.submit(fetch, u): i for i, u in enumerate(urls)}
        for n, f in enumerate(as_completed(futs), 1):
            try:
                paths[futs[f]] = f.result()
            except Exception as e:  # noqa: BLE001 - one failed cutout shouldn't kill the field
                errors.append(f"{urls[futs[f]]}: {e}")
            report("download", n, len(urls), f"downloaded {n}/{len(urls)}")

    out = Path(out_root) / target_id
    (out / "frames").mkdir(parents=True, exist_ok=True)
    for old in (out / "frames").glob("*"):
        old.unlink()
    out_w = output_wcs(ra_deg, dec_deg, npix)
    frames = []
    for i, (e, p, u) in enumerate(zip(chosen, paths, urls)):
        report("align", i, len(chosen), f"aligning {e.obs_id} D{e.detector}")
        if p is None:
            continue
        try:
            img, wave, bw = resample(p, out_w, npix, ra_deg, dec_deg)
        except Exception as ex:  # noqa: BLE001
            errors.append(f"{e.obs_id} D{e.detector}: {ex}")
            continue
        if np.isfinite(img).mean() < 0.2:
            continue                      # target barely on this image
        fid = f"f{len(frames):03d}"
        render_png(img, out / "frames" / f"{fid}.png")
        frames.append({
            "id": fid, "time_utc": e.time_utc, "mjd": round(e.mjd_mid, 6), "epoch": e.epoch,
            "detector": e.detector, "wavelength_um": round(wave, 4), "bandwidth_um": round(bw, 4),
            "image": f"frames/{fid}.png", "obs_id": e.obs_id, "source_url": u,
        })
    if not frames:
        raise LookupError(f"SPHEREx images found but none usable at RA {ra_deg} Dec {dec_deg}: "
                          + "; ".join(errors[:3]))

    target = {
        "schema_version": "0.2", "id": target_id,
        "name": name or f"SPHEREx field RA {ra_deg:.4f} Dec {dec_deg:+.4f}",
        "synthetic": False,
        "center": {"ra_deg": ra_deg, "dec_deg": dec_deg},
        "size_arcmin": size_arcmin,
        "image": {"width": npix, "height": npix, "pixel_scale_arcsec": PIXEL_SCALE_ARCSEC},
        "provenance": [prov_query, {
            "service": "IRSA SPHEREx cutouts",
            "query": f"{len(urls)} cutouts (per frame: source_url), size {cut_deg:.4f} deg, "
                     f"{per_group} per epoch+detector of {len(exposures)} images; "
                     f"{len(errors)} failed",
            "retrieved_utc": downloads_started}],
        "frames": frames, "known_objects": [], "detections": [],
    }
    report("render", len(frames), len(frames), "adding catalogue labels")
    try:
        from .labels import add_labels
        add_labels(target)
    except Exception as ex:  # noqa: BLE001 - labels are nice to have, frames are the product
        target["labels"] = []
        print(f"labels skipped: {ex}")
    (out / "target.json").write_text(json.dumps(target, indent=1), encoding="utf-8")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--id", required=True)
    ap.add_argument("--ra", type=float, required=True)
    ap.add_argument("--dec", type=float, required=True)
    ap.add_argument("--size", type=float, default=15)
    ap.add_argument("--out", type=Path, default=Path("data/targets"))
    ap.add_argument("--per-group", type=int, default=PER_GROUP)
    args = ap.parse_args(argv)
    out = build_target(args.id, args.ra, args.dec, args.size, args.out,
                       progress=lambda s, d=None, t=None, m="": print(f"[{s}] {m}", flush=True),
                       per_group=args.per_group)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
