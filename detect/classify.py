"""T08: classify detections as known / unknown / artifact (CONTRACTS "Detection", v0.9 `reason`).

Input: a target with `detections` (from T06; each a `track` of per-frame positions), `known_objects`
(T07, JPL, as seen from SPHEREx) and, when present, catalogue `labels` (T19; opt-in since v0.8).
Output: the same detections with `status`, `matched_object`, `score` (0-1), `motion` and a plain-words
`reason`. Nothing else in the target changes, except one provenance entry.

Order of the rules (first that applies wins):
1. known      the track follows a known asteroid/comet: median distance over shared frames <= MATCH_PX
2. known      the track follows a *moving* catalogued star (e.g. Barnard's Star) the same way
3. artifact   sits on a catalogued star that does not move (a star, not a mover)
4. artifact   seen in one frame only (nothing to confirm motion with)
5. artifact   does not move (< STILL_PX over the track)
6. artifact   positions inside one visit don't lie on a straight line (RMS > LINE_RMS_PX)
7. artifact   faster than any asteroid (> MAX_RATE_ARCSEC_PER_HR: satellite glint, cosmic ray pair)
8. unknown    moves plausibly and matches nothing: the interesting case

    python -m detect.classify data/targets/<id>        # updates target.json in place
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

from pipeline.motion import summarize

RULES_VERSION = "1"
MATCH_PX = 2.0                   # ~12": JPL positions (~1") + SPHEREx PSF/centroid + trailing
STILL_PX = 0.5                   # less than this over the whole track = not a mover
LOOKUP_SERVICES = ("SB Identification", "SkyBoT")  # provenance services of the known-object lookup (T07, T51)
LINE_RMS_PX = 1.0                # straight-line residual inside one visit
VISIT_GAP_DAYS = 0.25            # same visit grouping as detect.known_objects
MAX_RATE_ARCSEC_PER_HR = 7200.0  # 2 deg/h: faster than practically any asteroid seen by SPHEREx


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _by_frame(positions: list[dict]) -> dict[str, dict]:
    return {p["frame_id"]: p for p in positions if "frame_id" in p}


def _median_distance_px(track: dict[str, dict], other: dict[str, dict]) -> tuple[float, int]:
    """Median pixel distance over the frames both have, and how many frames that is."""
    shared = [f for f in track if f in other]
    if not shared:
        return math.inf, 0
    d = [math.hypot(track[f]["x"] - other[f]["x"], track[f]["y"] - other[f]["y"]) for f in shared]
    return statistics.median(d), len(shared)


def _best_match(track: dict[str, dict], candidates: list[tuple[str, list[dict]]]) -> tuple[str | None, float, int]:
    """Closest candidate (name, median px, shared frames) that matches on enough frames."""
    best = (None, math.inf, 0)
    for name, positions in candidates:
        med, n = _median_distance_px(track, _by_frame(positions))
        # need >= 2 shared frames, unless the detection itself has only one
        if n >= min(2, len(track)) and med <= MATCH_PX and med < best[1]:
            best = (name, med, n)
    return best


def _line_rms_px(points: list[dict], mjd: dict[str, float]) -> float:
    """RMS distance of points from the best straight line x(t), y(t) (least squares). 0 if < 3 points."""
    if len(points) < 3:
        return 0.0
    t = [mjd[p["frame_id"]] for p in points]
    t0 = sum(t) / len(t)
    tt = [v - t0 for v in t]
    denom = sum(v * v for v in tt)
    res = 0.0
    for axis in ("x", "y"):
        vals = [p[axis] for p in points]
        mean = sum(vals) / len(vals)
        slope = sum(a * (v - mean) for a, v in zip(tt, vals)) / denom if denom > 0 else 0.0
        res += sum((v - (mean + slope * a)) ** 2 for a, v in zip(tt, vals))
    return math.sqrt(res / len(points))


def _visits(points: list[dict], mjd: dict[str, float]) -> list[list[dict]]:
    out: list[list[dict]] = []
    for p in sorted(points, key=lambda p: mjd[p["frame_id"]]):
        if out and mjd[p["frame_id"]] - mjd[out[-1][-1]["frame_id"]] <= VISIT_GAP_DAYS:
            out[-1].append(p)
        else:
            out.append([p])
    return out


def _visit_rate(points: list[dict], mjd: dict[str, float], scale: float) -> float:
    """Fastest motion within one visit, "/h (first to last point of the visit).

    Own calculation on purpose: pipeline.motion.summarize ignores frame pairs < 0.05 h apart, but
    SPHEREx exposures inside a visit are ~2 min apart, which is exactly where asteroids show motion.
    """
    best = 0.0
    for v in _visits(points, mjd):
        hrs = (mjd[v[-1]["frame_id"]] - mjd[v[0]["frame_id"]]) * 24
        if len(v) >= 2 and hrs > 0:
            best = max(best, math.hypot(v[-1]["x"] - v[0]["x"], v[-1]["y"] - v[0]["y"]) * scale / hrs)
    return best


def known_objects_looked_up(target: dict) -> bool:
    """True if detect.known_objects (T07) asked for candidates: JPL sb_ident or, since T51, IMCCE SkyBoT."""
    return any(any(k in (p.get("service") or "") for k in LOOKUP_SERVICES) for p in target.get("provenance", []))


def classify_one(det: dict, target: dict) -> dict:
    """Return a copy of one detection with status, matched_object, score, motion and reason set."""
    frames = target["frames"]
    mjd = {f["id"]: f["mjd"] for f in frames}
    scale = target["image"]["pixel_scale_arcsec"]
    points = [p for p in det.get("track", []) if p.get("frame_id") in mjd]
    track = _by_frame(points)
    out = dict(det)
    summary = summarize(points, frames, scale)
    within = _visit_rate(points, mjd, scale)

    # motion (CONTRACTS): keep T06's if given, else derive from the track
    if not out.get("motion") and summary:
        rate = within or (summary["rate_arcsec_per_yr"] or 0.0) / (365.25 * 24)
        if summary["pa_deg"] is not None:
            out["motion"] = {"rate_arcsec_per_hr": round(rate, 3), "pa_deg": summary["pa_deg"] % 360}

    def result(status: str, reason: str, score: float, matched: str | None = None) -> dict:
        out.update(status=status, matched_object=matched, score=round(max(0.0, min(1.0, score)), 2), reason=reason)
        return out

    # 1. known asteroid / comet
    known = target.get("known_objects") or []
    name, med, n = _best_match(track, [(k["name"], k.get("positions", [])) for k in known])
    if name:
        src = next((k.get("source") for k in known if k["name"] == name), None)
        src = "JPL" if src == "jpl-sbident" else (src or "catalogue")
        return result("known", f"follows {name} ({src}) within {med:.1f} px on {n} frame(s)", 1.0 - 0.3 * med / MATCH_PX, name)

    # 2./3. catalogued star: moving ones are known, still ones mean "not a mover"
    labels = target.get("labels") or []
    lname, lmed, ln = _best_match(track, [(l.get("name", l.get("id", "?")), l.get("positions", [])) for l in labels])
    if lname:
        label = next(l for l in labels if l.get("name", l.get("id")) == lname)
        lclass = (label.get("motion") or {}).get("class") or (summarize(label.get("positions", []), frames, scale) or {}).get("class")
        if lclass and lclass != "still":
            return result("known", f"follows the catalogued star {lname} ({lclass}) within {lmed:.1f} px", 0.95 - 0.3 * lmed / MATCH_PX, lname)
        return result("artifact", f"sits on the catalogued star {lname}, which does not move", 0.1)

    # 4.-7. not a believable mover
    if len(points) < 2:
        return result("artifact", "seen in one frame only: nothing to confirm motion with", 0.15)
    reach_px = max(math.hypot(p["x"] - points[0]["x"], p["y"] - points[0]["y"]) for p in points)
    if reach_px < STILL_PX:
        return result("artifact", f"does not move (< {STILL_PX} px over the track)", 0.1)
    worst = max((_line_rms_px(v, mjd) for v in _visits(points, mjd)), default=0.0)
    if worst > LINE_RMS_PX:
        return result("artifact", f"positions within one visit are off a straight line by {worst:.1f} px RMS", 0.2)
    if within > MAX_RATE_ARCSEC_PER_HR:
        return result("artifact", f"moves {within / 3600:.1f}°/h: faster than any asteroid (satellite glint?)", 0.15)

    # 8. unknown: score from evidence (more frames, more visits, straighter = more convincing)
    n_visits = len(_visits(points, mjd))
    score = 0.45 + 0.08 * min(len(points) - 1, 4) + 0.1 * min(n_visits - 1, 2) + 0.1 * (1 - worst / LINE_RMS_PX)
    cls = "fast mover" if within >= 1.0 else (summary or {}).get("class")
    looked_up = known_objects_looked_up(target)
    return result("unknown", f"moves ({cls or 'mover'}) and matches no known object" +
                  ("" if looked_up else " (known asteroids were not looked up for this field: run detect.known_objects)"),
                  score if looked_up else min(score, 0.6))


def classify_detections(target: dict) -> dict:
    """Classify every detection in place; append one provenance entry. Returns the target."""
    dets = target.get("detections") or []
    if not dets:
        return target
    target["detections"] = [classify_one(d, target) for d in dets]
    counts = {s: sum(1 for d in target["detections"] if d["status"] == s) for s in ("known", "unknown", "artifact")}
    target.setdefault("provenance", []).append({
        "service": "detect.classify (T08)",
        "query": (f"rules v{RULES_VERSION}: match <= {MATCH_PX} px median over shared frames, still < {STILL_PX} px, "
                  f"line RMS <= {LINE_RMS_PX} px, rate <= {MAX_RATE_ARCSEC_PER_HR:g}\"/h; "
                  f"{len(target.get('known_objects') or [])} known objects, {len(target.get('labels') or [])} labels; "
                  f"result {counts}"),
        "retrieved_utc": _now(),
    })
    return target


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m detect.classify", description=__doc__.split("\n\n")[0])
    ap.add_argument("target_dir", type=Path)
    args = ap.parse_args(argv)
    path = args.target_dir / "target.json"
    target = json.loads(path.read_text(encoding="utf-8"))
    classify_detections(target)
    path.write_text(json.dumps(target, indent=2), encoding="utf-8")
    for d in target.get("detections", []):
        print(f"  {d['id']:<8} {d['status']:<9} {d['score']:.2f}  {d['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
