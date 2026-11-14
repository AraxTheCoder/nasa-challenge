"""T09: do we recover known asteroids in real SPHEREx data at the predicted position?

    python -m detect.known_check data/targets/<id> [<more target dirs>] [--no-mag] [--json out.json]
    python -m detect.known_check --object 29 --date 2026-07-29 [--window 0.5]   # a bright asteroid, see below

For every known object position (T07/T51: predicted for the frame time, as seen from SPHEREx):

1. Brightness: aperture photometry (T49, `pipeline.photometry`) at the predicted sky position in that frame,
   minus the median of the same sky position in the frames of the *other* epochs and the same detector
   (the asteroid has long moved on, whatever sits there for good cancels). S/N = difference / error, the
   error from the frame's own error and the scatter of the reference frames.
2. Position: on the aligned frames (all on one grid), the frame minus the median of those reference frames,
   each frame robust-normalised first (display PNGs have their own stretch). The brightest pixel within
   SEARCH_PX of the prediction, refined by a 3x3 centroid, gives the offset.
3. Control: the same at CONTROL positions (prediction shifted by CONTROL_SHIFT_PX in 4 directions), to see
   how often empty sky looks like a recovery.

A position counts as recovered when S/N >= SN_MIN and the peak lies within MAX_OFFSET_PX of the prediction.
Optional: the predicted V magnitude from JPL Horizons (one request per object), to see down to which
brightness it works.

Bright-asteroid mode (`--object`): built fields keep 2 images per epoch and detector, so they rarely contain
the few exposures a given bright asteroid is in. This mode takes exactly those: JPL Horizons gives the
asteroid's position seen from SPHEREx, the local image index (T31) the exposures that cover it within
`--window` days of `--date`; each is checked like above against up to REFS_PER_DETECTOR exposures of the same
sky in other epochs (same detector), on small IRSA cutouts, with the difference image on the exposure's own
pixel grid (references reprojected onto it).
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

import numpy as np

SN_MIN = 5.0
MAX_OFFSET_PX = 1.5          # ~9": positions ~1", PSF ~1 px, frames resampled once
SEARCH_PX = 3.0
CONTROL_SHIFT_PX = 15.0
REFS_PER_DETECTOR = 4


def load_frame(path: Path) -> np.ndarray:
    """Frame PNG as float, NaN where alpha is 0 (no data)."""
    from PIL import Image
    im = Image.open(path)
    a = np.asarray(im.convert("LA"), dtype=float)
    img = a[..., 0]
    img[a[..., 1] == 0] = np.nan
    return img


def normalise(img: np.ndarray) -> np.ndarray:
    med = np.nanmedian(img)
    mad = np.nanmedian(np.abs(img - med)) * 1.4826
    return (img - med) / (mad if mad > 0 else 1.0)


def peak_near(diff: np.ndarray, x: float, y: float, r: float = SEARCH_PX) -> tuple[float, float, float] | None:
    """(x, y, peak) of the brightest pixel within r of (x, y), centroided over its 3x3 neighbourhood."""
    h, w = diff.shape
    best = None
    for yy in range(max(0, int(y - r)), min(h, int(y + r) + 2)):
        for xx in range(max(0, int(x - r)), min(w, int(x + r) + 2)):
            if math.hypot(xx - x, yy - y) <= r and np.isfinite(diff[yy, xx]) and (best is None or diff[yy, xx] > best[2]):
                best = (xx, yy, float(diff[yy, xx]))
    if best is None:
        return None
    bx, by, pk = best
    win = diff[max(0, by - 1):by + 2, max(0, bx - 1):bx + 2]
    wts = np.where(np.isfinite(win), np.clip(win, 0, None), 0)
    if wts.sum() > 0:
        ys, xs = np.mgrid[max(0, by - 1):by + 2, max(0, bx - 1):bx + 2]
        return float((xs * wts).sum() / wts.sum()), float((ys * wts).sum() / wts.sum()), pk
    return float(bx), float(by), pk


def _flux_check(target: dict, frame: dict, refs: list[dict], ra: float, dec: float, raw_root) -> dict:
    from pipeline.photometry import measure
    m = measure(target, ra, dec, raw_root=raw_root)
    by = {r["frame_id"]: r for r in m["frames"]}
    me = by.get(frame["id"])
    ref = [by[g["id"]] for g in refs if g["id"] in by and not by[g["id"]]["masked"] and by[g["id"]]["flux_ujy"] is not None]
    if not me or me["masked"] or me["flux_ujy"] is None or len(ref) < 2:
        return {"flux_ujy": None, "sn": None, "n_ref": len(ref), "wavelength_um": me and me["wavelength_um"],
                "note": "flagged" if me and me["masked"] else "no cutout" if not me else "too few reference frames"}
    rf = [r["flux_ujy"] for r in ref]
    base = statistics.median(rf)
    mad = statistics.median(abs(v - base) for v in rf) * 1.4826
    err = math.hypot(me["err_ujy"] or 0.0, mad, statistics.median(r["err_ujy"] or 0.0 for r in ref))
    delta = me["flux_ujy"] - base
    return {"flux_ujy": round(delta, 1), "err_ujy": round(err, 1), "sn": round(delta / err, 1) if err > 0 else None,
            "n_ref": len(ref), "wavelength_um": me["wavelength_um"]}


def _position_check(tdir: Path, frame: dict, refs: list[dict], x: float, y: float) -> dict:
    img = normalise(load_frame(tdir / frame["image"]))
    stack = [normalise(load_frame(tdir / g["image"])) for g in refs]
    if len(stack) < 2:
        return {"offset_px": None, "peak_sigma": None}
    with np.errstate(all="ignore"):
        ref = np.nanmedian(np.stack(stack), axis=0)
    diff = img - ref
    scale = np.nanmedian(np.abs(diff - np.nanmedian(diff))) * 1.4826 or 1.0
    found = peak_near(diff / scale, x, y)
    if found is None:
        return {"offset_px": None, "peak_sigma": None}
    px, py, pk = found
    return {"offset_px": round(math.hypot(px - x, py - y), 2), "peak_sigma": round(pk, 1), "peak_x": round(px, 2), "peak_y": round(py, 2)}


def _mag(name: str, jd: float) -> float | None:
    """Predicted V magnitude seen from SPHEREx (JPL Horizons quantity 9)."""
    from .known_objects import HORIZONS, SPHEREX, Jpl, horizons_command, parse_horizons_table
    params = {"format": "json", "COMMAND": f"'{horizons_command(name)}'", "OBJ_DATA": "'NO'", "MAKE_EPHEM": "'YES'",
              "EPHEM_TYPE": "'OBSERVER'", "CENTER": f"'500@{SPHEREX}'", "QUANTITIES": "'9'", "CSV_FORMAT": "'YES'",
              "TIME_TYPE": "'UT'", "TLIST_TYPE": "'JD'", "TLIST": f"'{jd:.6f}'"}
    try:
        row = parse_horizons_table(Jpl()._get(HORIZONS, params, "JPL Horizons (V mag)")["result"])[0]
        vals = [c for c in row[3:] if c not in ("", "n.a.")]
        return float(vals[0]) if vals else None
    except Exception as e:  # noqa: BLE001 - magnitudes are a nice-to-have
        print(f"known_check: no V for {name}: {e}", file=sys.stderr)
        return None


def check_target(tdir: Path, raw_root=None, mags: bool = True) -> dict:
    """Recovery check for every known object position of one built target."""
    t = json.loads((tdir / "target.json").read_text(encoding="utf-8"))
    frames = {f["id"]: f for f in t["frames"]}
    rows, controls = [], []
    for k in t.get("known_objects", []):
        if k.get("synthetic"):
            continue
        v = _mag(k["name"], frames[k["positions"][0]["frame_id"]]["mjd"] + 2400000.5) if mags and k["positions"] else None
        for p in k["positions"]:
            f = frames[p["frame_id"]]
            refs = [g for g in t["frames"] if g["epoch"] != f["epoch"] and g["detector"] == f["detector"]]
            row = {"target": t["id"], "object": k["name"], "frame_id": f["id"], "epoch": f["epoch"], "detector": f["detector"],
                   "x": p["x"], "y": p["y"], "v_mag": v,
                   **_flux_check(t, f, refs, p["ra_deg"], p["dec_deg"], raw_root), **_position_check(tdir, f, refs, p["x"], p["y"])}
            row["recovered"] = bool(row["sn"] is not None and row["sn"] >= SN_MIN and row["offset_px"] is not None
                                    and row["offset_px"] <= MAX_OFFSET_PX)
            rows.append(row)
            scale = t["image"]["pixel_scale_arcsec"] / 3600
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                cx, cy = p["x"] + dx * CONTROL_SHIFT_PX, p["y"] + dy * CONTROL_SHIFT_PX
                if not (0 <= cx < t["image"]["width"] and 0 <= cy < t["image"]["height"]):
                    continue
                cra = p["ra_deg"] - dx * CONTROL_SHIFT_PX * scale / math.cos(math.radians(p["dec_deg"]))
                cdec = p["dec_deg"] - dy * CONTROL_SHIFT_PX * scale
                c = {**_flux_check(t, f, refs, cra, cdec, raw_root), **_position_check(tdir, f, refs, cx, cy)}
                c["recovered"] = bool(c["sn"] is not None and c["sn"] >= SN_MIN and c["offset_px"] is not None
                                      and c["offset_px"] <= MAX_OFFSET_PX)
                controls.append(c)
    return {"target": t["id"], "rows": rows, "controls": controls}


# ---------- bright-asteroid mode ----------

def _cutout(fits_url: str, ra: float, dec: float, size_deg: float, raw_root: Path) -> Path:
    """Small IRSA cutout (IMAGE, FLAGS, VARIANCE, ZODI, WCS-WAVE), cached like pipeline.build's."""
    from pipeline import build
    d = build._cutout_dir(fits_url, ra, dec, raw_root)
    path = d / f"{size_deg:.4f}.fits"
    if not path.exists():
        d.mkdir(parents=True, exist_ok=True)
        path.write_bytes(build._get_with_retry(build.cutout_url(fits_url, ra, dec, size_deg)))
    return path


def _try_cutout(fits_url: str, ra: float, dec: float, size_deg: float, raw_root: Path) -> Path | None:
    """_cutout, or None if IRSA doesn't have the image (the local index can hold outdated paths, T31)."""
    try:
        return _cutout(fits_url, ra, dec, size_deg, raw_root)
    except Exception as e:  # noqa: BLE001
        print(f"known_check: skipped {fits_url.rsplit('/', 1)[-1]}: {e}", file=sys.stderr)
        return None


def _image(path: Path):
    """(image minus its median, WCS) of a cutout; NaN where flagged."""
    import warnings
    from astropy.io import fits
    from astropy.wcs import WCS, FITSFixedWarning
    from pipeline import build
    with fits.open(path) as hd, warnings.catch_warnings():
        warnings.simplefilter("ignore", FITSFixedWarning)
        img = hd["IMAGE"].data.astype(float)
        img[(hd["FLAGS"].data.astype(np.int64) & build.HW_MASK) != 0] = np.nan
        return img - np.nanmedian(img), WCS(hd["IMAGE"].header)


def _diff_position(path: Path, ref_paths: list[Path], ra: float, dec: float) -> dict:
    from reproject import reproject_interp
    img, w = _image(path)
    refs = []
    for rp in ref_paths:
        r, rw = _image(rp)
        refs.append(reproject_interp((r, rw), w, shape_out=img.shape, return_footprint=False))
    if len(refs) < 2:
        return {"offset_px": None, "peak_sigma": None}
    with np.errstate(all="ignore"):
        diff = img - np.nanmedian(np.stack(refs), axis=0)
    scale = np.nanmedian(np.abs(diff - np.nanmedian(diff))) * 1.4826 or 1.0
    x, y = (float(v) for v in w.all_world2pix(ra, dec, 0))
    found = peak_near((diff - np.nanmedian(diff)) / scale, x, y)
    if found is None:
        return {"offset_px": None, "peak_sigma": None}
    px, py, pk = found
    return {"offset_px": round(math.hypot(px - x, py - y), 2), "peak_sigma": round(pk, 1)}


def check_object(name: str, mjd: float, window_d: float = 0.5, raw_root: Path | None = None) -> dict:
    """Bright-asteroid mode: every exposure covering `name` within window_d days of mjd, checked against
    the same sky in other epochs."""
    from pipeline import build, mirror
    from pipeline.photometry import measure_cutout
    from .known_objects import Jpl
    raw_root = raw_root or build.RAW_ROOT
    jpl = Jpl()
    ra0, dec0 = jpl.positions(name, [mjd + 2400000.5])[0]
    cover = mirror.find_exposures_local(ra0, dec0)[0]
    cands = [e for e in cover if abs(e.mjd_mid - mjd) <= window_d]
    if not cands:
        return {"object": name, "rows": [], "controls": [], "note": "no exposure covers it in this window"}
    pos = jpl.positions(name, [e.mjd_mid + 2400000.5 for e in cands])
    # one cutout per exposure, centred on the window's middle, big enough for the asteroid's motion
    motion = max(math.hypot((ra - ra0) * math.cos(math.radians(dec0)), dec - dec0) for ra, dec in pos)
    size = round(2 * motion + 0.12, 3)
    v = _mag(name, mjd + 2400000.5)
    refs_by_det: dict[int, list] = {}
    rows, controls = [], []
    for e, (ra, dec) in zip(cands, pos):
        if e.detector not in refs_by_det:
            others = [x for x in cover if x.epoch != e.epoch and x.detector == e.detector]
            step = max(1, len(others) // REFS_PER_DETECTOR)
            got = []
            for x in others[::step] + [o for i, o in enumerate(others) if i % step]:  # spread out, then the rest
                if len(got) == REFS_PER_DETECTOR:
                    break
                p = _try_cutout(x.fits_url, ra0, dec0, size, raw_root)
                if p:
                    got.append(p)
            refs_by_det[e.detector] = got
        refs = refs_by_det[e.detector]
        path = _try_cutout(e.fits_url, ra0, dec0, size, raw_root)
        if path is None:
            rows.append({"target": "exposures", "object": name, "frame_id": e.obs_id, "epoch": e.epoch, "detector": e.detector,
                         "mjd": e.mjd_mid, "v_mag": v, "flux_ujy": None, "sn": None, "wavelength_um": None,
                         "offset_px": None, "peak_sigma": None, "note": "image not found at IRSA (reprocessed?)"})
            continue

        def one(r, d):
            m = measure_cutout(path, r, d)
            if m is None or m["masked"] or m["flux_ujy"] is None:
                return {"flux_ujy": None, "sn": None, "wavelength_um": m and m["wavelength_um"],
                        "note": "off the image" if m is None else "flagged", **_diff_position(path, refs, r, d)}
            rm = [x for x in (measure_cutout(p, r, d) for p in refs) if x and not x["masked"] and x["flux_ujy"] is not None]
            if len(rm) < 2:
                return {"flux_ujy": None, "sn": None, "wavelength_um": m["wavelength_um"], "note": "too few references"}
            rf = [x["flux_ujy"] for x in rm]
            base = statistics.median(rf)
            mad = statistics.median(abs(x - base) for x in rf) * 1.4826
            err = math.hypot(m["err_ujy"] or 0.0, mad, statistics.median(x["err_ujy"] or 0.0 for x in rm))
            delta = m["flux_ujy"] - base
            return {"flux_ujy": round(delta, 1), "err_ujy": round(err, 1), "sn": round(delta / err, 1) if err > 0 else None,
                    "n_ref": len(rm), "wavelength_um": m["wavelength_um"], **_diff_position(path, refs, r, d)}

        row = {"target": "exposures", "object": name, "frame_id": e.obs_id, "epoch": e.epoch, "detector": e.detector,
               "mjd": e.mjd_mid, "v_mag": v, **one(ra, dec)}
        rows.append(row)
        shift = CONTROL_SHIFT_PX * 6.15 / 3600
        for dra, ddec in ((shift / math.cos(math.radians(dec)), 0), (0, shift)):
            controls.append(one(ra + dra, dec + ddec))
    for r in rows + controls:
        r["recovered"] = bool(r.get("sn") is not None and r["sn"] >= SN_MIN and r.get("offset_px") is not None
                              and r["offset_px"] <= MAX_OFFSET_PX)
    return {"target": f"{name} around MJD {mjd:.2f}", "rows": rows, "controls": controls,
            "provenance": jpl.log + [{"service": "SPHEREx image index (local mirror, T31) + IRSA cutouts",
                                       "query": f"{len(cands)} exposures within {window_d} d, cutouts {size} deg"}]}


def summary(results: list[dict]) -> dict:
    rows = [r for res in results for r in res["rows"]]
    ctrl = [c for res in results for c in res["controls"]]
    measured = [r for r in rows if r["sn"] is not None]
    objs: dict[tuple, list] = {}
    for r in rows:
        objs.setdefault((r["target"], r["object"]), []).append(r)
    rec = [r for r in measured if r["recovered"]]
    return {
        "positions": len(rows), "measured": len(measured), "recovered": len(rec),
        "objects": len(objs), "objects_recovered": sum(any(r["recovered"] for r in v) for v in objs.values()),
        "median_offset_px": round(statistics.median(r["offset_px"] for r in rec), 2) if rec else None,
        "controls": len([c for c in ctrl if c["sn"] is not None]), "controls_recovered": sum(c["recovered"] for c in ctrl),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m detect.known_check", description=__doc__.split("\n\n")[0])
    ap.add_argument("target_dirs", nargs="*", type=Path)
    ap.add_argument("--object", help="bright-asteroid mode: a small-body name or number, e.g. 29 or '(29) Amphitrite'")
    ap.add_argument("--date", help="bright-asteroid mode: the day (YYYY-MM-DD) or MJD to look at")
    ap.add_argument("--window", type=float, default=0.5, help="days around --date (default 0.5)")
    ap.add_argument("--no-mag", action="store_true", help="skip the V magnitudes from JPL Horizons")
    ap.add_argument("--json", type=Path, help="write all rows + summary here")
    args = ap.parse_args(argv)
    results = [check_target(d, mags=not args.no_mag) for d in args.target_dirs]
    if args.object:
        if not args.date:
            ap.error("--object needs --date")
        from astropy.time import Time
        mjd = float(args.date) if args.date.replace(".", "").isdigit() else Time(args.date).mjd
        results.append(check_object(args.object, mjd, args.window))
    if not results:
        ap.error("give target dirs or --object/--date")
    print(f"{'object':<26} {'frame':<5} {'D':>1} {'λ µm':>5} {'V':>5} {'Δflux µJy':>10} {'S/N':>6} {'off px':>6} {'peak σ':>6}  ok")
    for res in results:
        for r in res["rows"]:
            fmt = lambda v, f: "–" if v is None else format(v, f)  # noqa: E731
            print(f"{r['object'][:26]:<26} {r['frame_id'][-8:]:<5} {r['detector']:>1} {fmt(r['wavelength_um'], '.2f'):>5} {fmt(r['v_mag'], '.1f'):>5} "
                  f"{fmt(r['flux_ujy'], '.0f'):>10} {fmt(r['sn'], '.1f'):>6} {fmt(r['offset_px'], '.2f'):>6} {fmt(r['peak_sigma'], '.1f'):>6}  "
                  f"{'yes' if r['recovered'] else 'no'}{'  (' + r['note'] + ')' if r.get('note') else ''}")
    s = summary(results)
    print(json.dumps(s))
    if args.json:
        args.json.write_text(json.dumps({"summary": s, "results": results}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
