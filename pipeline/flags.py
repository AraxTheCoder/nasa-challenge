"""T60: SPHEREx quality flags in plain words.

Every level-2 image has a FLAGS plane: one bit per reason a pixel may be unreliable. Names and bits are the
mask planes of the FLAGS header (MSKNnnnn / MSKMnnnn, read from a DR1 image on 2026-11-15); the words are ours.
`kind`: "bad" = the value can't be trusted (these are the bits of build.HW_MASK), "warn" = look twice,
"info" = says something about the pixel, not a defect.
"""
from __future__ import annotations

import numpy as np

# bit: (name, kind, plain words)
FLAG_BITS: dict[int, tuple[str, str, str]] = {
    0: ("TRANSIENT", "bad", "a sudden jump during the exposure: a cosmic ray, or something passing"),
    1: ("OVERFLOW", "bad", "saturated: too bright for the detector"),
    2: ("SUR_ERROR", "bad", "error in the onboard processing"),
    6: ("NONFUNC", "bad", "dead pixel"),
    7: ("DICHROIC", "warn", "low sensitivity at the edge of the beam splitter"),
    9: ("MISSING_DATA", "bad", "data lost onboard"),
    10: ("HOT", "bad", "hot pixel"),
    11: ("COLD", "bad", "pixel with anomalously low signal"),
    12: ("FULLSAMPLE", "info", "full readout history available"),
    14: ("PHANMISS", "bad", "a readout artefact (phantom) could not be corrected"),
    15: ("NONLINEAR", "warn", "so bright that the value is only approximate"),
    17: ("PERSIST", "bad", "afterglow of a bright source seen just before"),
    19: ("OUTLIER", "warn", "differs from the other exposures of this spot: an artefact, or something that moved or changed"),
    20: ("CROSSTALK", "warn", "electronic echo of a bright source elsewhere on the detector"),
    21: ("SOURCE", "info", "a catalogued source is here"),
    22: ("GHOST", "warn", "ghost image of a bright source in the field"),
    23: ("GHOST_FPA", "warn", "ghost image of a bright source on another detector"),
    24: ("GHOST_EXT", "warn", "stray light from a bright source outside the field"),
    25: ("STREAK", "bad", "a streak: a satellite or a fast-moving object"),
    26: ("BLOOM", "bad", "charge spilling from a saturated star"),
    27: ("SNOWBALL", "bad", "a large cosmic-ray hit"),
    28: ("HALO", "bad", "halo around a transient hit"),
}
NAMES = {name: (bit, kind, words) for bit, (name, kind, words) in FLAG_BITS.items()}


def names(value: int) -> list[str]:
    """Flag names set in a FLAGS value (or the OR of several pixels), lowest bit first."""
    v = int(value)
    return [FLAG_BITS[b][0] if b in FLAG_BITS else f"BIT{b}" for b in range(32) if v >> b & 1]


def in_pixels(flag_values) -> list[str]:
    """Names of every flag set in any of the given pixels."""
    a = np.asarray(flag_values, dtype=np.int64)
    return names(int(np.bitwise_or.reduce(a.ravel()))) if a.size else []


def legend() -> list[dict]:
    return [{"name": n, "bit": b, "kind": k, "meaning": w} for b, (n, k, w) in sorted(FLAG_BITS.items())]


def meanings(rows: list[dict]) -> dict:
    """{name: {kind, meaning}} for every flag that occurs in the measurements `rows` (their "flags" lists)."""
    seen = sorted({n for r in rows for n in r.get("flags") or []}, key=lambda n: NAMES.get(n, (99,))[0])
    return {n: {"kind": NAMES[n][1], "meaning": NAMES[n][2]} if n in NAMES else {"kind": "warn", "meaning": "unnamed flag"}
            for n in seen}


# ---------- T60 step 2: where in a field the data is unreliable ----------

MIN_SHARE = 0.15         # flagged in at least this share of the frames to be drawn
BAD_MASK = sum(1 << b for b, (_, k, _) in FLAG_BITS.items() if k == "bad")
WARN_MASK = sum(1 << b for b, (_, k, _) in FLAG_BITS.items() if k == "warn")


def frame_flags(target: dict, frame: dict, raw_root=None):
    """The frame's FLAGS on the field grid (rows top-down, nearest pixel); None if its image can't be had."""
    import warnings
    from astropy.io import fits
    from astropy.wcs import WCS, FITSFixedWarning
    from . import build
    from .labels import Grid
    from .photometry import image_url

    c = target["center"]
    if not frame.get("source_url"):
        return None
    url, root = image_url(frame["source_url"]), raw_root or build.RAW_ROOT
    path = build.cached_cutout(url, c["ra_deg"], c["dec_deg"], 0.0, root)
    if path is None:           # evicted from the cache (T58/T97): fetched again like a build would
        try:
            path = build.fetch(url, c["ra_deg"], c["dec_deg"], target.get("size_arcmin", 15) / 60, root)
        except Exception:  # noqa: BLE001 - this frame just doesn't count
            return None
    g = Grid(target)
    with fits.open(path) as hd, warnings.catch_warnings():
        warnings.simplefilter("ignore", FITSFixedWarning)
        flg = hd["FLAGS"].data.astype(np.int64)
        w = WCS(hd["IMAGE"].header)
    yy, xx = np.mgrid[0:g.h, 0:g.w]
    ra, dec = g.wcs.all_pix2world(xx, g.h - 1 - yy, 0)             # row 0 is the top (north)
    ix, iy = w.all_world2pix(ra, dec, 0)
    ix, iy = np.rint(ix).astype(int), np.rint(iy).astype(int)
    ok = (ix >= 0) & (ix < flg.shape[1]) & (iy >= 0) & (iy < flg.shape[0])
    out = np.full((g.h, g.w), -1, np.int64)                        # -1 = this frame doesn't cover the pixel
    out[ok] = flg[iy[ok], ix[ok]]
    return out


def field_mask(target: dict, raw_root=None) -> dict:
    """How often each pixel of the field is flagged over its frames.
    {"rgba": (h, w, 4) uint8 overlay, "n_frames", "bad_fraction": share of pixel-frames flagged bad, "counts":
    {flag name: pixel-frames}}. Red = unreliable (alpha grows with the share of frames), amber = look twice."""
    h, w = target["image"]["height"], target["image"]["width"]
    bad = np.zeros((h, w), np.float32); warn = np.zeros((h, w), np.float32); cov = np.zeros((h, w), np.float32)
    counts: dict[str, int] = {}
    n = 0
    from concurrent.futures import ThreadPoolExecutor
    frames = target.get("frames", [])
    with ThreadPoolExecutor(8) as pool:
        all_flags = list(pool.map(lambda f: frame_flags(target, f, raw_root), frames))
    for fl in all_flags:
        if fl is None:
            continue
        n += 1
        seen = fl >= 0
        cov += seen
        bad += seen & ((fl & BAD_MASK) != 0)
        warn += seen & ((fl & WARN_MASK) != 0) & ((fl & BAD_MASK) == 0)
        for b, (name, kind, _) in FLAG_BITS.items():
            if kind != "info":
                k = int((seen & ((fl >> b & 1) == 1)).sum())
                if k:
                    counts[name] = counts.get(name, 0) + k
    fb = np.divide(bad, cov, out=np.zeros_like(bad), where=cov > 0)
    fw = np.divide(warn, cov, out=np.zeros_like(warn), where=cov > 0)
    rgba = np.zeros((h, w, 4), np.uint8)
    # only what persists: a pixel flagged in one frame of 36 (a cosmic ray) is not a property of the place
    is_bad, is_warn = fb >= MIN_SHARE, (fb < MIN_SHARE) & (fw >= MIN_SHARE)
    rgba[is_bad] = (255, 70, 70, 0)
    rgba[is_warn] = (245, 190, 60, 0)
    rgba[..., 3] = np.where(is_bad, 70 + 150 * fb, np.where(is_warn, 50 + 110 * fw, 0)).astype(np.uint8)
    return {"rgba": rgba, "n_frames": n, "bad_fraction": float(bad.sum() / cov.sum()) if cov.sum() else 0.0,
            "counts": dict(sorted(counts.items(), key=lambda kv: -kv[1]))}
