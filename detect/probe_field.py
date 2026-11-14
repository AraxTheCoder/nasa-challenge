"""T10: is a test target actually visible in SPHEREx pixels, and does it move between epochs?

For one target from `data/t10/test_fields.json` (written by `detect.test_fields`): download small
cutouts of up to N images per epoch on one detector, subtract ZODI and the local median, stack
per epoch (inverse-variance mean on the pixel grid of each cutout via WCS), and measure S/N and
centroid at the proper-motion position for that epoch.

    python -m detect.probe_field wise-0855 --detector 6 [--n 8] [--size 0.05]
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import requests

from pipeline.query import find_exposures

RAW = Path("data/raw/t10")
HW_MASK = sum(1 << b for b in (0, 1, 2, 6, 9, 10, 11, 14, 17, 25, 26, 27, 28))  # TEAM.md Log, T01


def fetch(url: str) -> bytes:
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".fits")
    if not path.exists():
        r = requests.get(url, timeout=180)
        r.raise_for_status()
        path.write_bytes(r.content)
    return path.read_bytes()


def measure(blob: bytes, ra: float, dec: float, r_ap: float = 1.5):
    from astropy.io import fits
    from astropy.wcs import WCS

    with fits.open(io.BytesIO(blob)) as h:
        img = h["IMAGE"].data.astype(float) - h["ZODI"].data
        var = h["VARIANCE"].data.astype(float)
        bad = (h["FLAGS"].data.astype(np.int64) & HW_MASK) != 0
        wcs = WCS(h["IMAGE"].header)
    img[bad | ~np.isfinite(img)] = np.nan
    x0, y0 = wcs.world_to_pixel_values(ra, dec)
    yy, xx = np.indices(img.shape)
    rr = np.hypot(xx - x0, yy - y0)
    ap = (rr <= r_ap) & np.isfinite(img)
    ann = (rr > 4) & (rr < 8) & np.isfinite(img)
    if ap.sum() < 3 or ann.sum() < 10:
        return None
    bkg = np.nanmedian(img[ann])
    flux = np.nansum(img[ap] - bkg)
    err = math.sqrt(np.nansum(var[ap]) + ap.sum() ** 2 * (1.2533 * np.nanstd(img[ann])) ** 2 / ann.sum())
    w = np.clip(img - bkg, 0, None) * (rr <= 3)
    w[~np.isfinite(w)] = 0
    if w.sum() > 0:
        cx, cy = (w * xx).sum() / w.sum(), (w * yy).sum() / w.sum()
        cra, cdec = wcs.pixel_to_world_values(cx, cy)
    else:
        cra = cdec = float("nan")
    return {"flux": flux, "err": err, "snr": flux / err if err > 0 else 0.0,
            "centroid_offset_arcsec": [float((cra - ra) * math.cos(math.radians(dec)) * 3600),
                                       float((cdec - dec) * 3600)]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("key")
    ap.add_argument("--detector", type=int, default=6)
    ap.add_argument("--n", type=int, default=8, help="images per epoch")
    ap.add_argument("--size", type=float, default=0.05, help="cutout side in deg")
    ap.add_argument("--fields", type=Path, default=Path("data/t10/test_fields.json"))
    args = ap.parse_args(argv)

    t = next(x for x in json.loads(args.fields.read_text(encoding="utf-8")) if x["key"] == args.key)
    out = {"key": args.key, "detector": args.detector, "epochs": []}
    for ep in t["epochs"]:
        pos = ep["position"]
        ex, _ = find_exposures(pos["ra_deg"], pos["dec_deg"])
        sel = [e for e in ex if e.detector == args.detector and e.epoch == ep["epoch"]][: args.n]
        urls = [e.fits_url + f"?center={pos['ra_deg']},{pos['dec_deg']}&size={args.size}deg" for e in sel]
        with ThreadPoolExecutor(8) as pool:
            blobs = list(pool.map(fetch, urls))
        ms = [m for m in (measure(b, pos["ra_deg"], pos["dec_deg"]) for b in blobs) if m]
        if not ms:
            out["epochs"].append({"epoch": ep["epoch"], "n": 0})
            continue
        w = np.array([1 / m["err"] ** 2 for m in ms])
        f = np.array([m["flux"] for m in ms])
        snr_stack = float((w * f).sum() / w.sum() * math.sqrt(w.sum()))
        offs = np.array([m["centroid_offset_arcsec"] for m in ms])
        row = {"epoch": ep["epoch"], "date": ep["start"], "n": len(ms),
               "wave_um": [sel[0].wave_min_um, sel[0].wave_max_um],
               "snr_single_median": round(float(np.median([m["snr"] for m in ms])), 1),
               "snr_stacked": round(snr_stack, 1),
               "centroid_offset_median_arcsec": [round(float(v), 2) for v in np.nanmedian(offs, axis=0)]}
        out["epochs"].append(row)
        print(row, flush=True)
    dst = Path(f"data/t10/probe_{args.key}_D{args.detector}.json")
    dst.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {dst}")


if __name__ == "__main__":
    main()
