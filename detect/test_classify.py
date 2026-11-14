"""Offline tests for detect.classify (T08): one synthetic detection per rule."""
from __future__ import annotations

import copy

import pytest

from detect.classify import MATCH_PX, classify_detections, classify_one

SCALE = 6.15  # "/px


def pos(fid, x, y):
    """Position with RA/Dec consistent with x/y on a simple north-up, east-left grid around (150, 2)."""
    return {"frame_id": fid, "ra_deg": 150.0 - (x - 72) * SCALE / 3600, "dec_deg": 2.0 - (y - 72) * SCALE / 3600, "x": x, "y": y}


# visit 1: three frames 3 min apart; visit 2: six days later, two frames
FRAMES = [{"id": f"f{i}", "mjd": m, "epoch": 1, "time_utc": "2025-08-15T00:00:00Z"}
          for i, m in enumerate([60000.0, 60000.002, 60000.004, 60006.0, 60006.002])]

TARGET = {
    "id": "t", "image": {"width": 146, "height": 146, "pixel_scale_arcsec": SCALE}, "frames": FRAMES,
    "known_objects": [{"name": "(4) Vesta", "source": "jpl-sbident", "synthetic": False,
                       "positions": [pos("f0", 30, 40), pos("f1", 33, 40), pos("f2", 36, 40)]}],
    "labels": [
        {"id": "l0", "name": "HD 1", "positions": [pos(f["id"], 100, 100) for f in FRAMES], "motion": {"class": "still"}},
        {"id": "l1", "name": "Barnard's star", "positions": [pos("f0", 120, 20), pos("f3", 121.5, 20)],
         "motion": {"class": "proper motion"}},
    ],
    "detections": [
        {"id": "d1", "track": [pos("f0", 30.4, 40.2), pos("f1", 33.3, 39.8), pos("f2", 36.5, 40.1)]},   # Vesta
        {"id": "d2", "track": [pos("f0", 60, 60)]},                                                    # one frame
        {"id": "d3", "track": [pos("f0", 80, 20), pos("f1", 80.1, 20), pos("f2", 80, 20.1)]},           # still
        {"id": "d4", "track": [pos("f0", 10, 120), pos("f1", 20, 126), pos("f2", 12, 120)]},            # zigzag
        {"id": "d5", "track": [pos("f0", 10, 10), pos("f1", 110, 10)]},                                 # too fast
        {"id": "d6", "track": [pos("f0", 50, 90), pos("f1", 55, 90), pos("f2", 60, 90), pos("f3", 50, 70)],
         "synthetic": True},                                                                          # unknown
        {"id": "d7", "track": [pos("f0", 100.2, 100), pos("f3", 99.9, 100.1)]},                         # on HD 1
        {"id": "d8", "track": [pos("f0", 120.1, 20), pos("f3", 121.4, 20.1)]},                          # Barnard
    ],
    "provenance": [{"service": "JPL SB Identification (sb_ident, first pass)", "query": "q", "retrieved_utc": "z"}],
}


@pytest.fixture()
def result():
    t = classify_detections(copy.deepcopy(TARGET))
    return {d["id"]: d for d in t["detections"]}, t


@pytest.mark.parametrize("did,status,matched,reason_part", [
    ("d1", "known", "(4) Vesta", "follows (4) Vesta"),
    ("d2", "artifact", None, "one frame"),
    ("d3", "artifact", None, "does not move"),
    ("d4", "artifact", None, "straight line"),
    ("d5", "artifact", None, "faster than any asteroid"),
    ("d6", "unknown", None, "matches no known object"),
    ("d7", "artifact", None, "catalogued star HD 1"),
    ("d8", "known", "Barnard's star", "proper motion"),
])
def test_rules(result, did, status, matched, reason_part):
    d = result[0][did]
    assert d["status"] == status, d["reason"]
    assert d["matched_object"] == matched
    assert reason_part in d["reason"]
    assert 0 <= d["score"] <= 1


def test_scores_rank_sensibly(result):
    dets = result[0]
    assert dets["d1"]["score"] > 0.8                      # close match to JPL
    assert dets["d6"]["score"] > dets["d2"]["score"]      # a real-looking mover beats a one-frame blip
    assert all(dets[k]["score"] <= 0.2 for k in ("d2", "d3", "d4", "d5", "d7"))


def test_motion_filled_and_contract_shaped(result):
    d6 = result[0]["d6"]
    assert d6["motion"]["rate_arcsec_per_hr"] == pytest.approx(5 * SCALE / (0.002 * 24), rel=0.02)  # 5 px per 2.88 min
    assert 0 <= d6["motion"]["pa_deg"] < 360
    assert d6["synthetic"] is True                         # untouched


def test_given_motion_is_kept():
    det = {"id": "x", "track": TARGET["detections"][5]["track"], "motion": {"rate_arcsec_per_hr": 1.0, "pa_deg": 10.0}}
    assert classify_one(det, TARGET)["motion"] == {"rate_arcsec_per_hr": 1.0, "pa_deg": 10.0}


def test_only_detections_and_provenance_change(result):
    t = result[1]
    for key in ("frames", "known_objects", "labels", "image"):
        assert t[key] == TARGET[key]
    assert t["provenance"][-1]["service"] == "detect.classify (T08)"
    assert "'unknown': 1" in t["provenance"][-1]["query"]


def test_no_detections_no_provenance():
    t = copy.deepcopy(TARGET)
    t["detections"] = []
    assert classify_detections(t)["provenance"] == TARGET["provenance"]


def test_unknown_without_jpl_lookup_says_so_and_scores_lower():
    t = copy.deepcopy(TARGET)
    t["provenance"] = []
    d = classify_one(t["detections"][5], t)
    assert d["status"] == "unknown" and "were not looked up" in d["reason"] and d["score"] <= 0.6


@pytest.mark.parametrize("service,looked_up", [
    ("JPL SB Identification (sb_ident, first pass)", True),
    ("IMCCE SkyBoT cone search (geocentric)", True),    # T51: SkyBoT finds the candidates, sb_ident only as fallback
    ("MPC orbit catalogue MPCORB.DAT (local copy; n-body to frame times, T51)", True),
    ("JPL known objects (T07) failed", False),
])
def test_known_object_lookup_counts_for_skybot_too(service, looked_up):
    t = copy.deepcopy(TARGET)
    t["provenance"] = [{"service": service, "query": "q", "retrieved_utc": "z"}]
    d = classify_one(t["detections"][5], t)
    assert ("were not looked up" not in d["reason"]) == looked_up and (d["score"] > 0.6) == looked_up


def test_match_tolerance_edge():
    t = copy.deepcopy(TARGET)
    off = MATCH_PX + 0.5
    det = {"id": "e", "track": [pos("f0", 30 + off, 40), pos("f1", 33 + off, 40), pos("f2", 36 + off, 40)]}
    assert classify_one(det, t)["status"] != "known"
