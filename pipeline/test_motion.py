"""pytest pipeline/test_motion.py: motion summary + class (T23), no network."""
from pipeline.motion import summarize

FRAMES = [{"id": "a", "mjd": 61000.0, "epoch": 1}, {"id": "b", "mjd": 61000.5, "epoch": 1},
          {"id": "c", "mjd": 61180.0, "epoch": 2}, {"id": "d", "mjd": 61365.0, "epoch": 3}]


def track(points):
    return [{"frame_id": f, "ra_deg": ra, "dec_deg": dec, "x": 0, "y": 0} for f, ra, dec in points]


def test_still():
    m = summarize(track([("a", 10, 5), ("c", 10, 5), ("d", 10, 5)]), FRAMES, 6.15)
    assert m["class"] == "still" and m["shift_arcsec"] == 0


def test_proper_motion_north_like_barnard():
    dec_step = 10.4 / 3600  # 10.4" over the year, straight north
    m = summarize(track([("a", 10, 5), ("c", 10, 5 + dec_step / 2), ("d", 10, 5 + dec_step)]), FRAMES, 6.15)
    assert m["class"] == "proper motion" and m["direction"] == "N"
    assert abs(m["rate_arcsec_per_yr"] - 10.4) < 0.1


def test_fast_mover_within_one_epoch():
    m = summarize(track([("a", 10, 5), ("b", 10.01, 5)]), FRAMES, 6.15)  # 36" in 12 h = 3"/h
    assert m["class"] == "fast mover" and m["direction"] == "E"


def test_distant_body_jumps_between_epochs():
    m = summarize(track([("a", 10, 5), ("b", 10, 5), ("c", 10.05, 5), ("d", 10.0, 5)]), FRAMES, 6.15)
    assert m["class"] == "distant body?"


def test_needs_two_positions():
    assert summarize(track([("a", 10, 5)]), FRAMES, 6.15) is None


def test_fast_mover_seen_in_one_burst_two_minutes_apart():
    fr = [{"id": "a", "mjd": 61000.0, "epoch": 1}, {"id": "b", "mjd": 61000.0 + 2 / 1440, "epoch": 1}]
    m = summarize(track([("a", 10, 5), ("b", 10, 5 + 10 / 3600)]), fr, 6.15)  # 10" in 2 min
    assert m["class"] == "fast mover" and m["max_rate_within_epoch_arcsec_per_hr"] > 250


def test_noise_between_close_frames_is_not_motion():
    fr = [{"id": "a", "mjd": 61000.0, "epoch": 1}, {"id": "b", "mjd": 61000.0 + 2 / 1440, "epoch": 1}]
    m = summarize(track([("a", 10, 5), ("b", 10, 5 + 1 / 3600)]), fr, 6.15)  # 1" jitter
    assert m["class"] == "still"
