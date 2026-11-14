"""T32: per-epoch HiPS tiles from built target folders, so Aladin Lite can blink epochs in the map.

For each epoch of a built target, the frames of that epoch (already on the common north-up grid,
8-bit, alpha = no data) are averaged into one image, and HiPS tiles are rendered from it on demand:

    /api/hips/<tid>                                  -> {"layers": [{epoch, label, url, n_frames}]}
    /api/hips/<tid>/e<epoch>/properties              -> HiPS properties
    /api/hips/<tid>/e<epoch>/Norder<k>/Dir<d>/Npix<n>.png

Tile pixel (row from top, col) <-> HEALPix NESTED index at nside 2^(k+9):
    npix * 512^2 + interleave(row -> even bits, col -> odd bits)
Checked against IRSA's copy of the CDS 2MASS K HiPS: Barnard's Star lands within 6-7" of its
position at orders 6 and 7 (2026-11-14).
"""
from __future__ import annotations

import io
import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np

TILE = 512
HIPS_ORDER = 7          # 3.2"/px: a bit finer than SPHEREx's 6.15"/px so zooming in stays sharp


def _interleave_table() -> np.ndarray:
    rows, cols = np.mgrid[0:TILE, 0:TILE].astype(np.int64)
    z = np.zeros_like(rows)
    for b in range(9):
        z |= ((rows >> b) & 1) << (2 * b)
        z |= ((cols >> b) & 1) << (2 * b + 1)
    return z


_XY = _interleave_table()


def epochs(target: dict) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    for f in target.get("frames", []):
        out.setdefault(int(f["epoch"]), []).append(f)
    return dict(sorted(out.items()))


def layers(tid: str, target: dict) -> list[dict]:
    res = []
    for ep, frames in epochs(target).items():
        t0, t1 = frames[0]["time_utc"][:10], frames[-1]["time_utc"][:10]
        res.append({"epoch": ep, "id": f"e{ep}", "n_frames": len(frames),
                    "label": f"Epoch {ep} · {t0} – {t1} · {len(frames)} frames",
                    "url": f"/api/hips/{tid}/e{ep}"})
    return res


def properties(tid: str, target: dict, ep: int) -> str:
    c = target["center"]
    lines = {
        "creator_did": f"ivo://spherex-blink/{tid}/e{ep}",
        "obs_title": f"SPHEREx epoch {ep} around RA {c['ra_deg']:.4f} Dec {c['dec_deg']:+.4f}"
                     + (" (SYNTHETIC)" if target.get("synthetic") else ""),
        "dataproduct_type": "image", "hips_version": "1.4", "hips_frame": "equatorial",
        "hips_order": str(HIPS_ORDER), "hips_order_min": "0", "hips_tile_width": str(TILE),
        "hips_tile_format": "png", "hips_initial_ra": str(c["ra_deg"]), "hips_initial_dec": str(c["dec_deg"]),
        "hips_initial_fov": str(target["size_arcmin"] / 60 * 2),
        "obs_copyright": "SPHEREx data: NASA/IPAC IRSA. Tiles rendered by SPHEREx Blink from the frames of this target.",
    }
    return "".join(f"{k:<20} = {v}\n" for k, v in lines.items())


@lru_cache(maxsize=32)
def epoch_image(target_dir: str, mtime: float, ep: int) -> tuple[np.ndarray, np.ndarray]:
    """Mean of the epoch's frames (grey 0-255) and a coverage mask. mtime keys the cache."""
    from PIL import Image

    d = Path(target_dir)
    t = json.loads((d / "target.json").read_text(encoding="utf-8"))
    acc = cnt = None
    for f in epochs(t)[ep]:
        a = np.asarray(Image.open(d / f["image"]).convert("LA"), np.float32)
        grey, alpha = a[..., 0], a[..., 1] > 0
        if acc is None:
            acc, cnt = np.zeros_like(grey), np.zeros_like(grey)
        acc += np.where(alpha, grey, 0)
        cnt += alpha
    mean = np.divide(acc, cnt, out=np.zeros_like(acc), where=cnt > 0)
    return mean, cnt > 0


def _grid_wcs(target: dict):
    from astropy.wcs import WCS

    w, h = target["image"]["width"], target["image"]["height"]
    s = target["image"]["pixel_scale_arcsec"] / 3600
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = [target["center"]["ra_deg"], target["center"]["dec_deg"]]
    wcs.wcs.crpix = [(w + 1) / 2, (h + 1) / 2]
    wcs.wcs.cdelt = [-s, s]
    return wcs, w, h


def _sep_deg(ra1, dec1, ra2, dec2) -> float:
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    c = math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(r1 - r2)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def tile_png(target_dir: Path, ep: int, order: int, npix: int) -> bytes | None:
    """PNG for one tile; rendered once per target version and then kept in memory (T41)."""
    mtime = (target_dir / "target.json").stat().st_mtime
    return _tile_cached(str(target_dir), mtime, ep, order, npix)


@lru_cache(maxsize=4096)
def _tile_cached(target_dir: str, mtime: float, ep: int, order: int, npix: int) -> bytes | None:
    return _render_tile(Path(target_dir), ep, order, npix)


def tiles_touching(target: dict, order: int) -> list[int]:
    """HEALPix tiles of this order that overlap the field (corners + centre + edge midpoints)."""
    import astropy.units as u
    from astropy_healpix import HEALPix

    c = target["center"]
    h = target["size_arcmin"] / 120
    cd = math.cos(math.radians(c["dec_deg"])) or 1e-6
    pts = [(c["ra_deg"] + dx * h / cd, c["dec_deg"] + dy * h) for dx in (-1, -0.5, 0, 0.5, 1) for dy in (-1, -0.5, 0, 0.5, 1)]
    hp = HEALPix(nside=2 ** order, order="nested")
    return sorted({int(p) for p in hp.lonlat_to_healpix([p[0] for p in pts] * u.deg, [p[1] for p in pts] * u.deg)})


def prerender(target_dir: Path) -> None:
    """Render every tile of every epoch that touches the field, finest orders first (T41)."""
    t = json.loads((target_dir / "target.json").read_text(encoding="utf-8"))
    for order in range(HIPS_ORDER, -1, -1):
        for npix in tiles_touching(t, order):
            for ep in epochs(t):
                try:
                    tile_png(target_dir, ep, order, npix)
                except Exception:  # noqa: BLE001 - best effort
                    pass


def _render_tile(target_dir: Path, ep: int, order: int, npix: int) -> bytes | None:
    """PNG (grey + alpha) for one HiPS tile, or None when the tile doesn't touch the field."""
    import astropy.units as u
    from astropy_healpix import HEALPix
    from PIL import Image

    t = json.loads((target_dir / "target.json").read_text(encoding="utf-8"))
    if ep not in epochs(t):
        return None
    c = t["center"]
    lon_c, lat_c = HEALPix(nside=2 ** order, order="nested").healpix_to_lonlat(npix)
    tile_radius = 58.6 / 2 ** order * 1.2              # generous: HEALPix cells are not square
    field_radius = t["size_arcmin"] / 60 * 0.75
    if _sep_deg(lon_c.to_value(u.deg), lat_c.to_value(u.deg), c["ra_deg"], c["dec_deg"]) > tile_radius + field_radius:
        return None

    lon, lat = HEALPix(nside=2 ** (order + 9), order="nested").healpix_to_lonlat(
        (np.int64(npix) * TILE * TILE + _XY).ravel())
    wcs, w, h = _grid_wcs(t)
    x, y = wcs.world_to_pixel_values(lon.to_value(u.deg), lat.to_value(u.deg))
    col, row = np.rint(x).astype(int), np.rint(h - 1 - y).astype(int)
    ok = (col >= 0) & (col < w) & (row >= 0) & (row < h)
    if not ok.any():
        return None
    mean, cov = epoch_image(str(target_dir), (target_dir / "target.json").stat().st_mtime, ep)
    grey = np.zeros(TILE * TILE, np.uint8)
    alpha = np.zeros(TILE * TILE, np.uint8)
    rr, cc = row[ok], col[ok]
    grey[ok] = mean[rr, cc].astype(np.uint8)
    alpha[ok] = np.where(cov[rr, cc], 255, 0)
    buf = io.BytesIO()
    Image.fromarray(np.dstack([grey.reshape(TILE, TILE), alpha.reshape(TILE, TILE)]), "LA").save(buf, "PNG")
    return buf.getvalue()
