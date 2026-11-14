"""Wide stitching test: full detector images -> one mosaic per epoch on a shared grid -> HiPS.
Usage: make_wide.py <image_dir> <out_dir> [max_side_deg]"""
import json, shutil, sys, time, warnings
from pathlib import Path
import numpy as np
import astropy.units as u
from astropy.io import fits
from astropy.wcs import WCS, FITSFixedWarning
from reproject import reproject_interp
from reproject.mosaicking import reproject_and_coadd, find_optimal_celestial_wcs
from reproject.hips import reproject_to_hips

warnings.simplefilter("ignore", FITSFixedWarning)
src, out = Path(sys.argv[1]), Path(sys.argv[2])
max_side = float(sys.argv[3]) if len(sys.argv) > 3 else 6.0
picked = {p["obs_id"]: p for p in json.load(open(src / "picked.json"))}
BAD = sum(1 << b for b in (0, 1, 2, 6, 9, 10, 11, 14, 17, 25, 26, 27, 28))

inputs = {}
for f in sorted(src.glob("*.fits")):
    obs = f.name.split("_D")[0]
    if obs not in picked:
        continue
    with fits.open(f, memmap=False) as h:
        img = h["IMAGE"].data.astype(np.float32) - h["ZODI"].data.astype(np.float32)
        img[(h["FLAGS"].data & BAD) != 0] = np.nan
        img -= np.nanmedian(img)
        w = WCS(h["IMAGE"].header).celestial
    inputs.setdefault(picked[obs]["epoch"], []).append((img, w, picked[obs]["time_utc"]))
    print("loaded", f.name, img.shape, flush=True)

allin = [(i, w) for v in inputs.values() for i, w, _ in v]
wcs_out, shape = find_optimal_celestial_wcs(allin, resolution=6.15 * u.arcsec)
if max(shape) * 6.15 / 3600 > max_side:  # keep it manageable
    scale = max(shape) * 6.15 / 3600 / max_side
    wcs_out, shape = find_optimal_celestial_wcs(allin, resolution=6.15 * scale * u.arcsec)
print("output grid", shape, f"= {shape[1] * abs(wcs_out.wcs.cdelt[0]):.2f} x {shape[0] * abs(wcs_out.wcs.cdelt[1]):.2f} deg", flush=True)

mosaics, summary = {}, {"epochs": []}
for ep, items in sorted(inputs.items()):
    t = time.time()
    mos, foot = reproject_and_coadd([(i, w) for i, w, _ in items], wcs_out, shape_out=shape,
                                    reproject_function=reproject_interp, combine_function="mean", match_background=True)
    mos[foot == 0] = np.nan
    mosaics[ep] = mos.astype(np.float32)
    area = float(np.sum(foot > 0)) * (abs(wcs_out.wcs.cdelt[0]) ** 2)
    summary["epochs"].append({"epoch": ep, "n_images": len(items), "area_deg2": round(area, 2),
                              "dates": sorted({tm[:10] for _, _, tm in items})})
    print(f"epoch {ep}: {len(items)} full images stitched, {area:.1f} deg^2 covered, {time.time() - t:.0f}s", flush=True)

allv = np.concatenate([m[np.isfinite(m)][::50] for m in mosaics.values()])
summary["cuts"] = [float(np.percentile(allv, 1)), float(np.percentile(allv, 99.7))]
c = wcs_out.pixel_to_world_values((shape[1] - 1) / 2, (shape[0] - 1) / 2)
summary.update({"ra_deg": float(c[0]), "dec_deg": float(c[1]), "field_deg": round(shape[1] * abs(wcs_out.wcs.cdelt[0]), 2)})
for ep, mos in mosaics.items():
    d = out / f"epoch{ep}"
    shutil.rmtree(d, ignore_errors=True)
    t = time.time()
    reproject_to_hips((mos, wcs_out), coord_system_out="equatorial", reproject_function=reproject_interp,
                      output_directory=str(d), tile_size=256, threads=True,
                      properties={"obs_title": f"SPHEREx D1 epoch {ep}, wide stitch test", "creator_did": f"ivo://local/spherex-wide-epoch{ep}"})
    n = len(list(d.rglob("*.fits")))
    summary["epochs"][[x["epoch"] for x in summary["epochs"]].index(ep)]["tiles"] = n
    print(f"epoch {ep}: {n} tiles, {time.time() - t:.0f}s", flush=True)
(out / "summary.json").write_text(json.dumps(summary, indent=1))
print(json.dumps(summary))
