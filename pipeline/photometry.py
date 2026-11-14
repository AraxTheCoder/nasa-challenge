"""T49: aperture photometry at one sky position in every frame of a built target.

For each frame, the cached SPHEREx cutout (the FITS the frame was rendered from, `data/raw/cutouts/`) is
measured at the position:

    flux = sum over the aperture (r = APERTURE_PX native pixels) of (IMAGE - ZODI - background)
    background = 3-sigma-clipped median of the annulus (ANNULUS_PX), flagged pixels left out
    error from VARIANCE (+ the background's uncertainty); MJy/sr * pixel solid angle -> uJy

plus the wavelength and bandwidth *at the star* (SPHEREx's linear variable filters: the wavelength
changes across the detector, so the field centre's value would be wrong off-centre).

Limits, said plainly in the result's `note`: no aperture correction (the PSF grows with wavelength, so a
spectrum's slope is approximate), and frames where hardware-flagged pixels (e.g. saturation) cover more
than MAX_MASKED of the aperture are marked `masked` and should not be trusted.

    python -m pipeline.photometry data/targets/<id> --ra 76.9566 --dec 30.4013
    python -m pipeline.photometry --all --ra 76.9566 --dec 30.4013      # T66: every exposure there

T66 (`measure_all`): the same photometry on *every* SPHEREx exposure covering a position (~300 instead of
the ~40 frames a field keeps for blinking), from tiny cutouts (SPECTRUM_CUT_DEG) read from the bucket or
the team VM in parallel, cached per position under data/spectra/.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import threading
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from . import build
from .s3 import IBE_PREFIX, S3_ROOT

APERTURE_PX = 3.0
ANNULUS_PX = (5.0, 8.0)
MAX_MASKED = 0.2            # more than this fraction of the aperture flagged -> masked
NOTE = ("Aperture photometry (r = 3 native px ≈ 18″) on the zodi-subtracted SPHEREx images; no aperture "
        "correction, so the spectrum's slope is approximate. Masked = saturated or flagged pixels in the aperture. "
        "Neighbours within ~18″ blend in (SPHEREx pixels are 6″), mostly at short wavelengths where stars are brightest.")


def image_url(source_url: str) -> str:
    """The IRSA image URL a frame was built from (the key of its cached cutout)."""
    url = source_url.split("#", 1)[0].split("?", 1)[0]
    if url.startswith(S3_ROOT):
        url = IBE_PREFIX + url[len(S3_ROOT):]
    return url


def measure_cutout(path: Path, ra: float, dec: float) -> dict | None:
    """Photometry at (ra, dec) in one cached cutout; None if the position is not on it."""
    from astropy.io import fits
    from astropy.wcs import WCS, FITSFixedWarning
    from astropy.wcs.utils import proj_plane_pixel_area

    with fits.open(path) as hd, warnings.catch_warnings():
        warnings.simplefilter("ignore", FITSFixedWarning)
        img = hd["IMAGE"].data.astype(float)
        if "ZODI" in hd:
            img = img - hd["ZODI"].data
        var = hd["VARIANCE"].data.astype(float) if "VARIANCE" in hd else None
        bad = ((hd["FLAGS"].data.astype(np.int64) & build.HW_MASK) != 0) | ~np.isfinite(img)
        w = WCS(hd["IMAGE"].header)
        x, y = (float(v) for v in w.all_world2pix(ra, dec, 0))
        ny, nx = img.shape
        r_out = ANNULUS_PX[1]
        if not (r_out <= x <= nx - 1 - r_out and r_out <= y <= ny - 1 - r_out):
            return None
        wave, bw = build.wavelength_at(hd, x, y)
        pix_sr = proj_plane_pixel_area(w) * (math.pi / 180) ** 2

    x0, x1 = int(x - r_out) - 1, int(x + r_out) + 2
    y0, y1 = int(y - r_out) - 1, int(y + r_out) + 2
    yy, xx = np.mgrid[y0:y1, x0:x1]
    r = np.hypot(xx - x, yy - y)
    sub, subbad = img[y0:y1, x0:x1], bad[y0:y1, x0:x1]
    ap = r <= APERTURE_PX
    ann = (r >= ANNULUS_PX[0]) & (r <= ANNULUS_PX[1]) & ~subbad
    if ann.sum() < 8:
        return None
    sky = sub[ann]
    med, sd = float(np.median(sky)), float(np.std(sky))
    sky = sky[np.abs(sky - med) < 3 * sd] if sd > 0 else sky
    bkg, bkg_sd = float(np.median(sky)), float(np.std(sky))

    good = ap & ~subbad
    masked_fraction = float(subbad[ap].mean())
    n_ap, n_good = int(ap.sum()), int(good.sum())
    if n_good == 0:
        flux_sum, var_sum = math.nan, math.nan
    else:
        # masked pixels inside the aperture are filled with the mean of the good ones
        flux_sum = float((sub[good] - bkg).sum()) * n_ap / n_good
        v = var[y0:y1, x0:x1][good] if var is not None else np.full(n_good, bkg_sd ** 2)
        var_sum = float(np.nansum(v)) * n_ap / n_good + (n_ap * bkg_sd) ** 2 / max(len(sky), 1)
    to_ujy = pix_sr * 1e12  # MJy/sr * sr = MJy; 1 MJy = 1e12 uJy
    return {
        "flux_ujy": None if math.isnan(flux_sum) else round(flux_sum * to_ujy, 3),
        "err_ujy": None if math.isnan(var_sum) else round(math.sqrt(max(var_sum, 0.0)) * to_ujy, 3),
        "wavelength_um": round(wave, 4), "bandwidth_um": round(bw, 4),
        "masked_fraction": round(masked_fraction, 3), "masked": masked_fraction > MAX_MASKED or n_good == 0,
    }


def measure(target: dict, ra: float, dec: float, raw_root: Path | None = None) -> dict:
    """Photometry at (ra, dec) in every frame of `target` (a parsed target.json)."""
    raw_root = raw_root or build.RAW_ROOT  # looked up at call time (tests point it elsewhere)
    c = target["center"]
    rows, missing = [], []
    for f in sorted(target["frames"], key=lambda f: f["mjd"]):
        path = build.cached_cutout(image_url(f.get("source_url") or ""), c["ra_deg"], c["dec_deg"], 0.0, raw_root) \
            if f.get("source_url") else None
        m = measure_cutout(path, ra, dec) if path else None
        if m is None:
            missing.append(f["id"])
            continue
        rows.append({"frame_id": f["id"], "epoch": f.get("epoch"), "mjd": f["mjd"], "time_utc": f.get("time_utc"),
                     "detector": f.get("detector"), **m})
    return {
        "id": target.get("id"), "ra_deg": round(ra, 6), "dec_deg": round(dec, 6),
        "aperture_px": APERTURE_PX, "annulus_px": list(ANNULUS_PX), "unit": "uJy",
        "frames": rows, "missing": missing, "note": NOTE,
    }


SPECTRUM_CUT_DEG = 0.05      # 3': room for the annulus (8 px) around the star, little over-read
SPECTRA_ROOT = Path("data/spectra")
SPECTRUM_THREADS = 24        # S3 from Europe: ~4 MB/s per connection, ~40 MB/s with 32 in parallel
_spectra_lock = threading.Lock()


def spectrum_cache(ra: float, dec: float) -> Path:
    return SPECTRA_ROOT / f"{ra:.4f}_{dec:+.4f}.json"


def measure_all(ra: float, dec: float, progress=None, threads: int = SPECTRUM_THREADS) -> dict:
    """T66: photometry at (ra, dec) on every exposure that covers it. progress(done, total) while running.
    Same answer shape as measure(); frame_id = '<obs_id>-D<detector>' (these are not the field's frames)."""
    ra, dec = round(ra % 360, 4), round(dec, 4)
    cached = spectrum_cache(ra, dec)
    if cached.is_file():
        return json.loads(cached.read_text(encoding="utf-8"))
    t0 = time.time()
    exposures, _ = build.cached_exposures(ra, dec)
    total = len(exposures)
    done, rows, missing, lock = [0], [], [], threading.Lock()

    def one(e) -> dict | None:
        path = build.fetch(e.fits_url, ra, dec, SPECTRUM_CUT_DEG, min_deg=SPECTRUM_CUT_DEG)
        m = measure_cutout(path, ra, dec)
        return None if m is None else {
            "frame_id": f"{e.obs_id}-D{e.detector}", "epoch": e.epoch, "mjd": round(e.mjd_mid, 6),
            "time_utc": e.time_utc, "detector": e.detector, **m}

    lost = []
    with ThreadPoolExecutor(threads) as pool:
        futs = {pool.submit(one, e): e for e in exposures}
        for f in as_completed(futs):
            e = futs[f]
            try:
                r = f.result()
                (rows.append(r) if r else missing.append(f"{e.obs_id}-D{e.detector}"))
            except LookupError:
                missing.append(f"{e.obs_id}-D{e.detector}")
            except Exception:  # noqa: BLE001 - path moved (reprocessed): resolved below
                lost.append(e)
            with lock:
                done[0] += 1
                if progress:
                    progress(done[0], total)
    if lost:   # reprocessed images live under another path (l2b_retry): look them up, one more try
        try:
            from .mirror import resolve_urls
            fixed = resolve_urls([e.publisher_did for e in lost])
        except Exception:  # noqa: BLE001
            fixed = {}
        for e in lost:
            url = fixed.get(e.publisher_did)
            try:
                if not url or url == e.fits_url:
                    raise LookupError
                e.fits_url = url
                r = one(e)
                (rows.append(r) if r else missing.append(f"{e.obs_id}-D{e.detector}"))
            except Exception:  # noqa: BLE001
                missing.append(f"{e.obs_id}-D{e.detector}")
    rows.sort(key=lambda r: (r["mjd"], r["detector"]))
    out = {"ra_deg": ra, "dec_deg": dec, "aperture_px": APERTURE_PX, "annulus_px": list(ANNULUS_PX),
           "unit": "uJy", "frames": rows, "missing": missing, "all_exposures": True, "n_exposures": total,
           "seconds": round(time.time() - t0, 1), "note": NOTE}
    with _spectra_lock:
        cached.parent.mkdir(parents=True, exist_ok=True)
        tmp = cached.with_suffix(f".{threading.get_ident()}.part")
        tmp.write_text(json.dumps(out), encoding="utf-8")
        tmp.replace(cached)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m pipeline.photometry", description=__doc__.split("\n\n")[0])
    ap.add_argument("target_dir", type=Path, nargs="?")
    ap.add_argument("--ra", type=float, help="default: the field centre")
    ap.add_argument("--dec", type=float)
    ap.add_argument("--all", action="store_true", help="T66: every exposure covering --ra/--dec (no field needed)")
    args = ap.parse_args(argv)
    if args.all:
        res = measure_all(args.ra, args.dec, progress=lambda d, n: print(f"\r{d}/{n}", end="", flush=True))
        print()
    else:
        t = json.loads((args.target_dir / "target.json").read_text(encoding="utf-8"))
        ra = args.ra if args.ra is not None else t["center"]["ra_deg"]
        dec = args.dec if args.dec is not None else t["center"]["dec_deg"]
        res = measure(t, ra, dec)
    for r in res["frames"]:
        flag = " masked" if r["masked"] else ""
        print(f"  {r['frame_id']}  ep{r['epoch']}  {r['wavelength_um']:.3f} µm  {r['flux_ujy']} ± {r['err_ujy']} µJy{flag}")
    print(f"{len(res['frames'])} measured, {len(res['missing'])} without a cached cutout / off the image"
          + (f", {res['seconds']} s" if res.get("seconds") is not None else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
