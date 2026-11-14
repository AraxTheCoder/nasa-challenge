"""Prototype for the T32 idea (Jonathan's task; this is only a local feel-test, nothing in the repo).
Stitch the cutouts of each epoch into one mosaic, then write each mosaic as HiPS tiles.

    make_hips.py <query_subset.json> <cutout_dir> <out_dir> [field_deg]
"""
import json, shutil, sys, time, warnings
from pathlib import Path
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS, FITSFixedWarning
from reproject import reproject_interp
from reproject.mosaicking import reproject_and_coadd
from reproject.hips import reproject_to_hips

warnings.simplefilter("ignore", FITSFixedWarning)
q = json.load(open(sys.argv[1])); cdir = Path(sys.argv[2]); out = Path(sys.argv[3])
field = float(sys.argv[4]) if len(sys.argv) > 4 else 1.2
ra0, dec0 = q["ra_deg"], q["dec_deg"]
BAD = sum(1 << b for b in (0, 1, 2, 6, 9, 10, 11, 14, 17, 25, 26, 27, 28))
scale = 6.15 / 3600
n = int(round(field / scale))
tw = WCS(naxis=2); tw.wcs.ctype = ["RA---TAN", "DEC--TAN"]; tw.wcs.crval = [ra0, dec0]
tw.wcs.crpix = [(n + 1) / 2, (n + 1) / 2]; tw.wcs.cdelt = [-scale, scale]

by_epoch = {}
for e in q["exposures"]:
    f = cdir / f"{e['obs_id']}_D1.fits"
    if f.exists():
        by_epoch.setdefault(e["epoch"], []).append((e, f))

out.mkdir(parents=True, exist_ok=True)
summary = {"ra_deg": ra0, "dec_deg": dec0, "field_deg": field, "epochs": []}
mosaics = {}
for ep, items in sorted(by_epoch.items()):
    t = time.time()
    inputs = []
    for e, f in items:
        with fits.open(f) as h:
            img = h["IMAGE"].data.astype(float) - h["ZODI"].data.astype(float)
            img[(h["FLAGS"].data & BAD) != 0] = np.nan
            img -= np.nanmedian(img)
            inputs.append((img, WCS(h["IMAGE"].header)))
    mos, foot = reproject_and_coadd(inputs, tw, shape_out=(n, n), reproject_function=reproject_interp,
                                    combine_function="mean", match_background=False)
    mos[foot == 0] = np.nan
    mosaics[ep] = mos
    cover = float(np.mean(foot > 0))
    summary["epochs"].append({"epoch": ep, "n_images": len(items), "coverage": round(cover, 3),
                              "dates": [items[0][0]["time_utc"][:10], items[-1][0]["time_utc"][:10]]})
    print(f"epoch {ep}: {len(items)} images stitched, {cover:.0%} of the {field} deg field covered, {time.time() - t:.0f}s", flush=True)

# one display range for all epochs so blinking compares like with like
allv = np.concatenate([m[np.isfinite(m)] for m in mosaics.values()])
lo, hi = np.percentile(allv, 1), np.percentile(allv, 99.7)
summary["cuts"] = [float(lo), float(hi)]
for ep, mos in mosaics.items():
    d = out / f"epoch{ep}"
    shutil.rmtree(d, ignore_errors=True)
    t = time.time()
    reproject_to_hips((mos.astype(np.float32), tw), coord_system_out="equatorial",
                      reproject_function=reproject_interp, output_directory=str(d), tile_size=256,
                      threads=True, properties={"obs_title": f"SPHEREx D1 epoch {ep} (prototype mosaic)",
                                                "creator_did": f"ivo://local/spherex-proto-epoch{ep}"})
    files = list(d.rglob("*.fits"))
    print(f"epoch {ep}: HiPS written, {len(files)} tiles, {sum(f.stat().st_size for f in files) / 1e6:.1f} MB, {time.time() - t:.0f}s", flush=True)
    summary["epochs"][[x["epoch"] for x in summary["epochs"]].index(ep)]["tiles"] = len(files)
(out / "summary.json").write_text(json.dumps(summary, indent=1))
print(json.dumps(summary))
