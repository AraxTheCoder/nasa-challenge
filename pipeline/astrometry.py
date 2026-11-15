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
STAR_CUT_DEG = 0.3       # cutout around the star when the field is a big one (reference stars within it)
VERSION = 3                  # 2: deep-stack fallback (T119); 3: `measured_field` (was a clash with `measured_in`)
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


STACK_DETECTORS = (5, 6)     # T119: 3.8–5 µm, where cold brown dwarfs shine (WISE 0855: invisible below ~3 µm)
STACK_N = 25                  # grid side, native pixels (2.6′)
STACK_MIN_SNR = 5.0
STACK_MIN_EXPOSURES = 3
SINGLE_MIN_SNR = 10.0         # median S/N of the single-exposure fits below this: the deep stacks are tried first


def _stacked_epochs(star: dict, results, corrs: dict, ra0: float, dec0: float, size_deg: float) -> list[dict]:
    """T119: each epoch's long-wavelength exposures, pointing-corrected, stacked on one grid around the star; the
    star fitted in each stack. Same epoch entries as the single-exposure path (east / north from the star's
    reference position, arcsec), plus "stacked": number of exposures."""
    from astropy.io import fits
    from astropy.wcs import WCS, FITSFixedWarning
    from scipy.ndimage import map_coordinates

    scale = 6.15 / 3600
    g = WCS(naxis=2)
    g.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    g.wcs.crval = [star["ra_deg"], star["dec_deg"]]
    g.wcs.crpix = [(STACK_N + 1) / 2, (STACK_N + 1) / 2]
    g.wcs.cdelt = [-scale, scale]
    yy, xx = np.mgrid[0:STACK_N, 0:STACK_N]
    gra, gdec = g.all_pix2world(xx, yy, 0)
    cosd = math.cos(math.radians(star["dec_deg"]))
    acc: dict[int, list] = {}
    for e, m in results:
        if e.detector not in STACK_DETECTORS or id(e) not in corrs:
            continue
        try:
            path = photometry._spectrum_cutout(e.fits_url, ra0, dec0, size_deg)
            with fits.open(path) as hd, warnings.catch_warnings():
                warnings.simplefilter("ignore", FITSFixedWarning)
                img = hd["IMAGE"].data.astype(float)
                bad = ((hd["FLAGS"].data.astype(np.int64) & build.HW_MASK) != 0) | ~np.isfinite(img)
                w = WCS(hd["IMAGE"].header)
        except Exception:  # noqa: BLE001 - one exposure less
            continue
        ce, cn = corrs[id(e)]           # this exposure puts a true position T at T + corr: sample there
        ix, iy = w.all_world2pix(gra + ce / 3600 / cosd, gdec + cn / 3600, 0)
        val = map_coordinates(np.where(bad, 0.0, img), [iy, ix], order=1, cval=np.nan)
        holes = map_coordinates(bad.astype(float), [iy, ix], order=1, cval=1.0) > 0.01
        val[holes] = np.nan
        if np.isfinite(val).sum() < STACK_N * STACK_N / 2:
            continue
        val -= np.nanmedian(val)        # local sky (zodiacal light differs per exposure)
        acc.setdefault(e.epoch, []).append((e.mjd_mid, val))
    def fit(vals, px, py):
        """(grid x, grid y, snr, fit error px) of the star in the mean of `vals`, or None."""
        stack = np.nanmean(np.array(vals), axis=0)
        xi, yi = int(round(px)), int(round(py))
        if not (STAMP_PX <= xi < STACK_N - STAMP_PX and STAMP_PX <= yi < STACK_N - STAMP_PX):
            return None
        sl = (slice(yi - STAMP_PX, yi + STAMP_PX + 1), slice(xi - STAMP_PX, xi + STAMP_PX + 1))
        sub = stack[sl]
        f = _gauss_fit(sub, ~np.isfinite(sub), px - (xi - STAMP_PX), py - (yi - STAMP_PX))
        if f is None:
            return None
        fx, fy, ex, ey, snr, _ = f
        gx, gy = fx + xi - STAMP_PX, fy + yi - STAMP_PX
        if snr < STACK_MIN_SNR or math.hypot(gx - px, gy - py) > SEARCH_PX or not math.isfinite(ex):
            return None
        return gx, gy, snr, math.hypot(ex, ey) / math.sqrt(2)

    def sky(gx, gy):
        ra, dec = (float(v) for v in g.all_pix2world(gx, gy, 0))
        return _offset_arcsec(ra, dec, star["ra_deg"], star["dec_deg"])

    out = []
    for ep, items in sorted(acc.items()):
        if len(items) < STACK_MIN_EXPOSURES:
            continue
        mjds = [mj for mj, _ in items]
        mjd = float(np.mean(mjds))
        (pra, pdec), = fieldspectra.positions_at([star], mjd)
        px, py = (float(v) for v in g.all_world2pix(pra, pdec, 0))
        whole = fit([v for _, v in items], px, py)
        if whole is None:
            continue
        east, north = sky(whole[0], whole[1])
        # The fit's own error is too optimistic on a stack (averaging and resampling make the pixel noise look
        # smaller than it is): the two halves of the epoch (alternate exposures) fitted apart give an honest one.
        err_e = err_n = max(whole[3] * 6.15, 0.1)
        if len(items) >= 2 * STACK_MIN_EXPOSURES:
            a, b = fit([v for _, v in items[0::2]], px, py), fit([v for _, v in items[1::2]], px, py)
            if a and b:
                (ae, an), (be, bn) = sky(a[0], a[1]), sky(b[0], b[1])
                err_e, err_n = max(err_e, abs(ae - be) / 2), max(err_n, abs(an - bn) / 2)
            else:
                err_e, err_n = err_e * 3, err_n * 3        # a half too faint to fit: the whole is marginal
        out.append({"epoch": ep, "mjd": mjd, "east": east, "north": north, "err_east": err_e, "err_north": err_n,
                    "n": len(items), "stacked": len(items), "snr": round(whole[2], 1), "mjds": mjds})
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


def cache_path(star_name: str) -> Path:
    """One result per star, whichever field it was measured in (the map's automatic tile fields and the typed
    field around the same star share it)."""
    import re
    return ROOT / (re.sub(r"[^a-z0-9]+", "-", star_name.lower()).strip("-") + ".json")


def cached(target: dict, name: str) -> dict | None:
    star = find_star(target, name)
    p = cache_path(star["name"]) if star else None
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
        p = cache_path(star["name"])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({**r, "measured_field": target["id"]}), encoding="utf-8")
    return r


def measure_motion_uncached(target: dict, name: str, processes: int | None = None, progress=None) -> dict:
    """Proper motion of the label called `name` (or with that alias) in the built field `target`."""
    sources = fieldspectra.sources_of(target)
    star = find_star(target, name)
    star = next((s for s in sources if star and s["id"] == star["id"]), None)
    if star is None:
        raise LookupError(f"no label called {name!r} in {target['id']}")
    c = target["center"]
    # A cutout around the star, not the field: the map's automatic fields are up to 1.5° wide (300 such cutouts
    # would take minutes). Centred on a 0.01° grid so every field around the same star reuses the same files;
    # inside a typed 15′ field around the star, T85's field cutouts are reused as they are.
    if fieldspectra._sep_arcsec(star, {"ra_deg": c["ra_deg"], "dec_deg": c["dec_deg"]}) < 120 and target.get("size_arcmin", 15) <= 20:
        ra0, dec0 = round(c["ra_deg"] % 360, 4), round(c["dec_deg"], 4)
        size_deg = round(target.get("size_arcmin", 15) / 60 + 2 * fieldspectra.MARGIN_DEG, 4)
    else:
        ra0, dec0 = round(star["ra_deg"] % 360, 2), round(star["dec_deg"], 2)
        size_deg = STAR_CUT_DEG
    inside = [x for x in sources if fieldspectra._sep_arcsec(x, {"ra_deg": ra0, "dec_deg": dec0}) < size_deg / 2 * 3600 - 60]
    refs = _references(inside, star)
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

    rows, corrs = [], {}
    for e, m in results:
        if not m:
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
        corrs[id(e)] = (float(corr[0]), float(corr[1]))          # T119: the deep stacks use it too
        if m[0] is None:
            continue
        ra, dec, err, snr = m[0]
        east, north = _offset_arcsec(ra, dec, star["ra_deg"], star["dec_deg"])
        rows.append({"frame_id": f"{e.obs_id}-D{e.detector}", "epoch": e.epoch, "mjd": e.mjd_mid,
                     "east": east - corr[0], "north": north - corr[1], "err": math.hypot(err, float(np.hypot(*corr_err))),
                     "snr": snr, "n_ref": len(offs)})
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
                       "err_east": se, "err_north": sn, "n": n, "mjds": [float(x) for x in t[keep]]})

    # Offsets are from the star's catalogue track at each moment, so a real measurement sits near 0. A source that
    # stays several arcsec away in every epoch is a neighbour the fit locked onto (WISE 0855: invisible in single
    # exposures, a field star 7.6″ away was fitted instead).
    def off_track(eps):
        return [math.hypot(e["east"] - _track_offset(star, e["mjd"])[0], e["north"] - _track_offset(star, e["mjd"])[1])
                for e in eps]
    mode = "single exposures"
    singles_ok = len(epochs) >= 2 and min(off_track(epochs)) <= LOCKED_ARCSEC
    weak = not rows or float(np.median([r["snr"] for r in rows])) < SINGLE_MIN_SNR
    if not singles_ok or weak:
        # T119: too faint for one exposure (WISE 0855: not found; or found only in noise-dominated fits, which bias
        # the motion): stack each epoch's long-wavelength exposures, then fit; a weak singles result is kept only
        # when the stacks don't give two epochs
        stacked = _stacked_epochs(star, results, corrs, ra0, dec0, size_deg)
        if len(stacked) >= 2 and min(off_track(stacked)) <= LOCKED_ARCSEC:
            epochs, mode = stacked, "deep stacks"
        elif singles_ok:
            pass
        elif len(epochs) >= 2:
            track_off = off_track(epochs)
            return {"version": VERSION, "name": star["name"], "status": "not_found",
                    "message": (f"{star['name']} itself was not found, neither in single SPHEREx exposures (the nearest "
                                f"source stays {np.median(track_off):.1f}″ from where the star is) nor in deep per-epoch "
                                "stacks at 3.8–5 µm, so its motion can't be measured here."),
                    "n_exposures": len(exposures), "n_measured": len(rows),
                    "offset_arcsec": round(float(np.median(track_off)), 1)}
        else:
            return {"version": VERSION, "name": star["name"], "status": "not_enough",
                    "message": f"the star was measured in {len(rows)} exposures of "
                               f"{len({r['epoch'] for r in rows})} epoch(s) and in {len(stacked)} deep epoch stack(s); "
                               "a motion needs two or more epochs",
                    "n_exposures": len(exposures), "n_measured": len(rows)}
    t = np.array([e["mjd"] for e in epochs]); t0 = float(t.mean()); yrs = (t - t0) / 365.25
    # parallax factors (AU) per epoch: the mean over its exposures of where Earth was (SPHEREx is in low orbit)
    fac = []
    for e in epochs:
        fac.append(np.mean([parallax_factors(star["ra_deg"], star["dec_deg"], m) for m in e["mjds"]], axis=0))
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
            "epochs": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in e.items() if k != "mjds"} for e in epochs],
            "measured_in": mode,
            "parallax": plx, "chi2_dof": round(chi2, 2) if chi2 is not None else None,
            "span_years": round(span, 2), "n_exposures": len(exposures),
            "n_measured": len(rows) if mode == "single exposures" else int(sum(e["n"] for e in epochs)),
            "n_references": len(refs),
            "method": (("Gaussian fit per exposure (flagged pixels left out), each exposure's pointing corrected with "
                        f"up to {REF_MAX} isolated Gaia stars, robust mean per epoch, weighted line through the epochs. ")
                       if mode == "single exposures" else
                       ("Too faint for one exposure: each epoch's exposures of detectors 5–6 (3.8–5 µm), each corrected "
                        f"for its pointing with up to {REF_MAX} isolated Gaia stars, stacked on one grid; a Gaussian fit "
                        "per epoch stack, weighted line through the epochs. ") +
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
    how = (f"measured in {r['n_measured']} of {r['n_exposures']} exposures" if r.get("measured_in") != "deep stacks" else
           f"too faint for single exposures: deep stacks of {' / '.join(str(e['stacked']) for e in r['epochs'])} "
           "exposures at 3.8–5 µm")
    print(f"  {how} over {r['span_years']} yr, {r['n_references']} reference stars")
    for e in r["epochs"]:
        print(f"  epoch {e['epoch']}: MJD {e['mjd']:.1f}  E {e['east']:+.2f} ± {e['err_east']:.2f}″  "
              f"N {e['north']:+.2f} ± {e['err_north']:.2f}″  ({e['n']} exposures)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
