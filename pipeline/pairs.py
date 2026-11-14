"""T17: wavelength-matched frame pairs across epochs (CONTRACTS v0.2 "Pair").

Stars change brightness with wavelength and no two SPHEREx frames share one, so only frames at
nearly the same wavelength compare fairly. A pair: two frames from different epochs, same
detector, |wavelength a - wavelength b| <= TOLERANCE x the smaller bandwidth. Closest matches are
taken first; each frame is used at most once per other epoch. `a` is the earlier frame.
On COSMOS detector 2, tolerance 0.5 gave 21 pairs (0.25 gave 7, 0.75 no more than 0.5).
"""
from __future__ import annotations

from itertools import combinations

TOLERANCE = 0.5


def find_pairs(frames: list[dict], tolerance: float = TOLERANCE) -> list[dict]:
    usable = [f for f in frames if f.get("bandwidth_um") and f.get("wavelength_um") is not None]
    pairs = []
    epochs = sorted({f["epoch"] for f in usable})
    detectors = sorted({f.get("detector") for f in usable}, key=lambda d: (d is None, d))
    for det in detectors:
        for ea, eb in combinations(epochs, 2):
            A = [f for f in usable if f["epoch"] == ea and f.get("detector") == det]
            B = [f for f in usable if f["epoch"] == eb and f.get("detector") == det]
            cand = sorted((abs(a["wavelength_um"] - b["wavelength_um"]), a["id"], b["id"], a, b) for a in A for b in B)
            used_a, used_b = set(), set()
            for dw, ida, idb, a, b in cand:
                if ida in used_a or idb in used_b:
                    continue
                if dw > tolerance * min(a["bandwidth_um"], b["bandwidth_um"]):
                    break  # sorted by dw: nothing closer follows
                used_a.add(ida); used_b.add(idb)
                first, second = (a, b) if a["mjd"] <= b["mjd"] else (b, a)
                pairs.append({"a": first["id"], "b": second["id"], "detector": det, "dwave_um": round(dw, 4),
                              "dt_days": round(second["mjd"] - first["mjd"], 2)})
    pairs.sort(key=lambda p: (p["detector"] is None, p["detector"], p["a"]))
    return pairs


def add_pairs(target: dict) -> dict:
    target["pairs"] = find_pairs(target.get("frames", []))
    return target
