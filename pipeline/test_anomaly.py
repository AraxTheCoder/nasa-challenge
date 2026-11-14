"""T84: spectral anomalies on synthetic spectra (offline; the catalogue check is faked)."""
import numpy as np

from pipeline import anomaly as A


def _spectrum(seed=1, epochs=(1, 2, 3), per_epoch=60, level=None, shape=None, masked=0.0):
    """A smooth star (power law) seen at random wavelengths, 2 % noise; optional changes per epoch."""
    rng = np.random.default_rng(seed)
    frames = []
    for ep in epochs:
        w = np.sort(rng.uniform(0.75, 5.0, per_epoch))
        for k, wl in enumerate(w):
            f = 1000.0 * wl ** -1.5
            if level and ep == level[0]:
                f *= level[1]
            if shape and ep == shape[0] and abs(wl - shape[1]) < 0.15:
                f *= shape[2]
            frames.append({"frame_id": f"e{ep}-{k:03d}", "epoch": ep, "mjd": 60800 + 180 * ep + k * 0.3,
                           "wavelength_um": float(wl), "flux_ujy": float(f * (1 + 0.02 * rng.normal())),
                           "err_ujy": float(0.02 * f), "detector": 1 + int((wl - 0.75) // 0.71),
                           "masked": False, "masked_fraction": masked})
    return {"ra_deg": 10.0, "dec_deg": 20.0, "frames": frames}


def test_steady_star_is_quiet():
    a = A.find_anomalies(_spectrum(), check_known=False)
    assert a["items"] == [] and a["summary"].startswith("Nothing unusual")


def test_spike_burst_found_and_grouped():
    s = _spectrum()
    e2 = [f for f in s["frames"] if f["epoch"] == 2]
    burst = e2[20:24]
    for k, f in enumerate(burst):          # an asteroid passing: four exposures minutes apart, 5x brighter
        f["mjd"] = 61160.0 + k * 0.001
        f["flux_ujy"] *= 5
    a = A.find_anomalies(s, check_known=False)
    sp = [i for i in a["items"] if i["type"] == "spike"]
    assert len(sp) == 1 and sp[0]["n_exposures"] == 4
    assert sorted(sp[0]["frames"]) == sorted(f["frame_id"] for f in burst)


def test_flagged_exposures_are_no_evidence():
    s = _spectrum()
    f = [f for f in s["frames"] if f["epoch"] == 1][30]
    f["flux_ujy"] *= 0.4                   # a filled-in saturated core looks like a dip ...
    f["masked_fraction"] = 0.035           # ... but one pixel of the aperture is flagged
    assert A.find_anomalies(s, check_known=False)["items"] == []


def test_saturated_source_cannot_be_judged():
    a = A.find_anomalies(_spectrum(masked=0.15), check_known=False)
    assert a["items"] == [] and a["summary"].startswith("Can't judge")


def test_level_change_between_epochs():
    a = A.find_anomalies(_spectrum(level=(2, 1.5)), check_known=False)
    lv = {tuple(i["epochs"]): i["change_pct"] for i in a["items"] if i["type"] == "level"}
    assert 40 < lv[(1, 2)] < 60 and -40 < lv[(2, 3)] < -25          # epoch 2 up, then back down


def test_shape_change_between_epochs():
    a = A.find_anomalies(_spectrum(shape=(3, 2.3, 1.8), per_epoch=120), check_known=False)
    sh = [i for i in a["items"] if i["type"] == "shape"]
    assert sh and sh[0]["epochs"] == [2, 3] and abs(sh[0]["wavelength_um"] - 2.3) < 0.3
    assert "×" in sh[0]["reason"]


def test_known_object_named(monkeypatch):
    import detect.mpcorb as mp
    s = _spectrum()
    f = [f for f in s["frames"] if f["epoch"] == 2][10]
    f["flux_ujy"] *= 8
    monkeypatch.setattr(mp, "available", lambda: True)
    monkeypatch.setattr(mp, "find", lambda target, vmag: [{"name": "262 Valda", "positions": [
        {"frame_id": f["frame_id"], "ra_deg": 10.0, "dec_deg": 20.0 + 5 / 3600}]}])
    a = A.find_anomalies(s)
    sp = [i for i in a["items"] if i["type"] == "spike"][0]
    assert sp["known"][0]["name"] == "262 Valda" and "passed through" in sp["reason"]
