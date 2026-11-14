"""Offline tests for detect.known_check (T09) on the committed demo-epochs fixture (synthetic)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np

from detect import known_check as kc

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "targets" / "demo-epochs"


def test_peak_near_finds_a_blob_and_centroids_it():
    img = np.zeros((40, 40))
    yy, xx = np.mgrid[0:40, 0:40]
    img += 10 * np.exp(-((xx - 20.3) ** 2 + (yy - 15.6) ** 2) / 2)
    px, py, pk = kc.peak_near(img, 21.0, 16.0)
    assert abs(px - 20.3) < 0.3 and abs(py - 15.6) < 0.3 and pk > 5
    assert kc.peak_near(np.full((10, 10), np.nan), 5, 5) is None


def test_load_frame_no_data_is_nan():
    img = kc.load_frame(FIXTURE / "frames" / "f000.png")
    assert np.isnan(img).any() and np.isfinite(img).any()   # demo-epochs has a no-data corner


def _target(tmp_path, monkeypatch, asteroid_flux):
    """demo-epochs with its known asteroid A treated as real, photometry stubbed."""
    d = tmp_path / "demo-epochs"
    shutil.copytree(FIXTURE, d)
    t = json.loads((d / "target.json").read_text())
    t["known_objects"] = [k for k in t["known_objects"] if "asteroid A" in k["name"]]
    t["known_objects"][0]["synthetic"] = False
    (d / "target.json").write_text(json.dumps(t))
    on = {p["frame_id"] for p in t["known_objects"][0]["positions"]}

    def fake_measure(target, ra, dec, raw_root=None):
        near = any(abs(p["ra_deg"] - ra) < 1e-4 and abs(p["dec_deg"] - dec) < 1e-4 for p in t["known_objects"][0]["positions"])
        return {"frames": [{"frame_id": f["id"], "masked": False, "wavelength_um": f["wavelength_um"],
                            "flux_ujy": (asteroid_flux if near and f["id"] in on else 0.0) + 100.0 + (i % 3), "err_ujy": 20.0}
                           for i, f in enumerate(target["frames"])]}
    monkeypatch.setattr("pipeline.photometry.measure", fake_measure)
    return d


def test_known_asteroid_is_recovered_with_small_offset(tmp_path, monkeypatch):
    res = kc.check_target(_target(tmp_path, monkeypatch, 1000.0), mags=False)
    rows = res["rows"]
    assert len(rows) == 4 and all(r["recovered"] for r in rows), rows
    assert max(r["offset_px"] for r in rows) < 1.0 and min(r["sn"] for r in rows) > 20
    s = kc.summary([res])
    assert s["objects_recovered"] == 1 and s["recovered"] == 4 and s["controls_recovered"] == 0


def test_too_faint_is_not_recovered(tmp_path, monkeypatch):
    res = kc.check_target(_target(tmp_path, monkeypatch, 10.0), mags=False)   # S/N < 1
    assert not any(r["recovered"] for r in res["rows"])
