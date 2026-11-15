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

    def fake(target_dir, feature, progress=None, refresh=False, z=0.0):
        progress and progress(1, 1)
        key = chemistry.map_key(feature, z)
        (target_dir / "chemistry").mkdir(exist_ok=True)
        Image.fromarray(np.dstack([np.full((49, 49), 200, np.uint8), np.full((49, 49), 255, np.uint8)]), "LA").save(
            target_dir / "chemistry" / f"{key}.png")
        stats = {"version": chemistry.VERSION, "feature": feature, "key": key, "z": z, "name": "Br-α", "exposures_used": 7}
        (target_dir / "chemistry" / f"{key}.json").write_text(json.dumps(stats))
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


# --- T96: 2-3 maps as one colour picture ---

def _tile(c, layer):
    from astropy_healpix import HEALPix
    import astropy.units as u
    n = int(HEALPix(nside=2 ** 7, order="nested").lonlat_to_healpix(10.0 * u.deg, 1.0 * u.deg))
    return c.get(f"/api/hips/c1-p1-s5/{layer}/Norder7/Dir{(n // 10000) * 10000}/Npix{n}.png")


def _grey(d, feature, value):
    (d / "chemistry").mkdir(exist_ok=True)
    Image.fromarray(np.dstack([np.full((49, 49), value, np.uint8), np.full((49, 49), 255, np.uint8)]), "LA").save(
        d / "chemistry" / f"{feature}.png")


def test_features_say_direction_and_colours(setup):
    c, _ = setup
    body = c.get("/api/chemistry/features").json()
    shows = {f["id"]: f["shows"] for f in body["features"]}
    assert shows["br_alpha"] == "emission" and shows["h2o_ice"] == "absorption"
    cols = body["combine"]["colours"]                                   # T108: any number, 2 and 3 as in T96
    assert body["combine"]["max"] == len(shows) and cols["2"] == ["#00ffff", "#ff0000"]
    assert cols["3"] == ["#0000ff", "#00ff00", "#ff0000"] and len(cols[str(len(shows))]) == len(shows)
    known = set(shows)                                                  # T107: presets use only listed features
    assert body["presets"] and all(set(p["features"]) <= known and p["try"]["name"] for p in body["presets"])


def test_combined_png_and_layer(setup):
    import io
    c, d = setup
    _grey(d, "br_alpha", 255)                       # Br-α (4.05 µm): strong emission -> red
    _grey(d, "h2o_ice", 0)                          # H₂O ice (3.05 µm): deep absorption -> cyan (shorter)
    png = c.get("/api/targets/c1-p1-s5/chemistry/h2o_ice-br_alpha.png")
    assert png.status_code == 200 and png.headers["content-type"] == "image/png"
    a = np.asarray(Image.open(io.BytesIO(png.content)).convert("RGBA"))
    assert tuple(a[20, 20]) == (255, 255, 255, 255)                     # both: white
    assert c.get("/api/hips/c1-p1-s5/x-h2o_ice-br_alpha/properties").status_code == 200
    t = _tile(c, "x-h2o_ice-br_alpha")
    assert t.status_code == 200
    rgba = np.asarray(Image.open(io.BytesIO(t.content)).convert("RGBA"))
    inside = rgba[..., 3] > 0
    assert inside.any() and (rgba[inside][:, :3] == 255).all()
    _grey(d, "br_alpha", 128)                       # remade (another version): the tiles follow, not cached
    t = _tile(c, "x-h2o_ice-br_alpha")
    rgba = np.asarray(Image.open(io.BytesIO(t.content)).convert("RGBA"))
    assert (rgba[rgba[..., 3] > 0][:, :3] == (0, 255, 255)).all()       # ice only: cyan


def test_combined_errors(setup):
    c, d = setup
    _grey(d, "br_alpha", 255)
    assert c.get("/api/targets/c1-p1-s5/chemistry/h2o_ice-br_alpha.png").status_code == 404   # ice not made
    _grey(d, "h2o_ice", 0)
    assert c.get("/api/targets/c1-p1-s5/chemistry/br_alpha-gold.png").status_code == 404
    assert c.get("/api/hips/c1-p1-s5/x-br_alpha-h2o_ice/properties").status_code == 404      # not in wavelength order
    assert c.get("/api/hips/c1-p1-s5/x-pa_beta-br_gamma-pah-pah/properties").status_code == 404   # twice the same


def test_more_than_three_features(setup):
    """T108: four maps in one picture; each feature its own hue, blue (shortest) to red (longest)."""
    import io
    from PIL import Image
    c, d = setup
    for f in ("pa_beta", "br_gamma", "pah", "br_alpha"):          # all four emit strongly everywhere
        _grey(d, f, 255)
    r = c.get("/api/targets/c1-p1-s5/chemistry/pa_beta-br_gamma-pah-br_alpha.png")
    assert r.status_code == 200
    rgba = np.asarray(Image.open(io.BytesIO(r.content)).convert("RGBA"))
    assert (rgba[rgba[..., 3] > 0][:, :3] == 255).all()           # all of them: white
    assert c.get("/api/hips/c1-p1-s5/x-pa_beta-br_gamma-pah-br_alpha/properties").status_code == 200


def test_redshifted_map_and_picture(setup):
    """T109: ?z= makes the map at a redshift under its own key; a picture takes maps of one z only."""
    c, d = setup
    url = "/api/targets/c1-p1-s5/chemistry"
    r = c.get(url, params={"feature": "br_alpha", "z": 0.00524, "start": 1})
    for _ in range(200):
        if r.status_code == 200:
            break
        time.sleep(0.02)
        r = c.get(url, params={"feature": "br_alpha", "z": 0.00524})
    body = r.json()
    assert body["status"] == "ready" and body["key"] == "br_alpha_z52" and body["layer"] == "x-br_alpha_z52"
    assert (d / "chemistry" / "br_alpha_z52.png").is_file() and not (d / "chemistry" / "br_alpha.png").exists()
    assert c.get(f"{url}/br_alpha_z52.png").status_code == 200
    assert c.get("/api/hips/c1-p1-s5/x-br_alpha_z52/properties").status_code == 200
    assert c.get(url, params={"feature": "br_alpha", "z": -0.5}).status_code == 400
    _grey(d, "pah_z52", 255)
    assert c.get(f"{url}/pah_z52-br_alpha_z52.png").status_code == 200
    _grey(d, "pah", 255)
    assert c.get(f"{url}/pah-br_alpha_z52.png").status_code == 404                    # two redshifts in one picture
