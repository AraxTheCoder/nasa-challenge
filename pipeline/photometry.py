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
import os
import re
import sys
import threading
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from . import build, flags, s3
from .s3 import IBE_PREFIX, S3_ROOT

APERTURE_PX = 3.0
ANNULUS_PX = (5.0, 8.0)
MAX_MASKED = 0.2            # more than this fraction of the aperture flagged -> masked
NOTE = ("Aperture photometry (r = 3 native px ≈ 18″) on the SPHEREx images, sky (incl. zodiacal light) from the "
        "surrounding ring; no aperture "
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
    return measure_cutout_many(path, [(ra, dec)])[0]


FAR_DEG = 3.0                # T113: farther than this from an image's centre = not on it (SPHEREx images are 3.5°)


def _sky_to_pixel(w, positions, nx: int, ny: int):
    """Pixel positions of (ra, dec) pairs; NaN for points far from the image. astropy's iterative solution raises
    for a point far from the image (no convergence, or no solution of the projection), which made a spectrum
    asked far outside a field a 500 (T113)."""
    ra = np.array([p[0] for p in positions], float)
    dec = np.array([p[1] for p in positions], float)
    cra, cdec = (float(v[0]) for v in w.all_pix2world([(nx - 1) / 2], [(ny - 1) / 2], 0))
    cosd = (np.sin(np.radians(dec)) * math.sin(math.radians(cdec)) +
            np.cos(np.radians(dec)) * math.cos(math.radians(cdec)) * np.cos(np.radians(ra - cra)))
    near = np.degrees(np.arccos(np.clip(cosd, -1, 1))) <= FAR_DEG
    xs, ys = np.full(len(ra), np.nan), np.full(len(ra), np.nan)
    if near.any():
        x, y = w.all_world2pix(ra[near], dec[near], 0, quiet=True)
        xs[near], ys[near] = x, y
    return xs, ys


def measure_cutout_many(path: Path, positions) -> list[dict | None]:
    """measure_cutout at many (ra, dec) positions, the file read once (T85: a whole field per exposure)."""
    from astropy.io import fits
    from astropy.wcs import WCS, FITSFixedWarning
    from astropy.wcs.utils import proj_plane_pixel_area

    positions = list(positions)
    with fits.open(path) as hd, warnings.catch_warnings():
        warnings.simplefilter("ignore", FITSFixedWarning)
        img = hd["IMAGE"].data.astype(float)
        if "ZODI" in hd:
            img = img - hd["ZODI"].data
        var = hd["VARIANCE"].data.astype(float) if "VARIANCE" in hd else None
        flg = hd["FLAGS"].data.astype(np.int64)
        bad = ((flg & build.HW_MASK) != 0) | ~np.isfinite(img)
        w = WCS(hd["IMAGE"].header)
        if not positions:
            return []
        ny, nx = img.shape
        xs, ys = _sky_to_pixel(w, positions, nx, ny)
        r_out = ANNULUS_PX[1]
        inside = (xs >= r_out) & (xs <= nx - 1 - r_out) & (ys >= r_out) & (ys <= ny - 1 - r_out)
        waves = build.wavelengths_at(hd, xs[inside], ys[inside]) if inside.any() else ([], [])
        pix_sr = proj_plane_pixel_area(w) * (math.pi / 180) ** 2
    out, k = [], 0
    for i in range(len(positions)):
        if not inside[i]:
            out.append(None)
            continue
        out.append(_aperture(img, var, bad, float(xs[i]), float(ys[i]), float(waves[0][k]), float(waves[1][k]), pix_sr, flg))
        k += 1
    return out


def _aperture(img, var, bad, x: float, y: float, wave: float, bw: float, pix_sr: float, flg=None) -> dict | None:
    r_out = ANNULUS_PX[1]
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
        # T60: every quality flag set anywhere in the aperture, by name (pipeline/flags.py says what each means)
        **({"flags": flags.in_pixels(flg[y0:y1, x0:x1][ap])} if flg is not None else {}),
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
        "frames": rows, "missing": missing, "note": NOTE, "flag_meanings": flags.meanings(rows),
    }


SPECTRUM_CUT_DEG = 0.05      # 3': room for the annulus (8 px) around the star, little over-read
SPECTRA_ROOT = Path("data/spectra")
# T83: a 3' cutout is ~0.6 MB in 7 dependent range requests (~2 s from Europe, all latency), so many
# images at once. Read the bucket directly: the cutout VM adds a hop and was answering 502s, and the
# IRSA cutout fallback takes seconds per image; a few missing points don't matter for a spectrum.
SPECTRUM_THREADS = 64
_spectra_lock = threading.Lock()


def spectrum_cache(ra: float, dec: float) -> Path:
    return SPECTRA_ROOT / f"{ra:.4f}_{dec:+.4f}.json"


WORKER_GB = 0.25             # T98: one worker process, measured (129 MB fresh, ~235 MB after field spectra)


def spectrum_processes(ram_gb: float | None = None, cpus: int | None = None, env: str | None = None) -> int:
    """T98: how many worker processes this machine gets: at most 16 (T83), one per CPU, and together no more
    than a quarter of the RAM (8 GB -> 8, 4 GB -> 4; 16 of them took 3.3 GB and got the API OOM-killed on an
    8 GB machine). SPHEREX_SPECTRUM_PROCESSES overrides it; 0 = no worker processes, threads only."""
    env = os.environ.get("SPHEREX_SPECTRUM_PROCESSES") if env is None else env
    if env not in (None, ""):
        try:
            return max(0, int(env))
        except ValueError:
            print(f"SPHEREX_SPECTRUM_PROCESSES={env!r} is not a number, ignored", file=sys.stderr)
    n = min(16, cpus or os.cpu_count() or 4)
    if ram_gb is None:
        try:
            ram_gb = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 2**30
        except (AttributeError, ValueError, OSError):      # Windows has no sysconf: CPUs decide
            return n
    return max(2, min(n, int(ram_gb / 4 / WORKER_GB)))


SPECTRUM_PROCESSES = spectrum_processes()   # T83: the cutouts' CPU part (FITS headers, WCS, RICE) holds the GIL; spread it
POOL_IDLE_S = 300            # T98: after this long without work the worker processes exit and give their memory back
SPECTRUM_BATCH = 8           # images per task: 16 processes x 8 threads = 128 requests in flight (latency-bound)
_proc_pool = None
_pool_used = 0.0
_proc_lock = threading.Lock()


_FIELD_ID = re.compile(r"^c(\d{7})-([mp])(\d{6})-s(\d+)")
_fields = {"mtime": None, "at": 0.0, "list": []}


def _field_centres() -> list[tuple[float, float, float]]:
    """T143: (ra, dec, side deg) of the built fields, from their folder names (c2694472-p047664-s14 = 269.4472°,
    +4.7664°, 14′: the same 4-decimal centre their cutouts are stored under). Read again when the folder changes."""
    root = build.RAW_ROOT.parent / "targets"
    try:
        m = root.stat().st_mtime
    except OSError:
        return []
    if _fields["mtime"] != m or time.time() - _fields["at"] > 30:
        out = []
        for name in os.listdir(root):
            g = _FIELD_ID.match(name)
            if g:
                out.append((int(g[1]) / 1e4, (-1 if g[2] == "m" else 1) * int(g[3]) / 1e4, int(g[4]) / 60))
        _fields.update(mtime=m, at=time.time(), list=out)
    return _fields["list"]


def _field_cutout(url: str, ra: float, dec: float, size_deg: float) -> Path | None:
    """T143: a stored cutout of this image made for a built field (its build, its spectra, its sources) that has
    (ra, dec) and the measuring margin (size_deg / 2) inside: read instead of downloading a small one. Point spectra
    took a median 14 s (max 87 s) on Mati's machine, nearly all of them downloads, mostly inside analysed fields."""
    cos = math.cos(math.radians(dec))
    near = []
    for fra, fdec, side in _field_centres():
        sep = math.degrees(math.acos(min(1.0, math.sin(math.radians(dec)) * math.sin(math.radians(fdec))
                                         + cos * math.cos(math.radians(fdec)) * math.cos(math.radians(ra - fra)))))
        if sep <= side:                                   # a cutout of a field this far off can't hold the point
            near.append((sep, fra, fdec))
    for sep, fra, fdec in sorted(near):
        # the circle that fits in the cutout's square (any rotation) must hold the point and its margin
        hit = build.cached_cutout(url, fra, fdec, 2 * (sep + size_deg / 2), build.RAW_ROOT)
        if hit:
            return hit
    return None


def _spectrum_cutout(url: str, ra: float, dec: float, size_deg: float = SPECTRUM_CUT_DEG) -> Path:
    hit = build.cached_cutout(url, ra, dec, size_deg, build.RAW_ROOT) or _field_cutout(url, ra, dec, size_deg)  # T143
    if hit:
        return hit
    d = build._cutout_dir(url, ra, dec, build.RAW_ROOT)
    d.mkdir(parents=True, exist_ok=True)
    dest = d / f"{size_deg:.4f}.fits"
    try:
        return s3.fetch_cutout(url, ra, dec, size_deg, dest)
    except LookupError:
        raise
    except Exception as ex:  # noqa: BLE001
        if not s3.is_not_found(ex):
            raise
        moved = s3.find_in_bucket(url)          # reprocessed: a listing of the bucket finds it (~1 s)
        if not moved or moved == url:
            raise LookupError(f"not in the bucket: {url.rsplit('/', 1)[-1]}") from ex
        return s3.fetch_cutout(moved, ra, dec, size_deg, dest)


def _spectrum_point(e, ra: float, dec: float) -> tuple[str, object]:
    """('row', dict) | ('missing', frame id) | ('lost', exposure) for one exposure."""
    fid = f"{e.obs_id}-D{e.detector}"
    try:
        m = measure_cutout(_spectrum_cutout(e.fits_url, ra, dec), ra, dec)
    except LookupError:
        return "missing", fid
    except Exception:  # noqa: BLE001 - path moved (reprocessed): looked up afterwards
        return "lost", e
    if m is None:
        return "missing", fid
    return "row", {"frame_id": fid, "epoch": e.epoch, "mjd": round(e.mjd_mid, 6), "time_utc": e.time_utc,
                   "detector": e.detector, **m}


def _spectrum_batch(exposures: list, ra: float, dec: float) -> list[tuple[str, object]]:
    with ThreadPoolExecutor(len(exposures)) as pool:
        return list(pool.map(lambda e: _spectrum_point(e, ra, dec), exposures))


def _pool():
    global _proc_pool, _pool_used
    with _proc_lock:
        if _proc_pool is None:
            import multiprocessing
            from concurrent.futures import ProcessPoolExecutor
            _proc_pool = ProcessPoolExecutor(SPECTRUM_PROCESSES, mp_context=multiprocessing.get_context("forkserver"),
                                             initializer=_watch_parent, initargs=(os.getpid(),))
            threading.Thread(target=_retire_when_idle, args=(_proc_pool,), daemon=True, name="spectrum-pool-idle").start()
        _pool_used = time.monotonic()
        return _proc_pool


PARENT_POLL_S = 5.0


def _watch_parent(server_pid: int, poll_s: float | None = None) -> None:
    """T99: runs in each worker. Workers are children of the fork server, not of the Live API, so nothing ends them
    when the API stops (a restart by the auto-pull left 16 per restart: 324 = 28.7 GB on one host). A daemon thread
    checks every few seconds that the process that made the pool is still there, and ends this worker if not."""
    def loop():
        while True:
            time.sleep(poll_s if poll_s is not None else PARENT_POLL_S)
            try:
                os.kill(server_pid, 0)                # signal 0: only "does it exist"
            except ProcessLookupError:
                os._exit(0)
            except PermissionError:                   # exists, under another user: still alive
                pass
    threading.Thread(target=loop, daemon=True, name="watch-server").start()


def _retire_when_idle(pool, idle_s: float | None = None, poll_s: float | None = None) -> None:
    """T98: shut `pool` down once it had no work for POOL_IDLE_S, so its processes (~0.2 GB each) don't stay
    for the life of the server; the next _pool() starts a new one (~2 s). Work handed in is never dropped:
    a pool with tasks waiting or running counts as in use, and shutdown lets anything still in it finish."""
    global _proc_pool, _pool_used
    while True:
        time.sleep(poll_s if poll_s is not None else min(30.0, POOL_IDLE_S / 4))
        with _proc_lock:
            if _proc_pool is not pool:            # replaced after a failure (the callers set it to None)
                break
            if getattr(pool, "_pending_work_items", None):      # tasks waiting or running
                _pool_used = time.monotonic()
                continue
            if time.monotonic() - _pool_used < (idle_s if idle_s is not None else POOL_IDLE_S):
                continue
            _proc_pool = None
            break
    pool.shutdown(wait=False)


def _anomalies(out: dict) -> dict:
    from .anomaly import find_anomalies       # T84
    try:
        return find_anomalies(out)
    except Exception as e:  # noqa: BLE001 - the spectrum stands without it
        return {"items": [], "summary": f"anomaly check failed: {e}", "counts": {}}


def _write_spectrum(path: Path, out: dict) -> None:
    with _spectra_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{threading.get_ident()}.part")
        tmp.write_text(json.dumps(out), encoding="utf-8")
        tmp.replace(path)


def measure_all(ra: float, dec: float, progress=None, threads: int = SPECTRUM_THREADS,
                processes: int | None = None) -> dict:
    """T66: photometry at (ra, dec) on every exposure that covers it. progress(done, total) while running.
    Same answer shape as measure(); frame_id = '<obs_id>-D<detector>' (these are not the field's frames).
    processes: 0 = threads only in this process (tests); default SPECTRUM_PROCESSES worker processes (T83)."""
    ra, dec = round(ra % 360, 4), round(dec, 4)
    cached = spectrum_cache(ra, dec)
    out = json.loads(cached.read_text(encoding="utf-8")) if cached.is_file() else None
    if out is not None and "flag_meanings" in out:       # T60: older entries have no flags: measured again below
        from .anomaly import VERSION
        if (out.get("anomalies") or {}).get("version") != VERSION:   # cached before T84 or with an older method
            out["anomalies"] = _anomalies(out)
            _write_spectrum(cached, out)
        return out
    t0 = time.time()
    exposures, _ = build.cached_exposures(ra, dec)
    total = len(exposures)
    done, rows, missing, lost = 0, [], [], []

    def take(results):
        nonlocal done
        for kind, v in results:
            {"row": rows, "missing": missing, "lost": lost}[kind].append(v)
        done += len(results)
        if progress:
            progress(done, total)

    procs = SPECTRUM_PROCESSES if processes is None else processes
    if procs:
        global _proc_pool
        batches = [exposures[i:i + SPECTRUM_BATCH] for i in range(0, total, SPECTRUM_BATCH)]
        try:
            futs = [_pool().submit(_spectrum_batch, b, ra, dec) for b in batches]
            for f in as_completed(futs):
                take(f.result())
        except Exception as ex:  # noqa: BLE001 - e.g. BrokenProcessPool: start over with threads
            print(f"spectrum worker processes failed ({type(ex).__name__}), using threads", file=sys.stderr)
            with _proc_lock:
                _proc_pool = None
            done, rows[:], missing[:], lost[:] = 0, [], [], []
            procs = 0
    if not procs:
        with ThreadPoolExecutor(threads) as pool:
            for f in as_completed([pool.submit(_spectrum_point, e, ra, dec) for e in exposures]):
                take([f.result()])
    if lost:   # reprocessed images under another path the bucket listing didn't find: TAP lookup, one more try
        try:
            from .mirror import resolve_urls
            fixed = resolve_urls([e.publisher_did for e in lost])
        except Exception:  # noqa: BLE001
            fixed = {}
        for e in lost:
            url = fixed.get(e.publisher_did)
            if url and url != e.fits_url:
                e.fits_url = url
                kind, v = _spectrum_point(e, ra, dec)
                (rows.append(v) if kind == "row" else missing.append(f"{e.obs_id}-D{e.detector}"))
            else:
                missing.append(f"{e.obs_id}-D{e.detector}")
    rows.sort(key=lambda r: (r["mjd"], r["detector"]))
    out = {"ra_deg": ra, "dec_deg": dec, "aperture_px": APERTURE_PX, "annulus_px": list(ANNULUS_PX),
           "unit": "uJy", "frames": rows, "missing": missing, "all_exposures": True, "n_exposures": total,
           "seconds": round(time.time() - t0, 1), "note": NOTE, "flag_meanings": flags.meanings(rows)}
    out["anomalies"] = _anomalies(out)                 # T84
    _write_spectrum(cached, out)
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
