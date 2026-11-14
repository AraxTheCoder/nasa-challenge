"""Reference (exploration code, not the pipeline): align cutouts, render PNGs, matched pairs.

    python pipeline/reference/align_render.py <query.json> <cutout_dir> <out_dir> [size_px]

<query.json> comes from `python -m pipeline.query --out`, <cutout_dir> from fetch_cutouts.py.
Writes frames/*.png (grey + alpha, no data = alpha 0), resid/*.png (minus the median of all
frames), pairdiff/*.png (wavelength-matched pairs, CONTRACTS v0.2 rule), summary.json, stack.npy.
Used for the COSMOS and Barnard's Star checks on 2026-11-14; see pipeline/reference/README.md."""
import json, sys, warnings
from pathlib import Path
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS, FITSFixedWarning
from reproject import reproject_interp
from PIL import Image

warnings.simplefilter("ignore", FITSFixedWarning)
q = json.load(open(sys.argv[1])); cdir = Path(sys.argv[2]); out = Path(sys.argv[3])
(out / "frames").mkdir(parents=True, exist_ok=True); (out / "resid").mkdir(exist_ok=True)
ra0, dec0 = q["ra_deg"], q["dec_deg"]
N, SCALE = int(sys.argv[4]) if len(sys.argv) > 4 else 128, 6.15 / 3600
tw = WCS(naxis=2)
tw.wcs.ctype = ["RA---TAN", "DEC--TAN"]; tw.wcs.crval = [ra0, dec0]
tw.wcs.crpix = [(N + 1) / 2, (N + 1) / 2]; tw.wcs.cdelt = [-SCALE, SCALE]
meta = {e["obs_id"]: e for e in q["exposures"]}

frames, stack = [], []
for f in sorted(cdir.glob("*.fits")):
    obs = f.name.split("_D")[0]; e = meta[obs]
    with fits.open(f) as h:
        img = h["IMAGE"].data.astype(float); flags = h["FLAGS"].data
        zodi = h["ZODI"].data.astype(float)
        w = WCS(h["IMAGE"].header)
        hdr = h["IMAGE"].header
        wt = h["WCS-WAVE"].data
        # (wavelength, bandwidth) on an n x n grid of 1-based detector pixels; VALUES[y][x]
        X = np.array(wt["X"][0], float); Y = np.array(wt["Y"][0], float)
        V = np.array(wt["VALUES"][0]).reshape(len(Y), len(X), 2)
        # "A" WCS: detector coordinate = 1-based cutout pixel - CRPIXnA (0-based) -> +1 for 1-based
        cx, cy = w.world_to_pixel_values(ra0, dec0)
        dx, dy = cx + 1 - hdr["CRPIX1A"] + 1, cy + 1 - hdr["CRPIX2A"] + 1
        from scipy.interpolate import RegularGridInterpolator
        wave = float(RegularGridInterpolator((Y, X), V[..., 0], bounds_error=False, fill_value=None)([[dy, dx]])[0])
        bw = float(RegularGridInterpolator((Y, X), V[..., 1], bounds_error=False, fill_value=None)([[dy, dx]])[0])
    sci = img - zodi
    sci[(flags & 503467591) != 0] = np.nan  # hardware/artifact planes only; keep SOURCE(21) and OUTLIER(19)
    arr, foot = reproject_interp((sci, w), tw, shape_out=(N, N))
    arr[foot < 0.5] = np.nan
    frames.append({"obs_id": obs, "time_utc": e["time_utc"], "mjd": e["mjd_mid"], "epoch": e["epoch"],
                   "wavelength_um": round(wave, 4), "bandwidth_um": round(bw, 4), "flag_frac": float(np.mean((flags & 503467591) != 0)), "outlier_frac": float(np.mean((flags>>19)&1)),
                   "median": float(np.nanmedian(arr)), "std": float(np.nanstd(arr)),
                   "zodi_median": float(np.median(zodi))})
    stack.append(arr)

order = np.argsort([fr["mjd"] for fr in frames])
frames = [frames[i] for i in order]; stack = np.array([stack[i] for i in order])
stack -= np.nanmedian(stack, axis=(1, 2))[:, None, None]
np.save(out / "stack.npy", stack)
med = np.nanmedian(stack, axis=0)
lo, hi = np.nanpercentile(med, 1), np.nanpercentile(med, 99.7)

def to8(a, lo, hi, asinh=True, nanval=0.0):
    # grey + alpha; no-data pixels (NaN) get alpha 0 per CONTRACTS v0.2
    x = np.clip((a - lo) / (hi - lo), 0, 1)
    if asinh: x = np.arcsinh(10 * x) / np.arcsinh(10)
    alpha = np.where(np.isfinite(a), 255, 0).astype(np.uint8)
    x = np.nan_to_num(x, nan=nanval)
    la = np.dstack([(x * 255).astype(np.uint8), alpha])[::-1]  # FITS y up -> PNG y down
    return Image.fromarray(la, mode="LA")

noise = np.nanmedian([np.nanstd(s - med) for s in stack])
for i, (fr, a) in enumerate(zip(frames, stack)):
    fid = f"f{i:03d}"; fr["id"] = fid
    to8(a, lo, hi).save(out / "frames" / f"{fid}.png")
    r = a - med
    to8(r, -5 * noise, 5 * noise, asinh=False, nanval=0.5).save(out / "resid" / f"{fid}.png")
    # strongest positive residual blobs = candidates (stars subtract out, movers don't)
    rs = np.nan_to_num(r / noise)
    peaks = []
    for _ in range(3):
        k = np.unravel_index(np.argmax(rs), rs.shape)
        if rs[k] < 8: break
        sky = tw.pixel_to_world_values(k[1], k[0])
        peaks.append({"x": int(k[1]), "y": int(N - 1 - k[0]), "snr": round(float(rs[k]), 1),
                      "ra": round(float(sky[0]), 5), "dec": round(float(sky[1]), 5)})
        rs[max(0, k[0]-4):k[0]+5, max(0, k[1]-4):k[1]+5] = 0
    fr["residual_peaks"] = peaks
to8(med, lo, hi).save(out / "median.png")
# wavelength-matched pairs across epochs (CONTRACTS v0.2 rule)
(out / "pairdiff").mkdir(exist_ok=True)
pairs = []
eps = sorted({f["epoch"] for f in frames})
for i, ea in enumerate(eps):
    for eb in eps[i + 1:]:
        A = [k for k, f in enumerate(frames) if f["epoch"] == ea]
        B = [k for k, f in enumerate(frames) if f["epoch"] == eb]
        cand = sorted((abs(frames[a]["wavelength_um"] - frames[b]["wavelength_um"]), a, b) for a in A for b in B)
        used_a, used_b = set(), set()
        for dw, a, b in cand:
            tol = 0.5 * min(frames[a]["bandwidth_um"], frames[b]["bandwidth_um"])
            if dw > tol or a in used_a or b in used_b: continue
            used_a.add(a); used_b.add(b)
            fa, fb = frames[a], frames[b]
            d = stack[b] - stack[a]
            pid = f"{fa['id']}-{fb['id']}"
            to8(d, -5 * noise * 1.4, 5 * noise * 1.4, asinh=False, nanval=0.5).save(out / "pairdiff" / f"{pid}.png")
            pairs.append({"a": fa["id"], "b": fb["id"], "detector": None, "dwave_um": round(dw, 4),
                          "dt_days": round(fb["mjd"] - fa["mjd"], 2), "rms": round(float(np.nanstd(d)), 4)})
pairs.sort(key=lambda p: p["a"])
print("pairs", len(pairs), [(p["a"], p["b"], p["dwave_um"]) for p in pairs])
print("rms pair diff", np.median([p["rms"] for p in pairs]), "vs median-resid", noise)
json.dump({"ra_deg": ra0, "dec_deg": dec0, "size_px": N, "pixel_scale_arcsec": 6.15, "noise_mjysr": noise,
           "frames": frames, "pairs": pairs}, open(out / "summary.json", "w"), indent=1)
for fr in frames:
    print(fr["id"], fr["epoch"], fr["time_utc"], fr["wavelength_um"], f"flag={fr['flag_frac']:.2f}",
          f"zodi={fr['zodi_median']:.3f}", fr["residual_peaks"])
print("noise", noise)
