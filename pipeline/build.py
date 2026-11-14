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
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
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
THREADS = 8          # IRSA cutout service: more parallel requests only get more 503s
S3_THREADS = 24      # AWS bucket (T33): not throttled, 7 MB/s at 32 parallel from Europe
REMOTE_THREADS = 8   # T57 cutout VM: 36 cutouts in 3.3 s at 8 parallel, 6.3 s at 24 (2026-11-14)
ALIGN_THREADS = 2    # T57: resample while downloading; 0.22 s per image serial, half on 2 threads
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


# T26: IRSA answers "503 Server busy, retry later" under load. Retry with backoff, and share one
# download limit across all concurrent builds in this process so we don't hammer it.
RETRY_STATUS = {429, 500, 502, 503, 504}
RETRY_WAITS_S = (2, 4, 8, 16, 30)
_DOWNLOAD_SLOTS = threading.BoundedSemaphore(THREADS)


def _get_with_retry(url: str, sleep=time.sleep) -> bytes:
    import requests

    last = None
    for attempt, wait in enumerate((0,) + RETRY_WAITS_S):
        if wait:
            sleep(wait + random.uniform(0, wait / 4))
        try:
            with _DOWNLOAD_SLOTS:
                r = requests.get(url, timeout=TIMEOUT_S)
        except (requests.ConnectionError, requests.Timeout) as e:
            last = e
            continue
        if r.status_code in RETRY_STATUS:
            last = RuntimeError(f"HTTP {r.status_code}: {r.text[:60].strip()}")
            continue
        r.raise_for_status()
        if not r.content.startswith(b"SIMPLE"):
            last = RuntimeError(f"not a FITS file: {r.content[:60]!r}")
            continue
        return r.content
    raise RuntimeError(f"gave up after {len(RETRY_WAITS_S) + 1} tries: {last}")


# T28: cutouts are cached per (image, centre) with their size in the file name. A cached cutout at
# least as large as needed is reused, so changing the field of view to something smaller (or equal)
# downloads nothing. Every download is at least MIN_CUTOUT_DEG: ~82% of a cutout's bytes are the
# EPSF table, which doesn't grow with size, so a bigger minimum costs little and saves re-downloads.
MIN_CUTOUT_DEG = 0.40   # covers fields up to ~15' with rotation margin


def _cutout_dir(fits_url: str, ra: float, dec: float, raw_root: Path) -> Path:
    key = f"{fits_url}|{ra:.4f}|{dec:.4f}"
    return raw_root / "cutouts" / hashlib.sha1(key.encode()).hexdigest()[:20]


def cached_cutout(fits_url: str, ra: float, dec: float, size_deg: float,
                  raw_root: Path = RAW_ROOT) -> Path | None:
    d = _cutout_dir(fits_url, ra, dec, raw_root)
    best = None
    for p in d.glob("*.fits") if d.exists() else []:
        try:
            s = float(p.stem)
        except ValueError:
            continue
        if s >= size_deg - 1e-9 and (best is None or s < best[0]):
            best = (s, p)
    return best[1] if best else None


def fetch(fits_url: str, ra: float, dec: float, size_deg: float, raw_root: Path = RAW_ROOT,
          min_deg: float = MIN_CUTOUT_DEG) -> Path:
    """Return a cached cutout covering size_deg, downloading one (>= min_deg) if needed.
    min_deg: builds keep MIN_CUTOUT_DEG so FOV changes reuse it; T66 spectra fetch tiny cutouts."""
    hit = cached_cutout(fits_url, ra, dec, size_deg, raw_root)
    if hit:
        return hit
    size = round(max(size_deg, min_deg), 4)
    d = _cutout_dir(fits_url, ra, dec, raw_root)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{size:.4f}.fits"
    from . import s3
    # T57: the team VM next to the bucket cuts it (fastest from Europe), then T33: the AWS bucket
    # directly (HTTP Range, only the rows we need), IRSA cutouts as the last fallback.
    in_bucket = True
    if s3.remote_available():
        try:
            return s3.fetch_cutout_remote(fits_url, ra, dec, size, path)
        except LookupError:
            raise
        except s3.NotInBucket:
            in_bucket = False                  # reading the bucket ourselves would 404 the same way
        except Exception as e:  # noqa: BLE001 - VM down or old: read the bucket ourselves
            print(f"Cutout VM failed, reading S3 directly: {fits_url.rsplit('/', 1)[-1]}: {e}")
    if in_bucket:
        try:
            return s3.fetch_cutout(fits_url, ra, dec, size, path)
        except LookupError:
            raise
        except Exception as e:  # noqa: BLE001 - e.g. a file not (yet) in the bucket
            print(f"S3 read failed, using IRSA cutout: {fits_url.rsplit('/', 1)[-1]}: {e}")
    content = _get_with_retry(cutout_url(fits_url, ra, dec, size))
    tmp = path.with_suffix(f".{threading.get_ident()}.part")
    tmp.write_bytes(content)
    tmp.replace(path)
    return path


def _find_quietly(fits_url: str) -> str | None:
    """s3.find_in_bucket, None on any error (TAP is the fallback)."""
    from . import s3
    try:
        return s3.find_in_bucket(fits_url)
    except Exception:  # noqa: BLE001
        return None


# T27: the exposure list for a position is cached on disk, so a new field of view (same centre)
# or a rebuild skips the IRSA TAP queries. Kept for a day so new data releases still show up;
# `refresh=True` forces a new query.
EXPOSURE_TTL_S = 24 * 3600


def cached_exposures(ra: float, dec: float, refresh: bool = False, raw_root: Path = RAW_ROOT):
    from .query import Exposure

    path = raw_root / "exposures" / f"{ra:.4f}_{dec:+.4f}.json"
    if not refresh and path.exists() and time.time() - path.stat().st_mtime < EXPOSURE_TTL_S:
        d = json.loads(path.read_text(encoding="utf-8"))
        return [Exposure(**e) for e in d["exposures"]], d["provenance"]
    from . import mirror
    if raw_root == RAW_ROOT and mirror.available():
        return mirror.find_exposures_local(ra, dec)   # T31: local index, milliseconds; not cached
    exposures, prov = find_exposures(ra, dec)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{threading.get_ident()}.part")
    tmp.write_text(json.dumps({"provenance": prov, "exposures": [asdict(e) for e in exposures]}),
                   encoding="utf-8")
    tmp.replace(path)
    return exposures, prov


def release_name(collection: str | None) -> str | None:
    """T64: 'spherex_qr3_deep' -> 'QR3 deep', 'spherex_dr1' -> 'DR1' (DR = data release, QR = quick release)."""
    if not collection:
        return None
    parts = collection.removeprefix("spherex_").split("_")
    return " ".join([parts[0].upper(), *parts[1:]])


def exposure_summary(exposures, prov: dict | None = None) -> dict:
    """T64: what SPHEREx had at this position when it was checked: how many images, the latest one, which
    collections. Written into target.json at build time (`source_exposures`); the Live API compares it with
    a fresh check (`GET /api/targets/<id>/updates`) to say when newer data exist."""
    latest = max(exposures, key=lambda e: e.mjd_mid) if exposures else None
    return {"count": len(exposures),
            "latest_mjd": round(latest.mjd_mid, 6) if latest else None,
            "latest_utc": latest.time_utc if latest else None,
            "collections": sorted({e.collection for e in exposures}),
            "checked_utc": (prov or {}).get("retrieved_utc")}


def source_of(path: Path, fits_url: str, ra: float, dec: float) -> str:
    """The URL the cached cutout was read from: S3 (with the detector rows kept) or an IRSA cutout."""
    from astropy.io import fits

    h = fits.getheader(path, 0)
    if "S3SRC" in h:
        from .s3 import s3_url
        via = f";via={h['VIA']}" if "VIA" in h else ""   # T57: cut by the team VM
        return f"{s3_url(fits_url)}#rows={h.get('S3CUT', '').replace(' ', '')}{via}"
    return cutout_url(fits_url, ra, dec, float(path.stem))


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
    w, b = wavelengths_at(hdul, [x0], [y0])
    return float(w[0]), float(b[0])


def wavelengths_at(hdul, xs, ys) -> tuple[np.ndarray, np.ndarray]:
    """wavelength_at for many pixels at once (T85: every source of a field in one cutout)."""
    from scipy.interpolate import RegularGridInterpolator

    h = hdul["IMAGE"].header
    t = hdul["WCS-WAVE"].data
    gx, gy = np.asarray(t["X"][0], float), np.asarray(t["Y"][0], float)
    vals = np.asarray(t["VALUES"][0], float)          # (ny, nx, 2): wavelength, bandwidth
    dx = np.asarray(xs, float) + 1 - h.get("CRPIX1W", h.get("CRPIX1A")) + h.get("CRVAL1W", 1)
    dy = np.asarray(ys, float) + 1 - h.get("CRPIX2W", h.get("CRPIX2A")) + h.get("CRVAL2W", 1)
    pts = np.c_[np.clip(dy, gy.min(), gy.max()), np.clip(dx, gx.min(), gx.max())]
    w, b = (RegularGridInterpolator((gy, gx), vals[..., k])(pts) for k in (0, 1))
    return w, b


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


LABEL_BUDGET_S = 5.0


def _labels_with_budget(target: dict, final_json: Path) -> None:
    """Add catalogue labels (T19), but don't let slow catalogue servers hold up the field.

    SIMBAD/Gaia took ~40 s on 2026-11-14 (CDS partly down). If they need more than LABEL_BUDGET_S,
    the target is written without labels and a background thread adds them to `final_json` (the
    folder the target ends up in; the Live API builds in a temp folder and moves it) when done."""
    import copy

    result: dict = {}

    def work():
        try:
            from .labels import add_labels
            t = copy.deepcopy(target)
            add_labels(t)
            result["labels"] = t.get("labels", [])
            result["prov"] = t["provenance"][len(target["provenance"]):]
        except Exception as ex:  # noqa: BLE001 - labels are nice to have, frames are the product
            result["error"] = str(ex)

    th = threading.Thread(target=work, daemon=True, name="labels")
    th.start()
    th.join(LABEL_BUDGET_S)
    if not th.is_alive():
        target["labels"] = result.get("labels", [])
        target["provenance"] += result.get("prov", [])
        if "error" in result:
            print(f"labels skipped: {result['error']}")
        return
    target["labels"] = []

    def finish_later():
        th.join()
        if "labels" not in result:
            print(f"late labels skipped: {result.get('error')}")
            return
        for _ in range(120):                      # wait until the build has been moved into place
            if final_json.exists():
                break
            time.sleep(1)
        try:
            t = json.loads(final_json.read_text(encoding="utf-8"))
            t["labels"] = result["labels"]
            t["provenance"] += result["prov"]
            tmp = final_json.with_suffix(".labels.part")
            tmp.write_text(json.dumps(t, indent=1), encoding="utf-8")
            tmp.replace(final_json)
        except Exception as ex:  # noqa: BLE001
            print(f"late labels not written: {ex}")

    threading.Thread(target=finish_later, daemon=True, name="labels-late").start()


def remap_to_frames(items: list[dict], stub_frames: list[dict], frames: list[dict]) -> list[dict]:
    """T54: positions computed on the early stub -> the built target's frames (matched by obs_id and
    detector). Frames that were dropped (failed download, little coverage) lose their positions;
    objects left without any are dropped."""
    final = {(f["obs_id"], f["detector"]): f["id"] for f in frames}
    to_final = {f["id"]: final.get((f["obs_id"], f["detector"])) for f in stub_frames}
    out = []
    for it in items:
        pos = [{**p, "frame_id": to_final[p["frame_id"]]} for p in it.get("positions", [])
               if to_final.get(p["frame_id"])]
        if pos:
            out.append({**it, "positions": pos})
    return out


def build_target(target_id: str, ra_deg: float, dec_deg: float, size_arcmin: float,
                 out_root: Path = Path("data/targets"), progress: Progress | None = None,
                 per_group: int = PER_GROUP, name: str | None = None, refresh: bool = False,
                 final_root: Path | None = None, labels: bool = False, early=None) -> Path:
    """Query, download, align, render. Returns the target folder with a valid target.json.

    early: T54, called once the frames are chosen (before any download) with a stub target: centre,
    image grid and one frame per chosen exposure (provisional ids, obs_id, detector, mjd). Labels and
    known objects need nothing more, so the caller can compute them while the images download; map
    the results to the final frames with `remap_to_frames`."""
    def report(step, done=None, total=None, message=""):
        if progress:
            progress(step, done, total, message)

    report("query", message="searching IRSA for SPHEREx images")
    exposures, prov_query = cached_exposures(ra_deg, dec_deg, refresh=refresh)
    if not exposures:
        raise LookupError(f"no SPHEREx images cover RA {ra_deg} Dec {dec_deg}")
    chosen = select(exposures, per_group)

    npix = max(16, int(round(size_arcmin * 60 / PIXEL_SCALE_ARCSEC)))
    cut_deg = size_arcmin / 60 * 1.5 + 0.01   # room for the rotation of the original frames
    if early is not None:
        early({"id": target_id, "synthetic": False, "center": {"ra_deg": ra_deg, "dec_deg": dec_deg},
               "size_arcmin": size_arcmin,
               "image": {"width": npix, "height": npix, "pixel_scale_arcsec": PIXEL_SCALE_ARCSEC},
               "frames": [{"id": f"c{i:03d}", "mjd": round(e.mjd_mid, 6), "obs_id": e.obs_id, "detector": e.detector,
                           "time_utc": e.time_utc, "epoch": e.epoch} for i, e in enumerate(chosen)],
               "labels": [], "known_objects": [], "detections": [], "provenance": []})
    downloads_started = _now()
    n_cached = sum(cached_cutout(e.fits_url, ra_deg, dec_deg, cut_deg) is not None for e in chosen)
    paths: list[Path | None] = [None] * len(chosen)
    errors = []
    report("download", 0, len(chosen), f"{len(chosen)} of {len(exposures)} SPHEREx images, "
                                       f"{n_cached} already cached")
    out_w = output_wcs(ra_deg, dec_deg, npix)
    # T57: each image is aligned as soon as it has arrived, while the rest still download
    # (0.2 s per image; 2 threads halve that, more don't help).
    aligned: dict[int, object] = {}
    from . import s3
    threads = REMOTE_THREADS if s3.remote_available() else S3_THREADS
    with ThreadPoolExecutor(threads) as pool, ThreadPoolExecutor(ALIGN_THREADS) as align_pool:
        futs = {pool.submit(fetch, e.fits_url, ra_deg, dec_deg, cut_deg): i for i, e in enumerate(chosen)}
        for n, f in enumerate(as_completed(futs), 1):
            try:
                paths[futs[f]] = f.result()
                aligned[futs[f]] = align_pool.submit(resample, paths[futs[f]], out_w, npix, ra_deg, dec_deg)
            except Exception as e:  # noqa: BLE001 - one failed cutout shouldn't kill the field
                errors.append(f"{chosen[futs[f]].obs_id} D{chosen[futs[f]].detector}: {e}")
            report("download", n, len(chosen), f"downloaded {n}/{len(chosen)}")

    # T31: paths derived from the local mirror can be wrong for reprocessed images (l2b_retry,
    # ~1%); IRSA answers 404 there. Look those up once via TAP and try again.
    lost = [i for i, p in enumerate(paths) if p is None]
    if lost:
        # T57: list the bucket first (~1-2 s, finds l2b_retry versions); TAP (20-40 s) only for the rest
        fixed = {}
        with ThreadPoolExecutor(min(8, len(lost))) as pool:
            for i, url in zip(lost, pool.map(lambda i: _find_quietly(chosen[i].fits_url), lost)):
                if url:
                    fixed[chosen[i].publisher_did] = url
        rest = [chosen[i].publisher_did for i in lost if chosen[i].publisher_did not in fixed]
        try:
            from .mirror import resolve_urls
            if rest:
                fixed.update(resolve_urls(rest))
        except Exception as ex:  # noqa: BLE001
            errors.append(f"TAP lookup for {len(rest)} failed paths: {ex}")
        for i in lost:
            url = fixed.get(chosen[i].publisher_did)
            if url and url != chosen[i].fits_url:
                chosen[i].fits_url = url
                try:
                    paths[i] = fetch(url, ra_deg, dec_deg, cut_deg)
                except Exception as ex:  # noqa: BLE001
                    errors.append(f"{chosen[i].obs_id} D{chosen[i].detector} (retry): {ex}")

    out = Path(out_root) / target_id
    (out / "frames").mkdir(parents=True, exist_ok=True)
    for old in (out / "frames").glob("*"):
        old.unlink()
    frames = []
    for i, (e, p) in enumerate(zip(chosen, paths)):
        report("align", i, len(chosen), f"aligning {e.obs_id} D{e.detector}")
        if p is None:
            continue
        try:
            done = aligned.get(i)                 # aligned during the download (not for T31 retries)
            img, wave, bw = done.result() if done is not None else resample(p, out_w, npix, ra_deg, dec_deg)
        except Exception as ex:  # noqa: BLE001
            errors.append(f"{e.obs_id} D{e.detector}: {ex}")
            continue
        if np.isfinite(img).mean() < 0.2:
            continue                      # target barely on this image
        u = source_of(p, e.fits_url, ra_deg, dec_deg)                 # where the pixels came from
        fid = f"f{len(frames):03d}"
        render_png(img, out / "frames" / f"{fid}.png")
        frames.append({
            "id": fid, "time_utc": e.time_utc, "mjd": round(e.mjd_mid, 6), "epoch": e.epoch,
            "detector": e.detector, "wavelength_um": round(wave, 4), "bandwidth_um": round(bw, 4),
            "image": f"frames/{fid}.png", "obs_id": e.obs_id, "source_url": u,
            "collection": e.collection,   # T64: which release (spherex_dr1, spherex_qr3_deep, ...)
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
            "service": ("SPHEREx level-2 images: AWS Open Data s3://nasa-irsa-spherex (HTTP Range; cut next to "
                        "the bucket by the team VM where a frame's source_url says via=...) or IRSA cutouts"),
            "query": f"{len(chosen)} cutouts (per frame: source_url; {n_cached} from cache), "
                     f"needed size {cut_deg:.4f} deg, "
                     f"{per_group} per epoch+detector of {len(exposures)} images; "
                     f"{len(errors)} failed",
            "retrieved_utc": downloads_started}],
        "frames": frames, "known_objects": [], "detections": [],
        "source_exposures": exposure_summary(exposures, prov_query),   # T64: for "newer data available"
    }
    if labels:
        report("render", len(frames), len(frames), "adding catalogue labels")
        _labels_with_budget(target, Path(final_root or out_root) / target_id / "target.json")
    else:
        target["labels"] = []      # T37: labels only on request (server: /api/targets/<id>/labels)
    from .pairs import add_pairs  # T17: wavelength-matched pairs for the viewer's pairs blink
    add_pairs(target)
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
    ap.add_argument("--labels", action="store_true", help="also add catalogue labels (SIMBAD, Gaia)")
    ap.add_argument("--refresh", action="store_true", help="re-query IRSA instead of the cached exposure list")
    args = ap.parse_args(argv)
    out = build_target(args.id, args.ra, args.dec, args.size, args.out,
                       progress=lambda s, d=None, t=None, m="": print(f"[{s}] {m}", flush=True),
                       per_group=args.per_group, refresh=args.refresh, labels=args.labels)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
