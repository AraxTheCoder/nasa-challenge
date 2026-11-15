"""T06: mover detection on made-up images (no network, no files)."""
import numpy as np
from astropy.wcs import WCS

from detect import movers
from detect.classify import classify_one

N = 80


def _wcs(shift=0.0):
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [150.0, 2.0]
    w.wcs.crpix = [N / 2 + shift, N / 2 - shift]        # every image points a little differently
    w.wcs.cdelt = [-6.15 / 3600, 6.15 / 3600]
    return w


STARS = [(150.010, 2.012, 400.0), (149.985, 1.990, 250.0), (150.020, 1.980, 120.0)]
MOVER = (149.998, 2.000, 150.0)


def _image(rng, w, extra=()):
    img = rng.normal(0.0, 1.0, (N, N))
    yy, xx = np.mgrid[0:N, 0:N]
    for ra, dec, flux in [*STARS, *extra]:
        x, y = w.all_world2pix(ra, dec, 0)
        img += flux / (2 * np.pi) * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / 2)
    return img


def _field(mover_in=("f04", "f05"), ray_in="f06"):
    """6 moments x 2 detectors (1 and 4); the mover is in both images of the third moment, a cosmic ray in one."""
    rng = np.random.default_rng(6)
    frames, loaded = [], {}
    for k in range(12):
        fid = f"f{k:02d}"
        frames.append({"id": fid, "mjd": 61000.0 + 3.0 * (k // 2), "detector": 1 if k % 2 == 0 else 4})
        w = _wcs(shift=1.7 * (k // 2))
        img = _image(rng, w, [MOVER] if fid in mover_in else [])
        if fid == ray_in:
            img[62, 14] += 80.0
        sn, sub, bad = movers.sn_map(img, np.ones((N, N)), np.zeros((N, N), bool))
        loaded[fid] = {"sn": sn, "img": sub, "bad": bad, "wcs": w}
    return frames, loaded


def test_noise_has_unit_scatter_and_stars_stand_out():
    frames, loaded = _field()
    sn = loaded["f00"]["sn"]
    assert 0.8 < np.std(sn[sn < 4]) < 1.2
    assert len(movers.sightings(loaded["f00"])) == 3


def test_finds_what_is_there_at_one_moment_in_both_detectors():
    frames, loaded = _field()
    groups, counts = movers.find(frames, loaded)
    assert len(groups) == 1 and [s["frame_id"] for s in groups[0]] == ["f04", "f05"]
    s = groups[0][0]
    assert abs(s["ra"] - MOVER[0]) * 3600 < 3 and abs(s["dec"] - MOVER[1]) * 3600 < 3      # within half a pixel
    assert s["refs"] == 5                                                                 # the 5 other moments
    assert counts["confirmed"] == 2                                 # the mover in each detector; not the cosmic ray
    assert counts["also_there_at_other_times"] >= 30                                      # the stars, every image


def test_one_detector_alone_is_not_a_detection():
    frames, loaded = _field(mover_in=("f04",))
    assert movers.find(frames, loaded)[0] == []


def test_without_references_nothing_is_claimed():
    frames, loaded = _field()
    keep = {"f04", "f05", "f06", "f07"}                  # one other moment only: fewer than MIN_REFS references
    groups, counts = movers.find([f for f in frames if f["id"] in keep], {k: v for k, v in loaded.items() if k in keep})
    assert groups == [] and counts["no_reference"] >= 1


def test_sightings_hours_apart_become_one_track():
    frames, loaded = _field()
    rng = np.random.default_rng(7)
    for k, fid in enumerate(("f12", "f13")):             # 3 h after the third moment, moved 60" (20"/h)
        frames.append({"id": fid, "mjd": 61006.0 + 3 / 24, "detector": 1 + 3 * k})
        w = _wcs(shift=9.0)
        img = _image(rng, w, [(MOVER[0] + 60 / 3600, MOVER[1], MOVER[2])])
        sn, sub, bad = movers.sn_map(img, np.ones((N, N)), np.zeros((N, N), bool))
        loaded[fid] = {"sn": sn, "img": sub, "bad": bad, "wcs": w}
    groups, _ = movers.find(frames, loaded)
    assert len(groups) == 1 and [s["frame_id"] for s in groups[0]] == ["f04", "f05", "f12", "f13"]


def test_classified_as_unknown_with_a_plain_reason():
    target = {"frames": [{"id": "f04", "mjd": 61006.0, "epoch": 1}, {"id": "f05", "mjd": 61006.0, "epoch": 1}],
              "image": {"width": 80, "height": 80, "pixel_scale_arcsec": 6.15}, "known_objects": [], "labels": [],
              "provenance": []}
    det = {"id": "d001", "track": [{"frame_id": "f04", "ra_deg": 150.0, "dec_deg": 2.0, "x": 40.0, "y": 40.0},
                                   {"frame_id": "f05", "ra_deg": 150.0, "dec_deg": 2.0, "x": 40.0, "y": 40.0}],
           "evidence": {"moments": 1, "images": 2, "absent_in": 5, "sn": 30.0}}
    out = classify_one(det, target)
    assert out["status"] == "unknown" and "not there in 5 images" in out["reason"] and 0.3 < out["score"] < 0.7
    assert classify_one({**det, "evidence": None}, target)["status"] == "artifact"      # without the evidence: still


# T67: follows the detector, not the sky

def _frame(rng, w, spots=(), off=(0.0, 0.0)):
    """One loaded image; spots: (x, y, flux) in cutout pixels."""
    img = rng.normal(0.0, 1.0, (N, N))
    yy, xx = np.mgrid[0:N, 0:N]
    for x, y, flux in spots:
        img += flux / (2 * np.pi) * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / 2)
    sn, sub, bad = movers.sn_map(img, np.ones((N, N)), np.zeros((N, N), bool))
    return {"sn": sn, "img": sub, "bad": bad, "wcs": w, "off": off}


def _pixel_case(g_spot, twin_spot=None, hours=-1.0):
    """f: sighting at cutout pixel (40, 40) of detector 1. g: detector 1, `hours` later (negative = earlier),
    pointing 10 px elsewhere but with the same detector offset, so its (40, 40) is the same detector pixel.
    h: detector 4 at g's moment."""
    rng = np.random.default_rng(67)
    wf, wg = _wcs(), _wcs(shift=10.0)
    loaded = {"f": _frame(rng, wf, [(40, 40, 120.0)]), "g": _frame(rng, wg, [g_spot] if g_spot else [])}
    frames = [{"id": "f", "mjd": 61000.0, "detector": 1}, {"id": "g", "mjd": 61000.0 + hours / 24, "detector": 1}]
    sky = wg.all_pix2world([40], [40], 0)
    hx, hy = (float(v[0]) for v in wg.all_world2pix(sky[0], sky[1], 0))
    loaded["h"] = _frame(rng, wg, [(hx, hy, twin_spot)] if twin_spot else [])
    frames.append({"id": "h", "mjd": frames[1]["mjd"], "detector": 4})
    ra, dec = (float(v[0]) for v in wf.all_pix2world([40], [40], 0))
    return movers.same_pixel(frames[0], ra, dec, 8.0, frames, loaded)


def test_afterglow_of_an_earlier_bright_source_on_the_same_pixel():
    assert _pixel_case((40, 40, 20000.0), twin_spot=20000.0) == {"looked": 1, "lit": 0, "persist": 1}


def test_pixel_lit_in_one_detector_only_is_a_hot_pixel():
    assert _pixel_case((40, 40, 60.0), hours=30.0) == {"looked": 1, "lit": 1, "persist": 0}


def test_a_real_star_on_that_pixel_elsewhere_in_the_sky_does_not_count():
    assert _pixel_case((40, 40, 60.0), twin_spot=60.0, hours=30.0) == {"looked": 1, "lit": 0, "persist": 0}


def test_nothing_on_that_pixel_elsewhere():
    assert _pixel_case(None, hours=30.0) == {"looked": 1, "lit": 0, "persist": 0}


def test_classify_calls_detector_followers_artifacts():
    target = {"frames": [{"id": "f04", "mjd": 61006.0, "epoch": 1}, {"id": "f05", "mjd": 61006.0, "epoch": 1}],
              "image": {"pixel_scale_arcsec": 6.15}, "known_objects": [], "provenance": []}
    track = [{"frame_id": "f04", "ra_deg": 1, "dec_deg": 1, "x": 5, "y": 5},
             {"frame_id": "f05", "ra_deg": 1, "dec_deg": 1, "x": 5, "y": 5}]
    ev = {"moments": 1, "images": 2, "absent_in": 3, "sn": 9.0}
    hot = classify_one({"id": "d1", "track": track, "evidence": {**ev, "same_pixel": {"looked": 2, "lit": 1, "persist": 0}}}, target)
    glow = classify_one({"id": "d2", "track": track, "evidence": {**ev, "same_pixel": {"looked": 1, "lit": 0, "persist": 1}}}, target)
    real = classify_one({"id": "d3", "track": track, "evidence": {**ev, "same_pixel": {"looked": 3, "lit": 1, "persist": 0}}}, target)
    assert hot["status"] == "artifact" and "hot pixel" in hot["reason"]
    assert glow["status"] == "artifact" and "afterglow" in glow["reason"]
    assert real["status"] == "unknown"        # 1 of 3: more likely a chance coincidence
