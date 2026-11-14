"""Build the synthetic multi-epoch fixture `fixtures/targets/demo-epochs/` (T55). NOT SPHEREx data.

    python fixtures/make_demo_epochs.py            # from the repo root; deterministic, same bytes every run

`demo-synthetic` is schema 0.1 with 4 frames and nothing else. This one shows every optional field the
contract has (schema 0.2): 3 epochs, 2 detectors, `bandwidth_um`, transparent no-data pixels,
wavelength-matched `pairs`, `labels` with `motion` / `importance` / `aliases`, `known_objects`, and
detections that come out known / unknown / artifact. Labels get their motion from `pipeline.motion` and
detections their status / score / reason from `detect.classify`, so the values are what our code writes.

What is in the images (all made up, positions in pixels, x right / y down, north up, east left):
- 16 static stars with different colours (brighter at short or long wavelengths)
- a proper-motion star (label, 2 px over the year) and a variable star (label, dim in epoch 2)
- an unknown asteroid crossing the field in epoch 2 (detection, no known object)
- a known asteroid in epoch 1 (known object + detection) and a faint one in epoch 3 (known, not detected)
- a hot pixel in f000 (detection rejected as an artifact)
- a corner without data in every frame (alpha 0), as on a rotated SPHEREx frame edge
Standard library only, plus `pipeline.motion` and `detect.classify` (both standard library too).
"""
from __future__ import annotations

import json
import math
import random
import struct
import sys
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from detect.classify import classify_detections  # noqa: E402
from pipeline.motion import summarize  # noqa: E402

TID = "demo-epochs"
NAME = "Synthetic multi-epoch demo field (NOT SPHEREx data)"
W = H = 96
SCALE = 6.15                      # arcsec / pixel, as SPHEREx
RA0, DEC0 = 150.0, 2.2
CX, CY = (W - 1) / 2, (H - 1) / 2
STAMP = "2026-11-14T00:00:00Z"    # fixed, so the output is the same on every run
R = 41                            # spectral resolving power of bands 1-4, bandwidth = wavelength / R

# id, epoch, mjd, detector, wavelength (um). Visits ~1.7 h apart inside an epoch, epochs ~180 days apart.
FRAMES = [
    ("f000", 1, 60790.00, 2, 1.200), ("f001", 1, 60790.07, 2, 1.230), ("f002", 1, 60790.14, 3, 1.800),
    ("f003", 1, 60790.21, 3, 1.830), ("f004", 2, 60970.00, 2, 1.210), ("f005", 2, 60970.07, 2, 1.300),
    ("f006", 2, 60970.14, 3, 1.820), ("f007", 3, 61150.00, 2, 1.235), ("f008", 3, 61150.07, 3, 2.100),
]
NO_DATA = {1: (1, 1, 168), 2: (-1, 1, 70), 3: (1, -1, 74)}   # per epoch: pixels with a*x + b*y > c have no data


def sky(x: float, y: float) -> tuple[float, float]:
    dec = DEC0 - (y - CY) * SCALE / 3600
    ra = RA0 - (x - CX) * SCALE / 3600 / math.cos(math.radians(DEC0))
    return round(ra, 6), round(dec, 6)


def pos(fid: str, x: float, y: float) -> dict:
    ra, dec = sky(x, y)
    return {"frame_id": fid, "ra_deg": ra, "dec_deg": dec, "x": round(x, 2), "y": round(y, 2)}


def png_gray_alpha(path: Path, gray: list[list[int]], alpha: list[list[int]]) -> None:
    raw = b"".join(b"\x00" + bytes(v for px in zip(g, a) for v in px) for g, a in zip(gray, alpha))

    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 4, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def frame_time(mjd: float) -> str:
    return (datetime(1858, 11, 17, tzinfo=timezone.utc) + timedelta(days=mjd)).strftime("%Y-%m-%dT%H:%M:%SZ")


def pairs(frames: list[dict]) -> list[dict]:
    """CONTRACTS "Pair": different epochs, same detector, |dλ| <= 0.5 * smaller bandwidth, closest first,
    each frame in at most one pair per other epoch."""
    cand = []
    for a in frames:
        for b in frames:
            if a["epoch"] < b["epoch"] and a["detector"] == b["detector"]:
                dw = abs(a["wavelength_um"] - b["wavelength_um"])
                if dw <= 0.5 * min(a["bandwidth_um"], b["bandwidth_um"]):
                    cand.append((dw, a, b))
    used, out = set(), []
    for dw, a, b in sorted(cand, key=lambda c: c[0]):
        if (a["id"], b["epoch"]) in used or (b["id"], a["epoch"]) in used:
            continue
        used |= {(a["id"], b["epoch"]), (b["id"], a["epoch"])}
        out.append({"a": a["id"], "b": b["id"], "detector": a["detector"], "dwave_um": round(dw, 4),
                    "dt_days": round(b["mjd"] - a["mjd"], 2)})
    return sorted(out, key=lambda p: p["a"])


def main() -> None:
    tdir = ROOT / "fixtures" / "targets" / TID
    (tdir / "frames").mkdir(parents=True, exist_ok=True)
    rng = random.Random(52)

    frames = [{"id": fid, "time_utc": frame_time(mjd), "mjd": mjd, "epoch": ep, "detector": det,
               "wavelength_um": lam, "bandwidth_um": round(lam / R, 4), "image": f"frames/{fid}.png",
               "obs_id": None, "source_url": None} for fid, ep, mjd, det, lam in FRAMES]
    t0 = frames[0]["mjd"]

    # (x, y, flux at 1.5 um, spectral slope): flux(λ) = flux * (λ / 1.5) ** slope
    stars = [(rng.uniform(6, W - 6), rng.uniform(6, H - 6), rng.uniform(60, 200), rng.uniform(-1.5, 1.0)) for _ in range(16)]

    def pm_star(f):           # proper motion: 0.6 px east, 0.8 px north every 180 days (synthetic, ~12"/yr)
        days = f["mjd"] - t0
        return 30.0 - 0.6 * days / 180, 64.0 - 0.8 * days / 180

    def var_star(f):          # variable: same place, dim in epoch 2
        return 70.0, 25.0

    var_amp = {1: 1.0, 2: 0.4, 3: 1.3}

    def mover(f):             # unknown asteroid, epoch 2 only: 5 px west + 0.6 px south per visit (~18"/h)
        k = (f["mjd"] - 60970.00) / 0.07
        return 40.0 + 5.0 * k, 30.0 + 0.6 * k

    def known_a(f):           # known asteroid, epoch 1: 1.5 px east + 4 px south per visit
        k = (f["mjd"] - 60790.00) / 0.07
        return 60.0 - 1.5 * k, 20.0 + 4.0 * k

    def known_b(f):           # known asteroid, epoch 3, too faint to detect
        k = (f["mjd"] - 61150.00) / 0.07
        return 20.0 + 3.0 * k, 70.0 + 2.0 * k

    for f in frames:
        ep, lam = f["epoch"], f["wavelength_um"]
        sources = [(x, y, fl * (lam / 1.5) ** s) for x, y, fl, s in stars]
        sources.append((*pm_star(f), 220.0 * (lam / 1.5) ** 0.8))
        sources.append((*var_star(f), 180.0 * var_amp[ep]))
        if ep == 2:
            sources.append((*mover(f), 140.0))
        if ep == 1:
            sources.append((*known_a(f), 160.0))
        if ep == 3:
            sources.append((*known_b(f), 6.0))
        a, b, c = NO_DATA[ep]
        gray, alpha = [], []
        for y in range(H):
            grow, arow = [], []
            for x in range(W):
                v = 30.0 + rng.gauss(0, 3.0)
                for sx, sy, fl in sources:
                    d2 = (x - sx) ** 2 + (y - sy) ** 2
                    if d2 < 36:
                        v += fl * math.exp(-d2 / (2 * 1.1 ** 2))
                if f["id"] == "f000" and (x, y) == (10, 10):
                    v = 255.0      # hot pixel
                nodata = a * x + b * y > c
                grow.append(0 if nodata else max(0, min(255, round(v))))
                arow.append(0 if nodata else 255)
            gray.append(grow)
            alpha.append(arow)
        png_gray_alpha(tdir / f["image"], gray, alpha)

    by_epoch = lambda e: [f for f in frames if f["epoch"] == e]  # noqa: E731
    labels = [
        {"id": "l000", "name": "Synthetic star PM-1 (not real)", "kind": "high proper-motion star (synthetic)",
         "otype": "PM*", "source": "synthetic", "named": True, "mag": 9.8, "pm_mas_yr": 12480.0, "importance": 1,
         "positions": [pos(f["id"], *pm_star(f)) for f in frames]},
        {"id": "l001", "name": "Synthetic variable V-1 (not real)", "kind": "variable star (synthetic)",
         "otype": "V*", "source": "synthetic", "named": True, "mag": 10.5, "pm_mas_yr": 0.0, "importance": 2,
         "positions": [pos(f["id"], *var_star(f)) for f in frames]},
        {"id": "l002", "name": "Synthetic 0001 (not real)", "kind": "star (synthetic)", "otype": "*",
         "source": "synthetic", "named": False, "mag": 12.1, "pm_mas_yr": 0.0, "importance": 3,
         "aliases": ["Synthetic 0001 B (not real)"],
         "positions": [pos(f["id"], stars[0][0], stars[0][1]) for f in frames]},
    ]
    for lab in labels:
        lab["motion"] = summarize(lab["positions"], frames, SCALE)

    known_objects = [
        {"name": "Synthetic asteroid A (not real)", "source": "synthetic", "synthetic": True,
         "positions": [pos(f["id"], *known_a(f)) for f in by_epoch(1)]},
        {"name": "Synthetic asteroid B (not real)", "source": "synthetic", "synthetic": True,
         "positions": [pos(f["id"], *known_b(f)) for f in by_epoch(3)]},
    ]
    jitter = random.Random(7)

    def track(fn, fs):
        return [pos(f["id"], fn(f)[0] + jitter.uniform(-0.15, 0.15), fn(f)[1] + jitter.uniform(-0.15, 0.15)) for f in fs]
    detections = [
        {"id": "d001", "status": "unknown", "matched_object": None, "synthetic": True, "score": 0.0,
         "track": track(mover, by_epoch(2))},
        {"id": "d002", "status": "unknown", "matched_object": None, "synthetic": True, "score": 0.0,
         "track": [pos("f000", 10.0, 10.0)]},
        {"id": "d003", "status": "unknown", "matched_object": None, "synthetic": True, "score": 0.0,
         "track": track(known_a, by_epoch(1))},
    ]

    target = {
        "schema_version": "0.2", "id": TID, "name": NAME, "synthetic": True,
        "center": {"ra_deg": RA0, "dec_deg": DEC0}, "size_arcmin": round(W * SCALE / 60, 2),
        "image": {"width": W, "height": H, "pixel_scale_arcsec": SCALE},
        "provenance": [
            {"service": "fixtures/make_demo_epochs.py (synthetic, NOT SPHEREx data)",
             "query": "seeded random stars, a proper-motion star, a variable, two known and one unknown asteroid, "
                      "a hot pixel; labels, known objects and detection tracks are made up too",
             "retrieved_utc": STAMP},
            {"service": "Synthetic small bodies (stand-in for the SkyBoT / JPL SB Identification lookup, T07)",
             "query": "two made-up asteroids written by fixtures/make_demo_epochs.py; no service was asked",
             "retrieved_utc": STAMP},
        ],
        "frames": frames, "pairs": pairs(frames), "labels": labels, "labels_requested": True,
        "known_objects": known_objects, "detections": detections, "objects_requested": True,
    }
    classify_detections(target)        # status, score, reason, motion as detect.classify (T08) writes them
    for p in target["provenance"]:
        p["retrieved_utc"] = STAMP
    (tdir / "target.json").write_text(json.dumps(target, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    index_path = ROOT / "fixtures" / "targets" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    entry = {"id": TID, "name": NAME, "synthetic": True, "ra_deg": RA0, "dec_deg": DEC0, "n_frames": len(frames)}
    index["targets"] = [t for t in index["targets"] if t["id"] != TID] + [entry]
    index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    for d in target["detections"]:
        print(f"{d['id']}  {d['status']:<8} {d['score']:.2f}  {d['reason']}")
    print("pairs:", [(p["a"], p["b"]) for p in target["pairs"]])
    print("labels:", [(lab["name"], lab["motion"] and lab["motion"]["class"]) for lab in labels])


if __name__ == "__main__":
    main()
