"""T93: GET /api/targets/<id>/chemistry (job, cache, PNG, map layer)."""
import json
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from pipeline import chemistry
from server.app import create_app


@pytest.fixture
def setup(tmp_path, monkeypatch):
    root = tmp_path / "targets"
    d = root / "c1-p1-s5"
    d.mkdir(parents=True)
    (d / "target.json").write_text(json.dumps({"id": "c1-p1-s5", "synthetic": False, "size_arcmin": 5,
                                               "center": {"ra_deg": 10.0, "dec_deg": 1.0},
                                               "image": {"width": 49, "height": 49, "pixel_scale_arcsec": 6.15},
                                               "frames": [{"id": "f000", "epoch": 1, "mjd": 1.0}]}))

    def fake(target_dir, feature, progress=None, refresh=False):
        progress and progress(1, 1)
        (target_dir / "chemistry").mkdir(exist_ok=True)
        Image.fromarray(np.dstack([np.full((49, 49), 200, np.uint8), np.full((49, 49), 255, np.uint8)]), "LA").save(
            target_dir / "chemistry" / f"{feature}.png")
        stats = {"version": chemistry.VERSION, "feature": feature, "name": "Br-α", "exposures_used": 7}
        (target_dir / "chemistry" / f"{feature}.json").write_text(json.dumps(stats))
        return stats
    monkeypatch.setattr(chemistry, "compute", fake)
    return TestClient(create_app(cache_root=root, fixture=True)), d


def test_features_list(setup):
    c, _ = setup
    ids = [f["id"] for f in c.get("/api/chemistry/features").json()["features"]]
    assert "h2o_ice" in ids and "br_alpha" in ids and "pah" in ids


def test_job_then_cached_then_png_and_layer(setup):
    c, d = setup
    assert c.get("/api/targets/c1-p1-s5/chemistry", params={"feature": "br_alpha"}).json()["status"] == "not_started"
    r = c.get("/api/targets/c1-p1-s5/chemistry", params={"feature": "br_alpha", "start": 1})
    for _ in range(50):
        if r.json()["status"] == "ready":
            break
        time.sleep(0.05)
        r = c.get("/api/targets/c1-p1-s5/chemistry", params={"feature": "br_alpha"})
    body = r.json()
    assert body["status"] == "ready" and body["layer"] == "x-br_alpha" and body["exposures_used"] == 7
    png = c.get("/api/targets/c1-p1-s5/chemistry/br_alpha.png")
    assert png.status_code == 200 and png.headers["content-type"] == "image/png"
    assert c.get("/api/hips/c1-p1-s5/x-br_alpha/properties").status_code == 200
    from astropy_healpix import HEALPix
    import astropy.units as u
    n = int(HEALPix(nside=2 ** 7, order="nested").lonlat_to_healpix(10.0 * u.deg, 1.0 * u.deg))
    tile = c.get(f"/api/hips/c1-p1-s5/x-br_alpha/Norder7/Dir{(n // 10000) * 10000}/Npix{n}.png")
    assert tile.status_code == 200
    a = np.asarray(Image.open(__import__("io").BytesIO(tile.content)).convert("LA"))
    assert a[..., 1].max() == 255 and a[..., 0][a[..., 1] > 0].min() == 200


def test_errors(setup):
    c, _ = setup
    assert c.get("/api/targets/c1-p1-s5/chemistry", params={"feature": "gold"}).status_code == 400
    assert c.get("/api/targets/nope-1/chemistry", params={"feature": "pah"}).status_code == 404
    assert c.get("/api/targets/c1-p1-s5/chemistry/pah.png").status_code == 404
    assert c.get("/api/targets/c1-p1-s5/chemistry/..%2ftarget.json").status_code == 404
