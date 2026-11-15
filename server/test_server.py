"""pytest server/  (fixture mode only; no network)."""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from server.app import create_app
from server.coords import CoordError, parse_dec, parse_ra, parse_size, target_id


def test_parse_wise0855_sexagesimal():
    # WISE 0855 from docs/CHALLENGE.md: 08h55m10.831s -7d14m42.53s
    ra, dec = parse_ra("08h55m10.831s"), parse_dec("-7d14m42.53s")
    assert ra == pytest.approx(133.7951292, abs=1e-6)
    assert dec == pytest.approx(-7.2451472, abs=1e-6)
    assert parse_ra("08:55:10.831") == pytest.approx(ra)
    assert parse_dec("-07:14:42.53") == pytest.approx(dec)
    assert parse_ra("133.7951292") == pytest.approx(ra)


@pytest.mark.parametrize("bad", ["", "abc", "-1", "360", "24h00m00s", "12:61:00"])
def test_parse_ra_rejects(bad):
    with pytest.raises(CoordError):
        parse_ra(bad)


def test_parse_dec_and_size_limits():
    with pytest.raises(CoordError):
        parse_dec("91")
    assert parse_size(None) == 15
    assert parse_size("120") == 120             # up to one SPHEREx detector (3.49 deg) since 2026-11-14
    assert parse_size("210") == 210
    with pytest.raises(CoordError):
        parse_size("211")
    with pytest.raises(CoordError):
        parse_size("4")


def test_target_id():
    assert target_id(133.79513, -7.24515, 15) == ("c1337951-m072452-s15", 133.7951, -7.2452)
    assert target_id(0.0, 2.2, 5)[0] == "c0000000-p022000-s5"


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path, fixture=True))


def _wait_ready(client, body):
    for _ in range(100):
        if body["status"] != "building":
            return body
        time.sleep(0.05)
        body = client.get(body["poll_url"]).json()
    raise AssertionError("build did not finish")


def test_fixture_build_then_cache(client):
    r = client.get("/api/target", params={"ra": "08h55m10.831s", "dec": "-7d14m42.53s"})
    assert r.status_code in (200, 202)
    body = _wait_ready(client, r.json())
    assert body == {"status": "ready", "id": "c1337951-m072451-s15",
                    "target_url": "/api/targets/c1337951-m072451-s15/target.json"}

    t = client.get(body["target_url"]).json()
    assert t["id"] == body["id"] and t["synthetic"] is True
    assert t["provenance"][-1]["service"] == "server --fixture"
    img = client.get(f"/api/targets/{t['id']}/{t['frames'][0]['image']}")
    assert img.status_code == 200 and img.content[:4] == b"\x89PNG"

    again = client.get("/api/target", params={"ra": "133.7951", "dec": "-7.2451"})
    assert again.status_code == 200 and again.json()["status"] == "ready"
    assert [x["id"] for x in client.get("/api/targets").json()["targets"]] == [t["id"]]


def test_cors_and_errors(client):
    r = client.get("/api/target", params={"ra": "x", "dec": "0"}, headers={"Origin": "https://a.b"})
    assert r.status_code == 400 and r.json()["status"] == "error"
    assert r.headers["access-control-allow-origin"] == "*"
    assert client.get("/api/jobs/nope").status_code == 404
    assert client.get("/api/targets/..%2f/target.json").status_code == 404
    assert client.get("/api/targets/c1-p1-s5/frames/..%2ftarget.json").status_code == 404


def test_hips_layers_and_tiles(client):
    import astropy.units as u
    from astropy_healpix import HEALPix

    body = _wait_ready(client, client.get("/api/target", params={"ra": "150", "dec": "2.2", "size": "5"}).json())
    t = client.get(body["target_url"]).json()
    h = client.get(f"/api/hips/{t['id']}").json()
    assert h["synthetic"] is True and [l["epoch"] for l in h["layers"]] == sorted({f["epoch"] for f in t["frames"]})
    url = h["layers"][0]["url"]
    props = client.get(f"{url}/properties").text
    assert "hips_order           = 7" in props and "SYNTHETIC" in props
    # the tile containing the field centre has data; one on the other side of the sky doesn't
    c = t["center"]
    for order in (7, 4):
        n = int(HEALPix(nside=2 ** order, order="nested").lonlat_to_healpix(c["ra_deg"] * u.deg, c["dec_deg"] * u.deg))
        r = client.get(f"{url}/Norder{order}/Dir{(n // 10000) * 10000}/Npix{n}.png")
        assert r.status_code == 200 and r.content[:4] == b"\x89PNG"
    far = int(HEALPix(nside=2 ** 7, order="nested").lonlat_to_healpix((c["ra_deg"] + 180) * u.deg, -c["dec_deg"] * u.deg))
    assert client.get(f"{url}/Norder7/Dir0/Npix{far}.png").status_code == 404


def test_hips_pixel_lands_on_field_centre(tmp_path):
    """The tile pixel that maps to the field centre must take its value from the grid centre."""
    import astropy.units as u
    import numpy as np
    from astropy_healpix import HEALPix
    from server import hips

    order = 7
    ra, dec = 150.0, 2.2
    n = int(HEALPix(nside=2 ** order, order="nested").lonlat_to_healpix(ra * u.deg, dec * u.deg))
    sub = int(HEALPix(nside=2 ** (order + 9), order="nested").lonlat_to_healpix(ra * u.deg, dec * u.deg))
    flat = np.nonzero((n * 512 * 512 + hips._XY).ravel() == sub)[0]
    assert len(flat) == 1
    row, col = divmod(int(flat[0]), 512)
    lon, lat = HEALPix(nside=2 ** (order + 9), order="nested").healpix_to_lonlat(n * 512 * 512 + int(hips._XY[row, col]))
    assert abs(lon.to_value(u.deg) - ra) < 3 / 3600 and abs(lat.to_value(u.deg) - dec) < 3 / 3600


def test_labels_on_request(client):
    body = _wait_ready(client, client.get("/api/target", params={"ra": "150", "dec": "2.2", "size": "7"}).json())
    tid = body["id"]
    r = client.get(f"/api/targets/{tid}/labels")
    assert r.status_code in (200, 202)
    for _ in range(100):
        if r.json()["status"] != "building":
            break
        time.sleep(0.05)
        r = client.get(f"/api/targets/{tid}/labels")
    assert r.status_code == 200 and r.json() == {"status": "ready", "n": 0}     # synthetic: no labels
    t = client.get(body["target_url"]).json()
    assert t["labels_requested"] is True and t["labels"] == []
    assert client.get("/api/targets/c9999999-p000000-s5/labels").status_code == 404


def test_sky_cache_serves_from_disk(tmp_path, monkeypatch):
    from server.skycache import SkyCache

    calls = []
    c = SkyCache(tmp_path)
    monkeypatch.setattr(c, "_fetch", lambda s, p: calls.append(p) or (None if "Npix9." in p else b"\x89PNGdata"))
    monkeypatch.setattr(c, "prefetch_around", lambda s, p: None)
    assert SkyCache.valid("spherex-cube", "Norder5/Dir0/Npix1600_1.png")
    assert not SkyCache.valid("spherex-cube", "../secret") and not SkyCache.valid("nope", "properties")
    assert c.get("spherex-cube", "Norder5/Dir0/Npix1600_1.png") == b"\x89PNGdata"
    assert c.get("spherex-cube", "Norder5/Dir0/Npix1600_1.png") == b"\x89PNGdata"
    assert c.get("spherex-cube", "Norder5/Dir0/Npix9.png") is None
    assert c.get("spherex-cube", "Norder5/Dir0/Npix9.png") is None
    assert calls == ["Norder5/Dir0/Npix1600_1.png", "Norder5/Dir0/Npix9.png"]      # each fetched once


def test_epoch_tiles_prerendered(client):
    from server import hips

    body = _wait_ready(client, client.get("/api/target", params={"ra": "150", "dec": "2.2", "size": "6"}).json())
    d = client.app.state.builder.target_dir(body["id"])
    t = client.get(body["target_url"]).json()
    assert hips.tiles_touching(t, 7)
    hips.prerender(d)
    before = hips._tile_cached.cache_info().hits
    n = hips.tiles_touching(t, 7)[0]
    client.get(f"/api/hips/{body['id']}/e1/Norder7/Dir{(n // 10000) * 10000}/Npix{n}.png")
    assert hips._tile_cached.cache_info().hits > before


def test_live_layer_routes_low_orders_to_cube(tmp_path, monkeypatch):
    from server.skycache import SkyCache

    c = SkyCache(tmp_path)
    seen = []
    real_fetch = c._fetch
    monkeypatch.setattr(c, "_fetch", lambda s, p: real_fetch(s, p) if s == "spherex-live" else (
        seen.append((s, p)) or (b"hips_order = 5\nhips_cube_depth = 102\n" if p == "properties" else b"\x89PNG")))
    monkeypatch.setattr(c.tiles, "get", lambda sl, o, n: seen.append(("live", sl, o, n)) or b"\x89PNGlive")
    assert b"hips_order           = 7" in c.get("spherex-live", "properties")
    assert c.get("spherex-live", "Norder5/Dir0/Npix12_20.png") == b"\x89PNG"
    assert c.get("spherex-live", "Norder3/Allsky_20.png") == b"\x89PNG"
    assert c.get("spherex-live", "Norder7/Dir0/Npix123_20.png") == b"\x89PNGlive"
    # T89: live orders ask one slice per detector (20 -> 17 = detector 2); the cube keeps its slice
    assert ("live", 17, 7, 123) in seen and ("spherex-cube", "Norder5/Dir0/Npix12_20.png") in seen


def _poll(client, url):
    r = client.get(url)
    for _ in range(200):
        if r.json()["status"] != "building":
            return r
        time.sleep(0.02)
        r = client.get(url)
    raise AssertionError(f"{url} did not finish")


def test_objects_on_request_fixture(client):
    body = _wait_ready(client, client.get("/api/target", params={"ra": "150", "dec": "2.2", "size": "7"}).json())
    r = _poll(client, f"/api/targets/{body['id']}/objects")
    assert r.status_code == 200 and r.json()["status"] == "ready"   # synthetic: nothing asked of JPL
    assert client.get("/api/targets/c9999999-p000000-s5/objects").status_code == 404


def test_objects_and_labels_jobs_do_not_overwrite_each_other(tmp_path, monkeypatch):
    """T51: real (non-synthetic) target; slow fake JPL while the labels job writes."""
    import json
    import threading

    import detect.run
    import pipeline.labels

    app = create_app(tmp_path)
    client = TestClient(app)
    tid = "c1800000-p000000-s15"
    (tmp_path / tid).mkdir()
    (tmp_path / tid / "target.json").write_text(json.dumps({
        "id": tid, "synthetic": False, "center": {"ra_deg": 180, "dec_deg": 0}, "frames": [],
        "labels": [], "known_objects": [], "detections": [], "provenance": [{"service": "build"}]}))

    jpl_started, labels_done = threading.Event(), threading.Event()

    def fake_detect(t):
        jpl_started.set()
        labels_done.wait(5)
        t["known_objects"] = [{"name": "433 Eros", "source": "jpl-sbident", "synthetic": False, "positions": []}]
        t["provenance"].append({"service": "JPL SB Identification (sb_ident, first pass)"})
        return t

    def fake_labels(t):
        t["labels"] = [{"name": "HD 1"}]
        t["provenance"].append({"service": "SIMBAD"})
        return t

    monkeypatch.setattr(detect.run, "detect_target", fake_detect)
    monkeypatch.setattr(pipeline.labels, "add_labels", fake_labels)
    assert client.get(f"/api/targets/{tid}/objects").status_code == 202
    assert jpl_started.wait(5)
    assert _poll(client, f"/api/targets/{tid}/labels").status_code == 200
    labels_done.set()
    assert _poll(client, f"/api/targets/{tid}/objects").json() == {"status": "ready", "n": 1}
    t = client.get(f"/api/targets/{tid}/target.json").json()
    assert t["labels"] == [{"name": "HD 1"}] and t["labels_requested"] is True
    assert t["known_objects"][0]["name"] == "433 Eros" and t["objects_requested"] is True
    assert [p["service"] for p in t["provenance"]] == ["build", "SIMBAD", "JPL SB Identification (sb_ident, first pass)"]


def test_early_labels_and_objects_land_with_the_build(tmp_path, monkeypatch):
    """T54: labels + known objects run on the stub during the 'download' and are merged onto the
    built frames (a dropped frame loses its positions); /labels and /objects are ready at once."""
    import json
    import threading

    import detect.run
    import pipeline.build
    import pipeline.labels

    stub_done = threading.Event()

    def fake_build(target_id, ra, dec, size, out_root, early=None, **kw):
        stub = {"id": target_id, "synthetic": False, "center": {"ra_deg": ra, "dec_deg": dec},
                "image": {"width": 10, "height": 10, "pixel_scale_arcsec": 6.15},
                "frames": [{"id": f"c00{i}", "mjd": 60000.0 + i, "obs_id": f"o{i}", "detector": 1} for i in range(3)],
                "labels": [], "known_objects": [], "detections": [], "provenance": []}
        early(stub)
        stub_done.wait(5)            # the "download" outlasts the early work
        d = Path(out_root) / target_id
        d.mkdir(parents=True)
        frames = [{"id": "f000", "mjd": 60000.0, "obs_id": "o0", "detector": 1},      # o1 dropped
                  {"id": "f001", "mjd": 60002.0, "obs_id": "o2", "detector": 1}]
        (d / "target.json").write_text(json.dumps({"id": target_id, "synthetic": False, "center": stub["center"],
            "image": stub["image"], "frames": frames, "labels": [], "known_objects": [], "detections": [],
            "provenance": [{"service": "build"}]}))
        return d

    def pos(fid):
        return {"frame_id": fid, "ra_deg": 1.0, "dec_deg": 2.0, "x": 1.0, "y": 2.0}

    def fake_labels(t):
        t["labels"] = [{"id": "l000", "name": "Star", "kind": "star", "otype": "*", "source": "simbad", "named": True,
                        "positions": [pos(f["id"]) for f in t["frames"]]}]
        t["provenance"].append({"service": "SIMBAD"})
        return t

    def fake_detect(t):
        t["known_objects"] = [{"name": "433 Eros", "source": "mpcorb", "synthetic": False, "positions": [pos("c001")]},
                              {"name": "1 Ceres", "source": "mpcorb", "synthetic": False, "positions": [pos("c002")]}]
        t["provenance"].append({"service": "MPC orbit catalogue"})
        stub_done.set()
        return t

    from pathlib import Path
    monkeypatch.setattr(pipeline.build, "build_target", fake_build)
    monkeypatch.setattr(pipeline.labels, "add_labels", fake_labels)
    monkeypatch.setattr(detect.run, "detect_target", fake_detect)
    client = TestClient(create_app(tmp_path))
    body = _wait_ready(client, client.get("/api/target", params={"ra": "180", "dec": "0", "size": "5"}).json())
    t = client.get(body["target_url"]).json()
    assert t["labels_requested"] is True and t["objects_requested"] is True
    assert [p["frame_id"] for p in t["labels"][0]["positions"]] == ["f000", "f001"]
    assert [o["name"] for o in t["known_objects"]] == ["1 Ceres"]          # Eros was only on the dropped frame
    assert t["known_objects"][0]["positions"][0]["frame_id"] == "f001"
    assert [p["service"] for p in t["provenance"]] == ["build", "SIMBAD", "MPC orbit catalogue"]
    assert client.get(f"/api/targets/{body['id']}/objects").json() == {"status": "ready", "n": 1}
    assert client.get(f"/api/targets/{body['id']}/labels").json() == {"status": "ready", "n": 1}


def test_sky_labels_endpoint_caches(tmp_path, monkeypatch):
    import pipeline.labels
    calls = []

    def fake(ra, dec, radius):
        calls.append((ra, dec, radius))
        return {"center": {"ra_deg": ra, "dec_deg": dec}, "radius_deg": radius, "mjd": 61041.0,
                "labels": [{"name": "M 31"}], "provenance": [{"service": "SIMBAD"}]}

    monkeypatch.setattr(pipeline.labels, "sky_labels", fake)
    client = TestClient(create_app(tmp_path / "targets", fixture=True))
    a = client.get("/api/sky-labels", params={"ra": 10.68, "dec": 41.27, "radius": 0.8}).json()
    b = client.get("/api/sky-labels", params={"ra": 10.70, "dec": 41.26, "radius": 0.9}).json()
    assert a == b and len(calls) == 1                     # same grid cell: computed once
    assert a["labels"] == [{"name": "M 31"}] and list((tmp_path / "sky_labels").glob("*.json"))
    assert client.get("/api/sky-labels", params={"ra": 1, "dec": 95}).status_code == 400


def test_photometry_all_exposures_job(tmp_path, monkeypatch):
    """T66: ?all=1 runs in the background (202 with progress), then 200 with every exposure."""
    import json
    import threading

    import pipeline.photometry as ph

    monkeypatch.setattr(ph, "SPECTRA_ROOT", tmp_path / "spectra")
    gate = threading.Event()

    def fake_all(ra, dec, progress=None):
        progress(1, 2)
        gate.wait(5)
        return {"ra_deg": ra, "dec_deg": dec, "frames": [{"frame_id": "o1-D1"}], "all_exposures": True, "n_exposures": 2}

    monkeypatch.setattr(ph, "measure_all", fake_all)
    tid = "c1800000-p000000-s15"
    (tmp_path / tid).mkdir()
    (tmp_path / tid / "target.json").write_text(json.dumps({"id": tid, "synthetic": False,
        "center": {"ra_deg": 180.0, "dec_deg": 0.0}, "frames": []}))
    client = TestClient(create_app(tmp_path))
    url = f"/api/targets/{tid}/photometry"
    r = client.get(url, params={"ra": 180.0, "dec": 0.0, "all": 1})
    for _ in range(50):
        if r.json().get("done"):
            break
        time.sleep(0.02)
        r = client.get(url, params={"ra": 180.0, "dec": 0.0, "all": 1})
    assert r.status_code == 202 and r.json()["status"] == "building" and r.json()["total"] == 2
    gate.set()
    for _ in range(100):
        r = client.get(url, params={"ra": 180.0, "dec": 0.0, "all": 1})
        if r.status_code == 200:
            break
        time.sleep(0.02)
    assert r.status_code == 200 and r.json()["all_exposures"] is True and r.json()["frames"] == [{"frame_id": "o1-D1"}]


def test_photometry_anywhere_no_field_needed(tmp_path, monkeypatch):
    """T79: GET /api/photometry?ra=&dec= measures all exposures at any sky point."""
    import pipeline.photometry as ph
    monkeypatch.setattr(ph, "SPECTRA_ROOT", tmp_path / "spectra")
    monkeypatch.setattr(ph, "measure_all", lambda ra, dec, progress=None: {
        "ra_deg": ra, "dec_deg": dec, "frames": [], "all_exposures": True, "n_exposures": 0})
    client = TestClient(create_app(tmp_path))
    for _ in range(100):
        r = client.get("/api/photometry", params={"ra": 10.5, "dec": -3.25})
        if r.status_code == 200:
            break
        time.sleep(0.02)
    assert r.status_code == 200 and r.json()["ra_deg"] == 10.5 and r.json()["all_exposures"] is True
    assert client.get("/api/photometry", params={"ra": 400, "dec": 0}).status_code == 400


def test_hips_frame_and_difference_layers(client):
    """T81: one layer per frame and A − B layers, same URL scheme as the epochs."""
    import io

    import astropy.units as u
    import numpy as np
    from astropy_healpix import HEALPix
    from PIL import Image

    body = _wait_ready(client, client.get("/api/target", params={"ra": "150", "dec": "2.2", "size": "5"}).json())
    t = client.get(body["target_url"]).json()
    h = client.get(f"/api/hips/{t['id']}").json()
    assert [l["frame_id"] for l in h["frame_layers"]] == [f["id"] for f in sorted(t["frames"], key=lambda f: f["mjd"])]
    a, b = h["frame_layers"][0]["frame_id"], h["frame_layers"][-1]["frame_id"]
    c = t["center"]
    n = int(HEALPix(nside=2 ** 7, order="nested").lonlat_to_healpix(c["ra_deg"] * u.deg, c["dec_deg"] * u.deg))
    for layer in (a, f"d-{a}-{b}", f"d-{a}-{a}"):
        assert "frame" in client.get(f"/api/hips/{t['id']}/{layer}/properties").text or layer.startswith("d-")
        r = client.get(f"/api/hips/{t['id']}/{layer}/Norder7/Dir{(n // 10000) * 10000}/Npix{n}.png")
        assert r.status_code == 200 and r.content[:4] == b"\x89PNG", layer
    same = np.asarray(Image.open(io.BytesIO(r.content)).convert("LA"))       # A − A: everything grey 128
    grey = same[..., 0][same[..., 1] > 0]
    assert grey.size and abs(float(np.median(grey)) - 128) <= 1
    assert client.get(f"/api/hips/{t['id']}/f999/properties").status_code == 404
    assert client.get(f"/api/hips/{t['id']}/x1/properties").status_code == 404


def test_spectral_outliers_job(tmp_path, monkeypatch):
    """T85/T86: not_started -> start=1 (202 while measuring) -> 200 with the ranked outliers; spectra seeded."""
    import json

    import numpy as np

    import pipeline.fieldspectra as FS
    import pipeline.photometry as ph
    from pipeline.test_fieldspectra import _field

    monkeypatch.setattr(FS, "ROOT", tmp_path / "fs")
    monkeypatch.setattr(ph, "SPECTRA_ROOT", tmp_path / "spectra")
    tid = "c0100000-p200000-s15"
    labels = [{"id": f"s{i}", "name": f"star {i}", "source": "gaia_dr3", "mag": 12.0,
               "positions": [{"frame_id": "f0", "ra_deg": 10 + i * 0.01, "dec_deg": 20.0}]} for i in range(60)]
    target = {"id": tid, "synthetic": False, "center": {"ra_deg": 10.0, "dec_deg": 20.0}, "size_arcmin": 15,
              "frames": [{"id": "f0", "mjd": 60800.0}], "labels": labels}
    (tmp_path / tid).mkdir()
    (tmp_path / tid / "target.json").write_text(json.dumps(target))

    def fake_measure(t, progress=None, **kw):
        progress(3, 3)
        fs = _field(odd={5: lambda w: 1 + 0.8 * np.clip((w - 2.8) / 2.0, 0, None)})
        srcs = FS.sources_of(t)
        fs.update(version=FS.VERSION, target_id=t["id"], sources=srcs, sources_key=FS._key(srcs), missing=[], seconds=1.0)
        FS._write(FS.cache_path(t["id"]), fs)
        return fs

    monkeypatch.setattr(FS, "measure_field", fake_measure)
    client = TestClient(create_app(tmp_path))
    url = f"/api/targets/{tid}/spectral-outliers"
    assert client.get(url).json()["status"] == "not_started"
    r = client.get(url, params={"start": 1})
    for _ in range(500):                            # up to 10 s: background job under a loaded machine
        if r.status_code == 200:
            break
        time.sleep(0.02)
        r = client.get(url)
    body = r.json()
    assert r.status_code == 200 and body["status"] == "ready" and body["items"][0]["name"] == "star 5"
    assert body["field"]["n_sources"] == 60 and "flux_ujy" not in body
    assert len(list((tmp_path / "spectra").glob("*.json"))) == 60          # clicks on these sources are instant


def test_hips_epoch_layers_per_detector_and_false_colour(tmp_path):
    """T89: e<ep>d<n> = one detector's frames of the epoch, e<ep>c = false colour of all of them."""
    import json as _json

    import numpy as np
    from PIL import Image

    from server import hips

    d = tmp_path / "t"
    d.mkdir()
    frames = []
    for i, det in enumerate((1, 3, 5)):
        Image.fromarray(np.dstack([np.full((8, 8), 50 * (i + 1), np.uint8), np.full((8, 8), 255, np.uint8)]), "LA").save(d / f"f{i}.png")
        frames.append({"id": f"f00{i}", "epoch": 1, "detector": det, "image": f"f{i}.png", "mjd": 1.0 + i,
                       "time_utc": "2025-06-01T00:00:00"})
    t = {"center": {"ra_deg": 10.0, "dec_deg": 0.0}, "size_arcmin": 1, "frames": frames,
         "image": {"width": 8, "height": 8, "pixel_scale_arcsec": 6.15}}
    (d / "target.json").write_text(_json.dumps(t), encoding="utf-8")
    assert hips.has_layer(t, "e1d3") and not hips.has_layer(t, "e1d2") and hips.has_layer(t, "e1c")
    m = (d / "target.json").stat().st_mtime
    mean, cov = hips.epoch_image(str(d), m, 1, 3)
    assert mean[0, 0] == 100 and cov.all()
    rgb, cov = hips.colour_image(str(d), m, 1)
    assert tuple(rgb[0, 0]) == (150, 100, 50)            # R = D5, G = D3, B = D1 (their pairs have no D6/D4/D2)
    assert hips.layers("x", t)[0]["detectors"] == [1, 3, 5]
    import re
    assert re.match(hips.LAYER_RE, "e1c") and re.match(hips.LAYER_RE, "e12d6") and not re.match(hips.LAYER_RE, "e1d7")


def test_target_request_for_one_detector(tmp_path):
    from fastapi.testclient import TestClient

    from server.app import create_app as api

    c = TestClient(api(tmp_path / "targets", fixture=True))
    r = c.get("/api/target?ra=10&dec=5&size=20&detector=3")
    assert r.json()["id"].endswith("-d3")
    assert c.get("/api/target?ra=10&dec=5&size=20&detector=9").status_code == 400


def test_motion_endpoint(tmp_path, monkeypatch):
    """T91: start=0 only reads; the default starts a job (202) and answers the measured motion (200)."""
    import json

    import pipeline.astrometry as AS

    monkeypatch.setattr(AS, "ROOT", tmp_path / "motion")
    tid = "c0100000-p200000-s15"
    target = {"id": tid, "synthetic": False, "center": {"ra_deg": 10.0, "dec_deg": 20.0}, "size_arcmin": 15,
              "frames": [{"id": "f0", "mjd": 60800.0}],
              "labels": [{"id": "l0", "name": "Fast Star", "source": "simbad", "mag": 9.0, "pm_mas_yr": 5000,
                          "positions": [{"frame_id": "f0", "ra_deg": 10.0, "dec_deg": 20.0}]}]}
    (tmp_path / tid).mkdir()
    (tmp_path / tid / "target.json").write_text(json.dumps(target))

    def fake(t, name, processes=None, progress=None):
        progress(1, 1)
        return {"version": AS.VERSION, "status": "ready", "id": "l0", "name": "Fast Star", "pm_total_arcsec_yr": 5.01}

    monkeypatch.setattr(AS, "measure_motion_uncached", fake)
    client = TestClient(create_app(tmp_path))
    url = f"/api/targets/{tid}/motion"
    assert client.get(url, params={"name": "Fast Star", "start": 0}).json()["status"] == "not_started"
    r = client.get(url, params={"name": "Fast Star"})
    for _ in range(500):                            # up to 10 s: background job under a loaded machine
        if r.status_code == 200:
            break
        time.sleep(0.02)
        r = client.get(url, params={"name": "l0", "start": 0})
    assert r.status_code == 200 and r.json()["pm_total_arcsec_yr"] == 5.01 and r.json()["target_id"] == tid
    assert client.get(url, params={"name": "Nobody"}).status_code == 404
    by_pos = client.get(url, params={"ra": 10.0 + 3 / 3600, "dec": 20.0, "start": 0}).json()
    assert by_pos["status"] == "ready" and by_pos["name"] == "Fast Star"          # the moving star at that spot
    r = client.get(url, params={"ra": 10.1, "dec": 20.0, "start": 0})
    assert r.status_code == 404 and r.json()["status"] == "none"


def test_hips_colour_and_detector_epoch_layers_over_http(client):
    """T94: /api/hips/<id>/e1c and /e1d<n> are layers (the epoch route took "1c" for a number: 422)."""
    import astropy.units as u
    from astropy_healpix import HEALPix

    body = _wait_ready(client, client.get("/api/target", params={"ra": "150", "dec": "2.2", "size": "5"}).json())
    t = client.get(body["target_url"]).json()
    tid = t["id"]
    dets = sorted({int(f["detector"]) for f in t["frames"] if int(f["epoch"]) == 1 and f.get("detector")})
    for layer in ["e1c"] + ([f"e1d{dets[0]}"] if dets else []):
        r = client.get(f"/api/hips/{tid}/{layer}/properties")
        assert r.status_code == 200, (layer, r.status_code)
    c = t["center"]
    npix = int(HEALPix(nside=2 ** 7, order="nested").lonlat_to_healpix(c["ra_deg"] * u.deg, c["dec_deg"] * u.deg))
    r = client.get(f"/api/hips/{tid}/e1c/Norder7/Dir{(npix // 10000) * 10000}/Npix{npix}.png")
    assert r.status_code == 200 and r.content[:4] == b"\x89PNG"
    assert client.get(f"/api/hips/{tid}/e1x/properties").status_code == 404
    assert client.get(f"/api/hips/{tid}/e1/properties").status_code == 200
