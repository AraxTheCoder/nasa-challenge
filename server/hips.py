"""T32: per-epoch HiPS tiles from built target folders, so Aladin Lite can blink epochs in the map.

For each epoch of a built target, the frames of that epoch (already on the common north-up grid,
8-bit, alpha = no data) are averaged into one image, and HiPS tiles are rendered from it on demand:

    /api/hips/<tid>                                  -> {"layers": [{epoch, label, url, n_frames}]}
    /api/hips/<tid>/e<epoch>/properties              -> HiPS properties
    /api/hips/<tid>/e<epoch>/Norder<k>/Dir<d>/Npix<n>.png
T81: also one layer per frame (`f<frame id>`, e.g. f003) and A − B differences (`d-<a>-<b>`, B fitted to
A's brightness like the viewer's T43 difference: grey 128 = no change, white = brighter in A,
black = brighter in B), same URL scheme: /api/hips/<tid>/f003/..., /api/hips/<tid>/d-f003-f017/...

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


LAYER_RE = r"^(e\d+(d[1-6]|c)?|f\d{3,}|d-f\d{3,}-f\d{3,}|x-[a-z0-9_]+(-[a-z0-9_]+){0,9})$"
# x-<feature>: T93 chemistry map; x-<a>-<b>[-<c>...]: T96/T108 2 or more of them as one colour picture (wavelength order)
# T89: e<ep>d<n> = the epoch's frames of detector n only (one band of the map); e<ep>c = false colour of
# all of them: blue = D1+D2 (0.75-1.62 µm), green = D3+D4 (1.63-3.82 µm), red = D5+D6 (3.83-5.0 µm).
COLOUR = ((5, 6), (3, 4), (1, 2))          # R, G, B detector pairs
# T89 LRGB: set by the Live API (server/app.py) to SkyCache.chroma: (order, npix) -> (512, 512, 3) colour of
# that HEALPix tile from the all-band cube (RGB / mean). Then e<ep>c = the epoch's detail x that colour, so a
# one-detector field can be shown in false colour; without it, e<ep>c composes the field's own detectors.
CHROMA = None
_EP_RE = __import__("re").compile(r"^e(\d+)(?:d([1-6])|(c))?$")


def epoch_key(key: str):
    """'e2' -> (2, None, False); 'e2d3' -> (2, 3, False); 'e2c' -> (2, None, True)."""
    m = _EP_RE.match(key)
    return int(m.group(1)), int(m.group(2)) if m.group(2) else None, bool(m.group(3))


def frame_layers(tid: str, target: dict) -> list[dict]:
    """T81: one layer per frame, for the map's A/B blink and play."""
    return [{"epoch": int(f["epoch"]), "frame_id": f["id"], "id": f["id"], "url": f"/api/hips/{tid}/{f['id']}",
             "label": f"{f['id']} · epoch {f['epoch']} · {f.get('wavelength_um', 0):.3f} µm · D{f.get('detector', '?')}"}
            for f in sorted(target.get("frames", []), key=lambda f: f["mjd"])]


def has_layer(target: dict, key: str) -> bool:
    ids = {f["id"] for f in target.get("frames", [])}
    if key.startswith("e"):
        ep, det, _ = epoch_key(key)
        frames = epochs(target).get(ep, [])
        return bool(frames) and (det is None or any(int(f.get("detector") or 0) == det for f in frames))
    if key.startswith("d-"):
        _, a, b = key.split("-")
        return a in ids and b in ids
    if key.startswith("x-"):                           # T93: made by GET /api/targets/<id>/chemistry first
        from pipeline.chemistry import combo, parse_key
        parts = key[2:].split("-")
        if len(parts) == 1:                            # T109: <feature>[_z<z·10⁴>]
            try:
                return bool(parse_key(parts[0]))
            except ValueError:
                return False
        try:                                           # T96: one name per combination, in wavelength order
            return combo(parts) == parts
        except ValueError:
            return False
    return key in ids


def layers(tid: str, target: dict) -> list[dict]:
    res = []
    for ep, frames in epochs(target).items():
        t0, t1 = frames[0]["time_utc"][:10], frames[-1]["time_utc"][:10]
        dets = sorted({int(f["detector"]) for f in frames if f.get("detector")})
        res.append({"epoch": ep, "id": f"e{ep}", "n_frames": len(frames),
                    "label": f"Epoch {ep} · {t0} – {t1} · {len(frames)} frames",
                    "url": f"/api/hips/{tid}/e{ep}", "detectors": dets})   # T89: + e<ep>d<n>, e<ep>c
    return res


def properties(tid: str, target: dict, ep) -> str:
    c = target["center"]
    key = ep if isinstance(ep, str) else f"e{ep}"
    what = {"e": f"epoch {key[1:]}", "f": f"frame {key}", "d": f"difference {key[2:].replace('-', ' − ')}",
            "x": f"chemistry map {key[2:].replace('-', ' + ')} (feature minus continuum, T93/T96)"}[key[0]]
    if key[0] == "e":
        ep, det, colour = epoch_key(key)
        what = f"epoch {ep}" + (f", detector {det}" if det else ", false colour" if colour else "")
    lines = {
        "creator_did": f"ivo://spherex-blink/{tid}/{key}",
        "obs_title": f"SPHEREx {what} around RA {c['ra_deg']:.4f} Dec {c['dec_deg']:+.4f}"
                     + (" (SYNTHETIC)" if target.get("synthetic") else ""),
        "dataproduct_type": "image", "hips_version": "1.4", "hips_frame": "equatorial",
        "hips_order": str(HIPS_ORDER), "hips_order_min": "0", "hips_tile_width": str(TILE),
        "hips_tile_format": "png", "hips_initial_ra": str(c["ra_deg"]), "hips_initial_dec": str(c["dec_deg"]),
        "hips_initial_fov": str(target["size_arcmin"] / 60 * 2),
        "obs_copyright": "SPHEREx data: NASA/IPAC IRSA. Tiles rendered by SPHEREx Blink from the frames of this target.",
    }
    return "".join(f"{k:<20} = {v}\n" for k, v in lines.items())


@lru_cache(maxsize=64)
def epoch_image(target_dir: str, mtime: float, ep: int, det: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Mean of the epoch's frames (grey 0-255; det: only that detector's) and a coverage mask.
    mtime keys the cache."""
    from PIL import Image

    d = Path(target_dir)
    t = json.loads((d / "target.json").read_text(encoding="utf-8"))
    acc = cnt = None
    frames = [f for f in epochs(t)[ep] if det is None or int(f.get("detector") or 0) == det]
    for f in frames:
        a = np.asarray(Image.open(d / f["image"]).convert("LA"), np.float32)
        grey, alpha = a[..., 0], a[..., 1] > 0
        if acc is None:
            acc, cnt = np.zeros_like(grey), np.zeros_like(grey)
        acc += np.where(alpha, grey, 0)
        cnt += alpha
    if acc is None:                                      # no frame of that detector in this epoch
        w, h = t["image"]["width"], t["image"]["height"]
        return np.zeros((h, w), np.float32), np.zeros((h, w), bool)
    mean = np.divide(acc, cnt, out=np.zeros_like(acc), where=cnt > 0)
    return mean, cnt > 0


@lru_cache(maxsize=32)
def colour_image(target_dir: str, mtime: float, ep: int) -> tuple[np.ndarray, np.ndarray]:
    """T89: false colour of the epoch, (h, w, 3) 0-255: R = D5+D6, G = D3+D4, B = D1+D2; coverage mask."""
    chans, cov = [], None
    for pair in COLOUR:
        acc = cnt = None
        for det in pair:
            m, c = epoch_image(target_dir, mtime, ep, det)
            acc = np.where(c, m, 0) if acc is None else acc + np.where(c, m, 0)
            cnt = c.astype(np.float32) if cnt is None else cnt + c
        chans.append(np.divide(acc, cnt, out=np.zeros_like(acc), where=cnt > 0))
        cov = cnt > 0 if cov is None else cov | (cnt > 0)
    return np.dstack(chans), cov


@lru_cache(maxsize=256)
def frame_image(target_dir: str, mtime: float, fid: str) -> tuple[np.ndarray, np.ndarray]:
    """One frame (grey 0-255) and its coverage mask."""
    from PIL import Image

    d = Path(target_dir)
    t = json.loads((d / "target.json").read_text(encoding="utf-8"))
    f = next(f for f in t["frames"] if f["id"] == fid)
    a = np.asarray(Image.open(d / f["image"]).convert("LA"), np.float32)
    return a[..., 0], a[..., 1] > 0


@lru_cache(maxsize=64)
def diff_image(target_dir: str, mtime: float, a: str, b: str) -> tuple[np.ndarray, np.ndarray]:
    """A − B with B fitted to A (robust linear fit over pixels valid in both, as web/diff.js does):
    grey 128 = no change, white = brighter in A, black = brighter in B."""
    ga, ma = frame_image(target_dir, mtime, a)
    gb, mb = frame_image(target_dir, mtime, b)
    both = ma & mb
    out = np.full(ga.shape, 128.0, np.float32)
    if both.sum() < 10:
        return out, both
    x, y = gb[both], ga[both]
    keep = np.ones(x.size, bool)
    for _ in range(3):                                   # clip outliers (the movers) and refit
        gain, off = np.polyfit(x[keep], y[keep], 1) if keep.sum() > 10 else (1.0, 0.0)
        r = y - (gain * x + off)
        s = 1.4826 * np.median(np.abs(r[keep] - np.median(r[keep]))) or 1.0
        keep = np.abs(r) < 3 * s
    diff = ga - (gain * gb + off)
    scale = max(np.percentile(np.abs(diff[both]), 99.5), 1.0)
    out[both] = np.clip(128 + 127 * diff[both] / scale, 0, 255)
    return out, both


def layer_image(target_dir: str, mtime: float, key: str) -> tuple[np.ndarray, np.ndarray]:
    if key.startswith("e"):
        ep, det, colour = epoch_key(key)
        return colour_image(target_dir, mtime, ep) if colour else epoch_image(target_dir, mtime, ep, det)
    if key.startswith("d-"):
        _, a, b = key.split("-")
        return diff_image(target_dir, mtime, a, b)
    if key.startswith("x-"):
        return chemistry_image(target_dir, key[2:])
    return frame_image(target_dir, mtime, key)


def _chem_mtime(target_dir: Path, key: str) -> float:
    """T93/T96: chemistry maps change without target.json changing: the newest of their PNGs (0 = one missing)."""
    ps = [Path(target_dir) / "chemistry" / f"{f}.png" for f in key[2:].split("-")]
    return max(p.stat().st_mtime for p in ps) if all(p.is_file() for p in ps) else 0.0


def chemistry_image(target_dir: str, feature: str) -> tuple[np.ndarray, np.ndarray]:
    """T93: the chemistry map (grey 128 = like the continuum) and its coverage; empty if not made yet.
    T96: feature "a-b[-c]" = those maps as one colour picture (RGB)."""
    from PIL import Image

    if "-" in feature:
        from pipeline.chemistry import combined_map
        try:
            return combined_map(Path(target_dir), feature.split("-"))
        except (LookupError, ValueError):
            feature = "-"                              # not all made yet: empty, like a missing single map
    p = Path(target_dir) / "chemistry" / f"{feature}.png"
    if not p.is_file():
        t = json.loads((Path(target_dir) / "target.json").read_text(encoding="utf-8"))
        n = int(t["image"]["width"])
        return np.full((n, n), 128.0, np.float32), np.zeros((n, n), bool)
    a = np.asarray(Image.open(p).convert("LA"), np.float32)
    return a[..., 0], a[..., 1] > 0


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


def tile_png(target_dir: Path, ep, order: int, npix: int) -> bytes | None:
    """PNG for one tile; rendered once per target version and then kept in memory (T41).
    ep: an epoch number, or a layer key (`e1`, `f003`, `d-f003-f017`, T81)."""
    mtime = (target_dir / "target.json").stat().st_mtime
    key = ep if isinstance(ep, str) else f"e{ep}"
    if key.startswith("x-"):                  # T93: a chemistry map changes without target.json changing
        mtime = _chem_mtime(target_dir, key)
    return _tile_cached(str(target_dir), mtime, key, order, npix)


@lru_cache(maxsize=8192)
def _tile_cached(target_dir: str, mtime: float, key: str, order: int, npix: int) -> bytes | None:
    return _render_tile(Path(target_dir), key, order, npix)


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


def _render_tile(target_dir: Path, ep, order: int, npix: int) -> bytes | None:
    """PNG (grey + alpha) for one HiPS tile, or None when the tile doesn't touch the field."""
    import astropy.units as u
    from astropy_healpix import HEALPix
    from PIL import Image

    t = json.loads((target_dir / "target.json").read_text(encoding="utf-8"))
    key = ep if isinstance(ep, str) else f"e{ep}"
    if not has_layer(t, key):
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
    lrgb = key.startswith("e") and epoch_key(key)[2] and CHROMA is not None
    mtime = _chem_mtime(target_dir, key) if key.startswith("x-") else (target_dir / "target.json").stat().st_mtime
    mean, cov = layer_image(str(target_dir), mtime, f"e{epoch_key(key)[0]}" if lrgb else key)
    if lrgb:                                           # T89: detail of the epoch x colour of the cube there
        ch = CHROMA(order, npix)
        if ch is not None:
            lum = np.zeros(TILE * TILE, np.float32)
            lum[ok] = mean[row[ok], col[ok]]
            mean = None
            rgb = np.clip(lum.reshape(TILE, TILE, 1) * ch, 0, 255).reshape(TILE * TILE, 3)
    alpha = np.zeros(TILE * TILE, np.uint8)
    rr, cc = row[ok], col[ok]
    alpha[ok] = np.where(cov[rr, cc], 255, 0)
    buf = io.BytesIO()
    if lrgb and mean is None:
        Image.fromarray(np.dstack([rgb.astype(np.uint8).reshape(TILE, TILE, 3), alpha.reshape(TILE, TILE)]), "RGBA").save(buf, "PNG")
        return buf.getvalue()
    if mean.ndim == 3:                                 # T89 false colour: RGBA
        rgb = np.zeros((TILE * TILE, 3), np.uint8)
        rgb[ok] = mean[rr, cc].astype(np.uint8)
        Image.fromarray(np.dstack([rgb.reshape(TILE, TILE, 3), alpha.reshape(TILE, TILE)]), "RGBA").save(buf, "PNG")
        return buf.getvalue()
    grey = np.zeros(TILE * TILE, np.uint8)
    grey[ok] = mean[rr, cc].astype(np.uint8)
    Image.fromarray(np.dstack([grey.reshape(TILE, TILE), alpha.reshape(TILE, TILE)]), "LA").save(buf, "PNG")
    return buf.getvalue()
