"""tilegen (T42/T47): live deep-zoom SPHEREx tiles (HiPS orders 6-7) from level-2 images.

Subcomponent: runs inside the Live API (local mode) or as its own service next to the AWS bucket
(`python -m tilegen`, remote mode), see tilegen/README.md. Depends on pipeline.s3 + pipeline.mirror.

The all-sky maps stop at order 5 (IRSA cube, 12.9"/px). Zooming further anywhere on the sky, the
map asks for order 6 (6.4"/px, SPHEREx's native 6.15") and 7 (3.2"/px) tiles of the layer
`spherex-live`; we build each from the AWS Open Data bucket:

  1. the band the user picked (cube slice 0-101) gives the detector: slice // 17 + 1,
  2. the local index (pipeline.mirror) gives the images of that detector covering the tile; we take
     the IMAGES_PER_TILE closest to their own image centre (cleanest optics), different epochs first,
  3. their rows come in cached chunks (pipeline.s3.S3Image), are sampled at the tile's HEALPix pixel
     centres, background-subtracted and divided by the noise of their chunk (so tiles and images
     match in brightness), averaged and asinh-stretched to 8 bit; alpha 0 where no image has data.

Tile pixel (row, col) <-> HEALPix NESTED sub-index: row -> even bits, col -> odd bits (same as server/hips.py).
"""
from __future__ import annotations

import io
import math
import os
import threading
from concurrent.futures import ThreadPoolExecutor

import numpy as np

LIVE_ORDERS = (6, 7)
# 1 image per tile when S3 is slow (from Europe: ~0.1 MB/s per connection on 2026-11-14), more
# next to the bucket (the Google Cloud VM sets TILEGEN_IMAGES=3).
IMAGES_PER_TILE = int(os.environ.get("TILEGEN_IMAGES", "1"))
SHARE_ORDER = 5               # tiles inside one order-5 cell use the same images (shared row chunks)
MAX_FILL = 3                  # more images, only while the tile still has holes (image edge, bad pixels)
FILL_UNTIL = 0.995            # stop once this fraction of the tile has data
FOOTPRINT_DEG = 1.6            # image centre within this of the tile centre (detector half-width 1.74)
TILE = 512
LO_SIGMA, HI_SIGMA, SOFT = -1.0, 150.0, 1.5

_index = None
_index_lock = threading.Lock()
_pool = ThreadPoolExecutor(16, thread_name_prefix="live-chunk")      # S3 row-chunk reads
_images = ThreadPoolExecutor(8, thread_name_prefix="live-image")     # one task per image (uses _pool)


def _mirror():
    """The local SPHEREx image index. data/ is gitignored, so on a fresh checkout it is missing:
    then it is built in the background (once, ~3 min) and IndexNotReady is raised meanwhile."""
    global _index
    with _index_lock:
        if _index is None:
            from pipeline.mirror import Index, IndexNotReady, ensure_background
            state = ensure_background()
            if state != "ready":
                raise IndexNotReady(f"local SPHEREx index (data/mirror/index.npz) {state}; "
                                    "building it takes ~3 min, tiles come after that")
            _index = Index()
        return _index


_XY = None


def _xy_table():
    """Tile pixel -> NESTED sub-index offset: row -> even bits, col -> odd bits."""
    global _XY
    if _XY is None:
        rows, cols = np.mgrid[0:TILE, 0:TILE].astype(np.int64)
        z = np.zeros_like(rows)
        for b in range(9):
            z |= ((rows >> b) & 1) << (2 * b)
            z |= ((cols >> b) & 1) << (2 * b + 1)
        _XY = z
    return _XY


def pick_images(ra: float, dec: float, detector: int, k: int = IMAGES_PER_TILE) -> list[str]:
    """FITS URLs of up to k images of this detector covering (ra, dec), best placed first."""
    from pipeline.mirror import derive_url, resolve_urls

    idx = _mirror()
    d = idx.d
    cand = idx.covering(ra, dec, radius_deg=FOOTPRINT_DEG)
    cand = cand[d["detector"][cand] == detector]
    if not len(cand):
        return []
    r, de = math.radians(ra), math.radians(dec)
    p = np.array([math.cos(de) * math.cos(r), math.cos(de) * math.sin(r), math.sin(de)], np.float32)
    order = cand[np.argsort(-(idx.xyz[cand] @ p))]          # closest image centre first
    from pipeline.query import assign_epochs
    mid = (d["t_min"][order] + d["t_max"][order]) / 2
    ep = assign_epochs(mid) if len(order) else []
    chosen, seen = [], set()
    for i, j in enumerate(order):                             # one per epoch first, then fill up
        if ep[i] not in seen:
            chosen.append(j); seen.add(ep[i])
        if len(chosen) == k:
            break
    for j in order:
        if len(chosen) == k:
            break
        if j not in chosen:
            chosen.append(j)
    urls, missing = [], []
    for j in chosen:
        coll, obs, det = str(d["collection"][j]), str(d["obs_id"][j]), int(d["detector"][j])
        u = derive_url(coll, obs, det, idx.versions)
        if u:
            urls.append(u)
        else:
            missing.append(f"ivo://irsa.ipac/{coll}?{obs}/D{det}")
    if missing:
        urls += list(resolve_urls(missing).values())
    return urls


def _covers(fits_url: str, ra: float, dec: float, margin_px: int = 20) -> bool:
    from pipeline.s3 import NotInBucket, S3Image

    try:
        im = S3Image.get(fits_url)
    except NotInBucket:
        return False
    x, y = im.wcs.all_world2pix(ra, dec, 0)
    return margin_px <= x <= im.nx - 1 - margin_px and margin_px <= y <= im.ny - 1 - margin_px


def _sample(fits_url: str, lon: np.ndarray, lat: np.ndarray) -> np.ndarray | None:
    """Noise-normalised values of one image at the given sky positions (NaN = no data)."""
    from scipy.ndimage import map_coordinates

    from pipeline.s3 import CHUNK_ROWS, NotInBucket, S3Image

    try:
        im = S3Image.get(fits_url)
    except NotInBucket:          # reprocessed file under another path: the other images still do
        return None
    x, y = im.wcs.all_world2pix(lon, lat, 0)
    inside = (x >= 0) & (x <= im.nx - 1) & (y >= 0) & (y <= im.ny - 1)
    if not inside.any():
        return None
    out = np.full(lon.shape, np.nan, np.float32)
    y_in = y[inside]
    c0, c1 = int(y_in.min()) // CHUNK_ROWS, int(min(im.ny - 1, y_in.max() + 1)) // CHUNK_ROWS
    parts = list(_pool.map(im.chunk, range(c0, c1 + 1)))
    img = np.concatenate([(p[0] - p[2]) / p[3] for p in parts])          # per chunk: (v - med) / sigma
    bad = np.concatenate([p[1] for p in parts])
    yy = y_in - c0 * CHUNK_ROWS
    vals = map_coordinates(np.where(bad, 0, img), [yy, x[inside]], order=1, mode="nearest")
    badv = map_coordinates(bad.astype(np.float32), [yy, x[inside]], order=1, mode="nearest") > 0.25
    vals[badv] = np.nan
    out[inside] = vals
    return out


def render(slice_: int, order: int, npix: int) -> bytes | None:
    """PNG (grey + alpha) of one live tile, or None if no SPHEREx image covers it."""
    import astropy.units as u
    from astropy_healpix import HEALPix
    from PIL import Image

    if order not in LIVE_ORDERS:
        return None
    detector = min(6, max(1, slice_ // 17 + 1))
    lon_c, lat_c = HEALPix(nside=2 ** order, order="nested").healpix_to_lonlat(npix)
    # Choose images for the whole order-5 cell, so neighbouring tiles read the same row chunks;
    # if those don't cover this tile, fall back to the best images for the tile itself.
    parent = npix >> (2 * (order - SHARE_ORDER))
    lon_p, lat_p = HEALPix(nside=2 ** SHARE_ORDER, order="nested").healpix_to_lonlat(parent)
    urls = pick_images(lon_p.to_value(u.deg), lat_p.to_value(u.deg), detector)
    if not urls or not _covers(urls[0], lon_c.to_value(u.deg), lat_c.to_value(u.deg)):
        urls = pick_images(lon_c.to_value(u.deg), lat_c.to_value(u.deg), detector)
    if not urls:
        return None
    lon, lat = HEALPix(nside=2 ** (order + 9), order="nested").healpix_to_lonlat(
        (np.int64(npix) * TILE * TILE + _xy_table()).ravel())
    lon, lat = lon.to_value(u.deg), lat.to_value(u.deg)
    stack = [s for s in _images.map(lambda url: _sample(url, lon, lat), urls) if s is not None]
    # Fill holes: where the chosen image ends inside the tile or has masked pixels, sample further
    # images (best placed for this tile first) only at the still empty pixels.
    v = None
    if stack:
        with np.errstate(all="ignore"):
            v = np.nanmean(np.stack(stack), axis=0)
    if v is None or np.isfinite(v).mean() < FILL_UNTIL:
        extra = [x for x in pick_images(lon_c.to_value(u.deg), lat_c.to_value(u.deg), detector, k=len(urls) + MAX_FILL)
                 if x not in urls][:MAX_FILL]
        for url in extra:
            hole = ~np.isfinite(v) if v is not None else np.ones(lon.shape, bool)
            if not hole.any():
                break
            s = _sample(url, lon[hole], lat[hole])
            if s is None:
                continue
            if v is None:
                v = np.full(lon.shape, np.nan, np.float32)
            v[hole] = s
            if np.isfinite(v).mean() >= FILL_UNTIL:
                break
    if v is None:
        return None
    ok = np.isfinite(v)
    lo, hi = math.asinh(LO_SIGMA / SOFT), math.asinh(HI_SIGMA / SOFT)
    g = (np.arcsinh(np.where(ok, v, 0) / SOFT) - lo) / (hi - lo)
    grey = (np.clip(g, 0, 1) * 255).astype(np.uint8)
    alpha = np.where(ok, 255, 0).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(np.dstack([grey.reshape(TILE, TILE), alpha.reshape(TILE, TILE)]), "LA").save(buf, "PNG")
    return buf.getvalue()
