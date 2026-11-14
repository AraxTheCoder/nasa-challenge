"""pytest pipeline/test_pairs.py (T17), no network."""
from pipeline.pairs import find_pairs


def f(i, ep, wave, det=1, bw=0.03, mjd=None):
    return {"id": i, "epoch": ep, "wavelength_um": wave, "bandwidth_um": bw, "detector": det,
            "mjd": mjd if mjd is not None else 61000 + ep * 180}


def test_closest_match_within_half_a_channel():
    fr = [f("a1", 1, 1.100), f("a2", 1, 1.130), f("b1", 2, 1.101), f("b2", 2, 1.160)]
    p = find_pairs(fr)
    assert [(x["a"], x["b"]) for x in p] == [("a1", "b1")]  # a2-b2 differ by 0.03 > 0.5 * 0.03
    assert p[0]["dwave_um"] == 0.001 and p[0]["dt_days"] == 180


def test_same_epoch_or_other_detector_never_pairs():
    fr = [f("a", 1, 1.1), f("b", 1, 1.1), f("c", 2, 1.1, det=2)]
    assert find_pairs(fr) == []


def test_each_frame_once_per_other_epoch_and_earlier_is_a():
    fr = [f("x", 2, 1.2, mjd=61400), f("y", 1, 1.2, mjd=61200), f("z", 1, 1.2005, mjd=61201)]
    p = find_pairs(fr)
    assert len(p) == 1 and p[0]["a"] == "y" and p[0]["b"] == "x"


def test_frames_without_bandwidth_are_skipped():
    fr = [f("a", 1, 1.1, bw=None), f("b", 2, 1.1)]
    assert find_pairs(fr) == []
