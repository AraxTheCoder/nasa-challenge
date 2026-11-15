"""T06: mover detection v0 on a built field.

    python -m detect.movers data/targets/<id>        # prints what it found, changes nothing

What counts as a detection: a point source that is in the SPHEREx images at one moment and not at the same
sky position at other times. Three steps, all on the field's cached SPHEREx cutouts (calibrated images with
their variance and flags, not the stretched display frames):

1. Sightings. Per image: minus the zodiacal light and a smooth background, signal-to-noise over 3x3 pixels,
   local peaks >= SN_DETECT with no flagged pixel under them. Position = flux-weighted centre -> RA/Dec.
2. Reference. A sighting is dropped when there is something at the same sky position at another time:
   S/N >= SN_REF in an image of the same detector (same wavelength range, so a star is as bright as before),
   or >= SN_REF_OTHER in any other image. It needs MIN_REFS images of the same detector at other times that
   cover the spot, otherwise nothing can be said and it is dropped too.
3. Confirmation. SPHEREx images every spot with two detectors at the same moment (bands 1+4, 2+5, 3+6 share
   the light through a dichroic). A real source is in both; a cosmic ray, hot pixel or persistence is in one.
   Sightings without their twin (S/N >= SN_TWIN at the same sky position) are dropped.

What is left is grouped: the two simultaneous images are one sighting; sightings within LINK_HOURS and a
plausible speed become one track. `detect.classify` (T08) then decides known / unknown / artifact.

Limits of v0: built fields keep 2 images per survey pass and detector, days apart, so most real movers are
seen at one moment only (no motion measured); single exposures reach about V 14-15 (T09), so expect few
detections and mostly known asteroids; ghosts and diffraction spikes of bright stars also show in both
detectors and move with the telescope's roll, so sightings near a very bright source are dropped
(BRIGHT_SN, BRIGHT_PX).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

VERSION = "1"
SN_DETECT = 6.0          # a sighting: 3x3 signal-to-noise of the peak
SN_REF = 3.0             # same detector, other time: this much at the spot = it is always there
SN_REF_OTHER = 5.0       # any other detector, other time
SN_TWIN = 4.0            # the simultaneous image of the other detector must show it at least this much
MATCH_PX = 1.5           # "the same sky position", in native pixels (6.15")
MIN_REFS = 2             # reference images (same detector, other time) needed to judge a sighting
SAME_TIME_S = 90.0       # images this close in time are simultaneous
OTHER_TIME_H = 1.0       # references must be at least this far away in time
LINK_HOURS = 12.0        # sightings closer than this may be one object ...
MAX_LINK_RATE = 150.0    # ... if it would move no faster than this, arcsec per hour (main belt ~30, near-Earth more)
BRIGHT_SN = 300.0        # near something this bright (spikes, ghosts, wings) nothing is trusted
BRIGHT_PX = 10
EDGE_PX = 4
BKG_PX = 25              # box of the median background
MAX_SIGHTINGS = 400      # per image; more means a crowded or broken image: only the brightest are used


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _background(img: np.ndarray) -> np.ndarray:
    """Smooth background: the median of BKG_PX boxes, interpolated between the box centres (a running median
    of the same size gives the same detections and takes 0.3 s per image instead of a few ms)."""
    from scipy import ndimage

    ny, nx = img.shape
    by, bx = max(1, ny // BKG_PX), max(1, nx // BKG_PX)
    ye, xe = np.linspace(0, ny, by + 1).astype(int), np.linspace(0, nx, bx + 1).astype(int)
    coarse = np.array([[np.median(img[ye[i]:ye[i + 1], xe[j]:xe[j + 1]]) for j in range(bx)] for i in range(by)])
    if coarse.size == 1:
        return np.full(img.shape, coarse[0, 0])
    yc, xc = (ye[:-1] + ye[1:]) / 2 - 0.5, (xe[:-1] + xe[1:]) / 2 - 0.5
    yi = np.interp(np.arange(ny), yc, np.arange(by)) if by > 1 else np.zeros(ny)
    xi = np.interp(np.arange(nx), xc, np.arange(bx)) if bx > 1 else np.zeros(nx)
    return ndimage.map_coordinates(coarse, np.meshgrid(yi, xi, indexing="ij"), order=1, mode="nearest")


def sn_map(img: np.ndarray, var: np.ndarray | None, bad: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(3x3 signal-to-noise, background-subtracted image, 'not usable' mask grown by one pixel).
    The noise is the image's own (VARIANCE where given), rescaled so the S/N of empty sky has scatter 1."""
    from scipy import ndimage

    img = np.where(bad, np.nan, img)
    fill = np.nanmedian(img) if np.isfinite(img).any() else 0.0
    filled = np.where(np.isfinite(img), img, fill)
    sub = filled - _background(filled)
    sub[bad] = 0.0
    if var is None or not np.isfinite(var).any():
        var = np.full(img.shape, 1.0)
    var = np.where(np.isfinite(var) & (var > 0) & ~bad, var, np.nanmedian(var[np.isfinite(var) & (var > 0)]))
    sn = ndimage.uniform_filter(sub, 3, mode="nearest") * 9 / np.sqrt(ndimage.uniform_filter(var, 3, mode="nearest") * 9)
    wide = ndimage.binary_dilation(bad, iterations=1)
    sky = sn[~wide]
    if sky.size > 50:
        med = np.median(sky)
        mad = 1.4826 * np.median(np.abs(sky - med))
        if mad > 0:
            sn = (sn - med) / mad
    sn[wide] = 0.0
    return sn, sub, wide


def load_frame(path: Path) -> dict | None:
    """One cached cutout ready for detection, or None if it can't be read."""
    from astropy.io import fits
    from astropy.wcs import WCS, FITSFixedWarning
    from pipeline import build

    try:
        with fits.open(path) as hd, warnings.catch_warnings():
            warnings.simplefilter("ignore", FITSFixedWarning)
            img = hd["IMAGE"].data.astype(float)
            if "ZODI" in hd:
                img = img - hd["ZODI"].data
            var = hd["VARIANCE"].data.astype(float) if "VARIANCE" in hd else None
            bad = ~np.isfinite(img)
            if "FLAGS" in hd:
                bad |= (hd["FLAGS"].data.astype(np.int64) & build.HW_MASK) != 0
            wcs = WCS(hd["IMAGE"].header)
    except Exception:  # noqa: BLE001 - a broken cache file must not fail the build
        return None
    sn, sub, wide = sn_map(img, var, bad)
    return {"sn": sn, "img": sub, "bad": wide, "wcs": wcs}


def sightings(fr: dict) -> list[dict]:
    """Local S/N peaks of one image: [{x, y (native pixels), ra, dec, sn}], brightest first."""
    from scipy import ndimage

    sn, img = fr["sn"], fr["img"]
    ny, nx = sn.shape
    peak = (sn >= SN_DETECT) & (sn == ndimage.maximum_filter(sn, size=5, mode="nearest"))
    peak[:EDGE_PX], peak[-EDGE_PX:], peak[:, :EDGE_PX], peak[:, -EDGE_PX:] = False, False, False, False
    near_bright = ndimage.maximum_filter(sn, size=2 * BRIGHT_PX + 1, mode="nearest") >= BRIGHT_SN
    ys, xs = np.nonzero(peak & ~near_bright)
    order = np.argsort(-sn[ys, xs])[:MAX_SIGHTINGS]
    out = []
    for y, x in zip(ys[order], xs[order]):
        box = np.clip(img[y - 1:y + 2, x - 1:x + 2], 0, None)
        tot = box.sum()
        if tot <= 0 or fr["bad"][y - 1:y + 2, x - 1:x + 2].any():
            continue
        dy, dx = np.mgrid[-1:2, -1:2]
        cx, cy = x + float((box * dx).sum() / tot), y + float((box * dy).sum() / tot)
        out.append({"x": cx, "y": cy, "sn": float(sn[y, x])})
    if out:
        ra, dec = fr["wcs"].all_pix2world([s["x"] for s in out], [s["y"] for s in out], 0)
        for s, a, d in zip(out, ra, dec):
            s["ra"], s["dec"] = float(a), float(d)
    return out


def sn_at(fr: dict, ra, dec) -> np.ndarray:
    """Highest S/N within MATCH_PX of sky positions (arrays) in an image; NaN where the spot is off it or flagged."""
    ra, dec = np.atleast_1d(np.asarray(ra, float)), np.atleast_1d(np.asarray(dec, float))
    out = np.full(ra.shape, np.nan)
    if not ra.size:
        return out
    x, y = fr["wcs"].all_world2pix(ra, dec, 0)
    ny, nx = fr["sn"].shape
    r = int(math.ceil(MATCH_PX))
    with np.errstate(invalid="ignore"):
        xi, yi = np.rint(x), np.rint(y)
        ok = np.isfinite(x) & np.isfinite(y) & (xi >= r) & (xi < nx - r) & (yi >= r) & (yi < ny - r)
    for k in np.nonzero(ok)[0]:
        a, b = int(xi[k]), int(yi[k])
        if not fr["bad"][b - 1:b + 2, a - 1:a + 2].any():
            out[k] = fr["sn"][b - r:b + r + 1, a - r:a + r + 1].max()
    return out


def _sep_arcsec(a: dict, b: dict) -> float:
    return 3600 * math.hypot((a["ra"] - b["ra"]) * math.cos(math.radians(a["dec"])), a["dec"] - b["dec"])


def find(frames: list[dict], loaded: dict[str, dict], inside=None) -> tuple[list[list[dict]], dict]:
    """frames: target frames (id, mjd, detector); loaded: frame id -> load_frame(); inside(ra, dec) -> bool array
    limits the search (the cutouts are larger than the field). Returns (groups, counts): each group is a list of
    confirmed sightings {frame_id, mjd, detector, ra, dec, sn, refs} of one object."""
    fs = [f for f in frames if f["id"] in loaded]
    counts = {"images": len(fs), "sightings": 0, "also_there_at_other_times": 0, "no_reference": 0,
              "one_detector_only": 0, "confirmed": 0}
    kept = []
    for f in fs:
        ss = sightings(loaded[f["id"]])
        if ss and inside is not None:
            keep = inside(np.array([s["ra"] for s in ss]), np.array([s["dec"] for s in ss]))
            ss = [s for s, k in zip(ss, keep) if k]
        if not ss:
            continue
        counts["sightings"] += len(ss)
        ra, dec = np.array([s["ra"] for s in ss]), np.array([s["dec"] for s in ss])
        refs, there = np.zeros(len(ss), int), np.zeros(len(ss), bool)
        twin = np.full(len(ss), -np.inf)
        twin_frames: list[dict | None] = [None] * len(ss)
        for g in fs:
            dt_s = abs(g["mjd"] - f["mjd"]) * 86400
            same = g.get("detector") == f.get("detector")
            if dt_s >= OTHER_TIME_H * 3600:
                v = sn_at(loaded[g["id"]], ra[~there], dec[~there])      # what is settled is not looked at again
                idx = np.nonzero(~there)[0]
                seen = np.isfinite(v)
                if same:
                    refs[idx[seen]] += 1
                there[idx[seen & (np.nan_to_num(v, nan=-np.inf) >= (SN_REF if same else SN_REF_OTHER))]] = True
            elif g["id"] != f["id"] and dt_s <= SAME_TIME_S and not same:
                v = np.nan_to_num(sn_at(loaded[g["id"]], ra, dec), nan=-np.inf)
                for k in np.nonzero(v > twin)[0]:
                    twin[k], twin_frames[k] = v[k], g
        for k, s in enumerate(ss):
            if there[k]:
                counts["also_there_at_other_times"] += 1
            elif refs[k] < MIN_REFS:
                counts["no_reference"] += 1
            elif twin[k] < SN_TWIN:
                counts["one_detector_only"] += 1
            else:
                counts["confirmed"] += 1
                g = twin_frames[k]
                kept.append({"frame_id": f["id"], "mjd": f["mjd"], "detector": f.get("detector"), "ra": s["ra"],
                             "dec": s["dec"], "sn": round(s["sn"], 1), "refs": int(refs[k])})
                kept.append({"frame_id": g["id"], "mjd": g["mjd"], "detector": g.get("detector"), "ra": s["ra"],
                             "dec": s["dec"], "sn": round(float(twin[k]), 1), "refs": int(refs[k])})

    # group: the simultaneous pair is one sighting; sightings close in time and reachable are one object
    parent = list(range(len(kept)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, a in enumerate(kept):
        for j in range(i):
            b = kept[j]
            hours = abs(a["mjd"] - b["mjd"]) * 24
            sep = _sep_arcsec(a, b)
            if (hours * 3600 <= SAME_TIME_S and sep <= MATCH_PX * 6.2) or \
               (SAME_TIME_S < hours * 3600 and hours <= LINK_HOURS and sep <= MAX_LINK_RATE * hours and a["frame_id"] != b["frame_id"]):
                parent[root(i)] = root(j)
    groups: dict[int, list[dict]] = {}
    for i, s in enumerate(kept):
        groups.setdefault(root(i), []).append(s)
    out = []
    for g in groups.values():
        best = {}
        for s in g:                                  # one point per image: the strongest
            if s["frame_id"] not in best or s["sn"] > best[s["frame_id"]]["sn"]:
                best[s["frame_id"]] = s
        out.append(sorted(best.values(), key=lambda s: (s["mjd"], s["detector"] or 0)))
    out.sort(key=lambda g: -max(s["sn"] for s in g))
    return out, counts


def find_movers(target: dict, raw_root: Path | None = None) -> dict:
    """Fill target['detections'] with tracks found in the field's cached SPHEREx cutouts (unclassified: T08 does
    that) and append one provenance entry. Without cached images nothing is claimed. Returns the target."""
    from pipeline import build, photometry
    from pipeline.labels import Grid

    raw_root = raw_root or build.RAW_ROOT
    c = target["center"]
    loaded = {}
    for f in target.get("frames", []):
        url = f.get("source_url")
        path = build.cached_cutout(photometry.image_url(url), c["ra_deg"], c["dec_deg"], 0.0, raw_root) if url else None
        fr = load_frame(path) if path else None
        if fr is not None:
            loaded[f["id"]] = fr
    prov = target.setdefault("provenance", [])
    if len(loaded) < 2 * MIN_REFS:
        prov.append({"service": "mover search (T06) skipped",
                     "query": f"{len(loaded)} of {len(target.get('frames', []))} frames have a cached SPHEREx image",
                     "retrieved_utc": _now()})
        return target
    grid = Grid(target)

    def inside(ra, dec):
        x, y = grid.to_xy(ra, dec)
        return grid.contains(x, y, margin=-EDGE_PX)

    groups, counts = find(target["frames"], loaded, inside)
    dets = []
    for n, g in enumerate(groups, 1):
        track = []
        for s in g:
            x, y = grid.to_xy(s["ra"], s["dec"])
            track.append({"frame_id": s["frame_id"], "ra_deg": round(s["ra"], 6), "dec_deg": round(s["dec"], 6),
                          "x": round(float(x), 2), "y": round(float(y), 2)})
        moments = len({round(s["mjd"] * 86400 / SAME_TIME_S) for s in g})
        dets.append({"id": f"d{n:03d}", "status": "unknown", "matched_object": None, "synthetic": False,
                     "score": 0.0, "track": track,
                     "evidence": {"moments": moments, "images": len(g), "absent_in": min(s["refs"] for s in g),
                                  "sn": max(s["sn"] for s in g)}})
    target["detections"] = dets
    prov.append({"service": "detect.movers (T06)",
                 "query": (f"v{VERSION}: 3x3 S/N >= {SN_DETECT:g}; gone at other times (S/N < {SN_REF:g} same detector, "
                           f"< {SN_REF_OTHER:g} others, >= {MIN_REFS} references); in both simultaneous detectors "
                           f"(S/N >= {SN_TWIN:g}); {counts}; {len(dets)} detection(s)"),
                 "retrieved_utc": _now()})
    return target


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m detect.movers", description=__doc__.split("\n\n")[0])
    ap.add_argument("target_dir", type=Path)
    args = ap.parse_args(argv)
    target = json.loads((args.target_dir / "target.json").read_text(encoding="utf-8"))
    target["detections"] = []
    find_movers(target)
    print(target["provenance"][-1]["service"], "|", target["provenance"][-1]["query"])
    for d in target["detections"]:
        p = d["track"][0]
        print(f"  {d['id']}  RA {p['ra_deg']:.5f} Dec {p['dec_deg']:+.5f}  x {p['x']:.1f} y {p['y']:.1f}  "
              f"frames {[q['frame_id'] for q in d['track']]}  {d['evidence']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
