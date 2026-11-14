"""T91: a star's proper motion measured from SPHEREx alone.

The viewer draws a star's catalogue path (T19/T22); here its position is *measured* in every SPHEREx exposure and
turned into a motion with an error bar, to set next to Gaia's value ("SPHEREx: 10.3 ± 0.2″/yr, Gaia: 10.39").

1. Every exposure covering the field (the same field-sized cutouts as T85, cached) gives the star's position:
   a 2-D Gaussian fitted to a small stamp around where it should be, flagged pixels left out. For a saturated
   star the flagged core is ignored and its unsaturated wings fix the centre. The catalogue track is only used
   to *find* the star (search box ±SEARCH_PX); it does not enter the measurement.
2. Each exposure's own pointing error is taken out with the field's reference stars: unsaturated, isolated Gaia
   stars whose catalogue positions (moved by their proper motions) are known to milliarcseconds. Their median
   offset is that exposure's correction.
3. Positions per epoch (robust mean, error from the scatter), then a weighted straight line through the epochs:
   µα*, µδ, total and direction with 1-σ errors. With three or more epochs the parallax is fitted as well (the
   yearly wobble from Earth's orbit; SPHEREx is in low Earth orbit), which gives the distance.

    python -m pipeline.astrometry data/targets/<id> --name "Barnard's star"
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from . import build, fieldspectra, photometry

LOCKED_ARCSEC = 3.0      # measured this far from the catalogue track in every epoch: not the star (a neighbour)
PLX_MAX_CHI2 = 3.0       # a parallax is believed only if position + motion + parallax fit the epochs this well
STAMP_PX = 5             # half-size of the fitted stamp (11 x 11 native pixels, 68″)
SEARCH_PX = 4.0          # the fitted centre must lie within this of where the star should be
REF_MAX = 40             # reference stars per field
REF_MIN = 5
REF_ISOLATION_ARCSEC = 30.0
MIN_SNR = 5.0
VERSION = 1
ROOT = Path("data/motion")


def _gauss_fit(stamp, bad, x0, y0):
    """Fit amp*exp(-r²/2s²)+bg to the unflagged pixels; (x, y, err_x, err_y, snr) in stamp pixels or None."""
    from scipy.optimize import curve_fit
    ny, nx = stamp.shape
    yy, xx = np.mgrid[0:ny, 0:nx]
    ok = ~bad & np.isfinite(stamp)
    if ok.sum() < 12:
        return None
    z, X, Y = stamp[ok], xx[ok], yy[ok]
    bg0 = float(np.median(np.concatenate([stamp[0][ok[0]], stamp[-1][ok[-1]], stamp[:, 0][ok[:, 0]], stamp[:, -1][ok[:, -1]]]))) \
        if ok[0].any() else float(np.median(z))
    amp0 = max(float(z.max() - bg0), 1e-6)

    def model(xy, amp, x, y, s, bg):
        return amp * np.exp(-((xy[0] - x) ** 2 + (xy[1] - y) ** 2) / (2 * s * s)) + bg

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            p, cov = curve_fit(model, (X, Y), z, p0=[amp0, x0, y0, 1.0, bg0],
                               bounds=([0, 0, 0, 0.4, -np.inf], [np.inf, nx - 1, ny - 1, 3.5, np.inf]), maxfev=4000)
    except Exception:  # noqa: BLE001 - no convergence: no position from this exposure
        return None
    resid = z - model((X, Y), *p)
    noise = 1.4826 * float(np.median(np.abs(resid - np.median(resid)))) or float(np.std(resid)) or 1e-9
    flux = 2 * math.pi * p[0] * p[3] ** 2
    snr = flux / (noise * math.sqrt(4 * math.pi * p[3] ** 2))
    ex, ey = (math.sqrt(max(cov[i, i], 0)) if np.all(np.isfinite(cov)) else math.inf for i in (1, 2))
    return float(p[1]), float(p[2]), ex, ey, float(snr), float(p[3])


def _measure(path: Path, positions):
    """Fitted sky position of each (ra, dec) guess in one cutout: [(ra, dec, err_arcsec, snr) | None]."""
    from astropy.io import fits
    from astropy.wcs import WCS, FITSFixedWarning
    from astropy.wcs.utils import proj_plane_pixel_scales

    with fits.open(path) as hd, warnings.catch_warnings():
        warnings.simplefilter("ignore", FITSFixedWarning)
        img = hd["IMAGE"].data.astype(float)
        bad = ((hd["FLAGS"].data.astype(np.int64) & build.HW_MASK) != 0) | ~np.isfinite(img)
        w = WCS(hd["IMAGE"].header)
    scale = float(np.mean(proj_plane_pixel_scales(w))) * 3600
    xs, ys = w.all_world2pix([p[0] for p in positions], [p[1] for p in positions], 0)
    ny, nx = img.shape
    out = []
    for x, y in zip(xs, ys):
        if not (np.isfinite(x) and np.isfinite(y)):
            out.append(None)
            continue
        xi, yi = int(round(x)), int(round(y))
        if not (STAMP_PX <= xi < nx - STAMP_PX and STAMP_PX <= yi < ny - STAMP_PX):
            out.append(None)
            continue
        sl = (slice(yi - STAMP_PX, yi + STAMP_PX + 1), slice(xi - STAMP_PX, xi + STAMP_PX + 1))
        f = _gauss_fit(img[sl], bad[sl], x - (xi - STAMP_PX), y - (yi - STAMP_PX))
        if f is None:
            out.append(None)
            continue
        fx, fy, ex, ey, snr, _ = f
        px, py = fx + xi - STAMP_PX, fy + yi - STAMP_PX
        if math.hypot(px - x, py - y) > SEARCH_PX or snr < MIN_SNR or not math.isfinite(ex):
            out.append(None)
            continue
        ra, dec = w.all_pix2world(px, py, 0)
        out.append((float(ra), float(dec), math.hypot(ex, ey) / math.sqrt(2) * scale, snr))
    return out


def parallax_factors(ra: float, dec: float, mjd: float) -> tuple[float, float]:
    """(east, north) shift in arcsec per arcsec of parallax at that moment: minus Earth's barycentric position
    (AU) projected on the sky's east and north directions at (ra, dec)."""
    from astropy.coordinates import get_body_barycentric
    from astropy.time import Time
    p = get_body_barycentric("earth", Time(mjd, format="mjd", scale="tdb")).xyz.to("AU").value
    a, d = math.radians(ra), math.radians(dec)
    east = np.array([-math.sin(a), math.cos(a), 0.0])
    north = np.array([-math.sin(d) * math.cos(a), -math.sin(d) * math.sin(a), math.cos(d)])
    return float(-p @ east), float(-p @ north)


def _track_offset(star: dict, mjd: float) -> tuple[float, float]:
    """Where the catalogue track puts the star at mjd, as (east, north) arcsec from its reference position."""
    (ra, dec), = fieldspectra.positions_at([star], mjd)
    return _offset_arcsec(ra, dec, star["ra_deg"], star["dec_deg"])


def _offset_arcsec(ra, dec, ra0, dec0):
    """(east, north) of (ra, dec) from (ra0, dec0) in arcsec."""
    return ((ra - ra0 + 180) % 360 - 180) * math.cos(math.radians(dec0)) * 3600, (dec - dec0) * 3600


def _references(sources: list[dict], target: dict) -> list[dict]:
    """Isolated, unsaturated-looking Gaia stars with a catalogue track (T85 sources)."""
    gaia = [s for s in sources if s["source"] == "gaia_dr3" and s is not target and s.get("mag") is not None
            and 10.5 <= s["mag"] <= 15.5]
    out = []
    for s in sorted(gaia, key=lambda s: s["mag"]):
        if all(fieldspectra._sep_arcsec(s, o) > REF_ISOLATION_ARCSEC for o in sources if o is not s):
            out.append(s)
        if len(out) >= REF_MAX:
            break
    return out


def _one(e, ra0, dec0, size_deg, track):
    try:
        path = photometry._spectrum_cutout(e.fits_url, ra0, dec0, size_deg)
        return e, _measure(path, fieldspectra.positions_at(track, e.mjd_mid))
    except Exception:  # noqa: BLE001 - a missing exposure is just one point less
        return e, None


def _batch(exposures, ra0, dec0, size_deg, track):
    with ThreadPoolExecutor(len(exposures)) as pool:
        return list(pool.map(lambda e: _one(e, ra0, dec0, size_deg, track), exposures))


def cache_path(target_id: str, label_id: str) -> Path:
    return ROOT / f"{target_id}__{label_id}.json"


def cached(target: dict, name: str) -> dict | None:
    star = find_star(target, name)
    p = cache_path(target["id"], star["id"]) if star else None
    if p and p.is_file():
        r = json.loads(p.read_text(encoding="utf-8"))
        if r.get("version") == VERSION:
            return r
    return None


def find_star(target: dict, name: str) -> dict | None:
    key = name.lower()
    return next((s for s in fieldspectra.sources_of(target) if key in (s["name"] or "").lower() or s["id"] == name
                 or any(key in (a or "").lower() for a in s.get("aliases", []))), None)


def measure_motion(target: dict, name: str, processes: int | None = None, progress=None) -> dict:
    """measure_motion_uncached + a cache per (field, label) under data/motion/."""
    hit = cached(target, name)
    if hit:
        return hit
    r = measure_motion_uncached(target, name, processes=processes, progress=progress)
    if r.get("id") or r.get("status") in ("not_found", "not_enough"):
        star = find_star(target, name)
        p = cache_path(target["id"], star["id"])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({**r, "id": star["id"]}), encoding="utf-8")
    return r


def measure_motion_uncached(target: dict, name: str, processes: int | None = None, progress=None) -> dict:
    """Proper motion of the label called `name` (or with that alias) in the built field `target`."""
    sources = fieldspectra.sources_of(target)
    star = find_star(target, name)
    star = next((s for s in sources if star and s["id"] == star["id"]), None)
    if star is None:
        raise LookupError(f"no label called {name!r} in {target['id']}")
    refs = _references(sources, star)
    c = target["center"]
    ra0, dec0 = round(c["ra_deg"] % 360, 4), round(c["dec_deg"], 4)
    size_deg = round(target.get("size_arcmin", 15) / 60 + 2 * fieldspectra.MARGIN_DEG, 4)
    exposures, _ = build.cached_exposures(ra0, dec0)
    track = [star] + refs

    results = []
    total = len(exposures)
    if processes == 0:
        with ThreadPoolExecutor(32) as pool:
            results = list(pool.map(lambda e: _one(e, ra0, dec0, size_deg, track), exposures))
    else:      # the fits hold the GIL: spread them over the spectra worker processes (T83)
        from concurrent.futures import as_completed
        batch = photometry.SPECTRUM_BATCH
        futs = [photometry._pool().submit(_batch, exposures[i:i + batch], ra0, dec0, size_deg, track)
                for i in range(0, total, batch)]
        for f in as_completed(futs):
            results += f.result()
            if progress:
                progress(len(results), total)

    rows = []
    for e, m in results:
        if not m or m[0] is None:
            continue
        # this exposure's pointing error: median offset of the reference stars from their catalogue positions
        offs = []
        for r, fit in zip(refs, m[1:]):
            if fit is None:
                continue
            (pra, pdec), = fieldspectra.positions_at([r], e.mjd_mid)
            offs.append(_offset_arcsec(fit[0], fit[1], pra, pdec))
        if len(offs) < REF_MIN:
            continue
        offs = np.array(offs)
        corr = np.median(offs, axis=0)
        corr_err = 1.2533 * offs.std(axis=0) / math.sqrt(len(offs))
        ra, dec, err, snr = m[0]
        east, north = _offset_arcsec(ra, dec, star["ra_deg"], star["dec_deg"])
        rows.append({"frame_id": f"{e.obs_id}-D{e.detector}", "epoch": e.epoch, "mjd": e.mjd_mid,
                     "east": east - corr[0], "north": north - corr[1], "err": math.hypot(err, float(np.hypot(*corr_err))),
                     "snr": snr, "n_ref": len(offs)})
    if len({r["epoch"] for r in rows}) < 2:
        return {"version": VERSION, "name": star["name"], "status": "not_enough",
                "message": f"the star was measured in {len(rows)} exposures of "
                           f"{len({r['epoch'] for r in rows})} epoch(s); a motion needs two or more epochs",
                "n_exposures": len(exposures), "n_measured": len(rows)}

    epochs = []
    for ep in sorted({r["epoch"] for r in rows}):
        rs = [r for r in rows if r["epoch"] == ep]
        t = np.array([r["mjd"] for r in rs]); E = np.array([r["east"] for r in rs]); N = np.array([r["north"] for r in rs])
        me, mn = np.median(E), np.median(N)
        keep = np.hypot(E - me, N - mn) <= max(3 * 1.4826 * np.median(np.hypot(E - me, N - mn)), 0.5)
        n = int(keep.sum())
        se = max(float(np.std(E[keep])), 0.05) / math.sqrt(n) if n > 1 else float(rs[0]["err"])
        sn = max(float(np.std(N[keep])), 0.05) / math.sqrt(n) if n > 1 else float(rs[0]["err"])
        epochs.append({"epoch": ep, "mjd": float(t[keep].mean()), "east": float(E[keep].mean()), "north": float(N[keep].mean()),
                       "err_east": se, "err_north": sn, "n": n})

    # Offsets are from the star's catalogue track at each moment, so a real measurement sits near 0. A source that
    # stays several arcsec away in every epoch is a neighbour the fit locked onto (WISE 0855: invisible in single
    # exposures, a field star 7.6″ away was fitted instead); say so instead of reporting its motion.
    track_off = [math.hypot(e["east"] - _track_offset(star, e["mjd"])[0], e["north"] - _track_offset(star, e["mjd"])[1])
                 for e in epochs]
    if min(track_off) > LOCKED_ARCSEC:
        return {"version": VERSION, "name": star["name"], "status": "not_found",
                "message": (f"{star['name']} itself was not found in single SPHEREx exposures: the nearest source the "
                            f"fit could lock onto stays {np.median(track_off):.1f}″ from where the star is, so its "
                            "motion can't be measured here (too faint; deep stacks would be needed)."),
                "n_exposures": len(exposures), "n_measured": len(rows), "offset_arcsec": round(float(np.median(track_off)), 1)}
    t = np.array([e["mjd"] for e in epochs]); t0 = float(t.mean()); yrs = (t - t0) / 365.25
    # parallax factors (AU) per epoch: the mean over its exposures of where Earth was (SPHEREx is in low orbit)
    fac = []
    for e in epochs:
        mj = [r["mjd"] for r in rows if r["epoch"] == e["epoch"]]
        fac.append(np.mean([parallax_factors(star["ra_deg"], star["dec_deg"], m) for m in mj], axis=0))
    fac = np.array(fac)
    y = np.concatenate([[e["east"] for e in epochs], [e["north"] for e in epochs]])
    s = np.concatenate([[e["err_east"] for e in epochs], [e["err_north"] for e in epochs]])
    n = len(epochs)
    one, zero = np.ones(n), np.zeros(n)
    def lsq(with_plx):
        """unknowns: east0, north0, µ_east, µ_north (+ parallax ″). (sol, err, chi2/dof or None)"""
        cols = [np.r_[one, zero], np.r_[zero, one], np.r_[yrs, zero], np.r_[zero, yrs]]
        if with_plx:
            cols.append(np.r_[fac[:, 0], fac[:, 1]])
        A = np.array(cols).T / s[:, None]
        sol, *_ = np.linalg.lstsq(A, y / s, rcond=None)
        cov = np.linalg.inv(A.T @ A)
        chi2 = float(np.sum((A @ sol - y / s) ** 2))
        dof = 2 * n - len(cols)
        grow = math.sqrt(max(chi2 / dof, 1.0)) if dof > 0 else 1.0     # errors grown if the epochs disagree
        return sol, np.sqrt(np.diag(cov)) * grow, (chi2 / dof if dof > 0 else None)

    # The motion: a straight line per axis (robust with 2+ epochs). The parallax is tried on top with 3+ epochs and
    # reported only if that fit is consistent (chi2/dof <= PLX_MAX_CHI2) and significant: an epoch-to-epoch shift
    # from the fit itself (e.g. a saturated core, Barnard's Star: 1.9″ at epoch 2) would otherwise pose as a parallax.
    # the motion per axis on its own, so a systematic shift on one axis only widens that axis' error
    axis = {}
    for k, comp in enumerate(("east", "north")):
        yy = y[k * n:(k + 1) * n]; ss = s[k * n:(k + 1) * n]
        A1 = np.c_[np.ones(n), yrs] / ss[:, None]
        so1, *_ = np.linalg.lstsq(A1, yy / ss, rcond=None)
        c1 = np.linalg.inv(A1.T @ A1)
        ch = float(np.sum((A1 @ so1 - yy / ss) ** 2)); df = n - 2
        axis[comp] = (float(so1[1]), float(math.sqrt(c1[1, 1])) * (math.sqrt(max(ch / df, 1.0)) if df > 0 else 1.0),
                      ch / df if df > 0 else None)
    (pe, se_, ce), (pn, sn_, cn) = axis["east"], axis["north"]
    chi_line = max(c for c in (ce, cn) if c is not None) if n > 2 else None
    plx = None
    if 2 * n - 5 >= 1:
        sp, ep_, chi_p = lsq(True)
        good = chi_p is not None and chi_p <= PLX_MAX_CHI2 and sp[4] > 3 * ep_[4]
        plx = {"parallax_arcsec": round(float(sp[4]), 3), "parallax_err": round(float(ep_[4]), 3),
               "chi2_dof": round(chi_p, 2) if chi_p is not None else None, "reliable": bool(good),
               "distance_pc": round(1 / float(sp[4]), 2) if good else None,
               "note": ("measured" if good else
                        "not measurable here: the epochs scatter more than a parallax would move the star "
                        "(systematic shifts of the fit), so no distance is claimed" if chi_p is not None and chi_p > PLX_MAX_CHI2
                        else "too small to measure with these epochs")}
    chi2 = chi_line
    dof = 1
    total = math.hypot(pe, pn)
    total_err = math.hypot(pe * se_, pn * sn_) / total if total else math.hypot(se_, sn_)
    pa = math.degrees(math.atan2(pe, pn)) % 360
    cat_e, cat_n = star["dra_deg_day"] * math.cos(math.radians(star["dec_deg"])) * 3600 * 365.25, star["ddec_deg_day"] * 3600 * 365.25
    cat_total = math.hypot(cat_e, cat_n)
    diff = math.hypot(pe - cat_e, pn - cat_n)
    span = float((t.max() - t.min()) / 365.25)
    sig = diff / max(math.hypot(se_, sn_), 1e-9)
    verdict = ("agrees with the catalogue" if sig < 3 else
               f"differs from the catalogue by {diff:.2f}″/yr ({sig:.1f}σ)")
    return {"version": VERSION, "status": "ready", "name": star["name"], "id": star["id"],
            "pm_east_arcsec_yr": round(pe, 3), "pm_north_arcsec_yr": round(pn, 3),
            "err_east": round(se_, 3), "err_north": round(sn_, 3),
            "pm_total_arcsec_yr": round(total, 3), "pm_total_err": round(total_err, 3), "pa_deg": round(pa, 1),
            "catalogue": {"pm_total_arcsec_yr": round(cat_total, 3),
                          "pa_deg": round(math.degrees(math.atan2(cat_e, cat_n)) % 360, 1), "source": star["source"]},
            "difference_arcsec_yr": round(diff, 3), "difference_sigma": round(sig, 1), "verdict": verdict,
            "summary": (f"SPHEREx: {total:.2f} ± {total_err:.2f}″/yr toward PA {pa:.0f}°; catalogue "
                        f"{cat_total:.2f}″/yr toward {math.degrees(math.atan2(cat_e, cat_n)) % 360:.0f}°: {verdict}."),
            "epochs": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in e.items()} for e in epochs],
            "parallax": plx, "chi2_dof": round(chi2, 2) if chi2 is not None else None,
            "span_years": round(span, 2), "n_exposures": len(exposures), "n_measured": len(rows),
            "n_references": len(refs),
            "method": ("Gaussian fit per exposure (flagged pixels left out), each exposure's pointing corrected with "
                       f"up to {REF_MAX} isolated Gaia stars, robust mean per epoch, weighted line through the epochs. "
                       "With 3+ epochs the parallax is fitted too (Earth's position at each exposure).")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m pipeline.astrometry", description=__doc__.split("\n\n")[0])
    ap.add_argument("target_dir", type=Path)
    ap.add_argument("--name", required=True)
    args = ap.parse_args(argv)
    t = json.loads((args.target_dir / "target.json").read_text(encoding="utf-8"))
    r = measure_motion(t, args.name)
    if r["status"] != "ready":
        print(r["message"])
        return 1
    print(r["summary"])
    if r.get("parallax"):
        p = r["parallax"]
        print(f"  parallax fit {p['parallax_arcsec']:.3f} ± {p['parallax_err']:.3f}″ (χ²/dof {p['chi2_dof']}): "
              + (f"distance {p['distance_pc']} pc" if p["reliable"] else p["note"]))
    print(f"  measured in {r['n_measured']} of {r['n_exposures']} exposures over {r['span_years']} yr, "
          f"{r['n_references']} reference stars")
    for e in r["epochs"]:
        print(f"  epoch {e['epoch']}: MJD {e['mjd']:.1f}  E {e['east']:+.2f} ± {e['err_east']:.2f}″  "
              f"N {e['north']:+.2f} ± {e['err_north']:.2f}″  ({e['n']} exposures)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
