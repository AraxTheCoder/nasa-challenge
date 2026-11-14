"""T64: GET /api/targets/<id>/updates and the release fields of a build (CONTRACTS v0.17 "Newer data")."""
import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from pipeline import build
from pipeline.query import Exposure
from server.app import create_app
from server.updates import compare


def _utc(mjd):
    return (datetime(1858, 11, 17) + timedelta(days=mjd)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _exp(i, mjd, epoch, coll="spherex_dr1"):
    return Exposure(obs_id=f"2026W01_1A_{i:04d}_1", collection=coll, detector=1, mjd_start=mjd - 0.001, mjd_mid=mjd,
                    time_utc=_utc(mjd), exptime_s=100, wave_min_um=0.75,
                    wave_max_um=1.1, epoch=epoch, fits_url="u", publisher_did="d")


OLD = [_exp(0, 61041.0, 1), _exp(1, 61042.0, 1), _exp(2, 61043.0, 1)]
PROV = {"service": "local SPHEREx image index", "query": "q", "retrieved_utc": "2026-11-14T00:00:00Z"}


def _target(with_summary=True, frames_coll=True):
    frames = [{"id": "f000", "mjd": 61041.0, "epoch": 1, **({"collection": "spherex_dr1"} if frames_coll else {})},
              {"id": "f001", "mjd": 61042.0, "epoch": 1, **({"collection": "spherex_dr1"} if frames_coll else {})}]
    t = {"id": "c1-p1-s5", "synthetic": False, "center": {"ra_deg": 10.0, "dec_deg": 1.0}, "frames": frames}
    if with_summary:
        t["source_exposures"] = build.exposure_summary(OLD, PROV)
    return t


def test_release_name_and_summary():
    assert build.release_name("spherex_qr3_deep") == "QR3 deep" and build.release_name("spherex_dr1") == "DR1"
    assert build.release_name(None) is None
    s = build.exposure_summary(OLD, PROV)
    assert s == {"count": 3, "latest_mjd": 61043.0, "latest_utc": _utc(61043.0),
                 "collections": ["spherex_dr1"], "checked_utc": "2026-11-14T00:00:00Z"}


def test_up_to_date():
    r = compare(_target(), OLD, PROV)
    assert r["newer_images"] == 0 and r["basis"] == "build" and r["message"].startswith("Up to date")
    assert r["releases_built"] == r["releases_now"] == ["DR1"]


def test_newer_images_new_pass_new_release():
    now = OLD + [_exp(3, 61043.5, 1), _exp(4, 61230.0, 2, "spherex_qr3"), _exp(5, 61231.0, 2, "spherex_qr3_deep")]
    r = compare(_target(), now, PROV)
    assert r["newer_images"] == 3 and r["new_passes"] == 1 and r["new_collections"] == ["spherex_qr3", "spherex_qr3_deep"]
    assert r["releases_now"] == ["DR1", "QR3"]
    assert r["message"] == (f"3 newer SPHEREx images here ({_utc(61043.5)[:10]} to {_utc(61231.0)[:10]}; 1 new survey pass; "
                            "new release QR3). Rebuild to include them.")


def test_old_build_without_summary_counts_only_a_new_pass():
    now = OLD + [_exp(3, 61043.5, 1), _exp(4, 61230.0, 2)]
    r = compare(_target(with_summary=False, frames_coll=False), now, PROV)
    assert r["basis"] == "frames" and r["newer_images"] == 1 and r["new_passes"] == 1 and r["new_collections"] == []


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(cache_root=tmp_path / "targets", fixture=True)), tmp_path / "targets"


def test_route(client, monkeypatch):
    c, root = client
    (root / "c1-p1-s5").mkdir(parents=True)
    (root / "c1-p1-s5" / "target.json").write_text(json.dumps(_target()))
    seen = {}
    def fake(ra, dec, refresh=False, **kw):
        seen["pos"] = (ra, dec)
        return OLD + [_exp(4, 61230.0, 2, "spherex_qr3")], PROV
    monkeypatch.setattr(build, "cached_exposures", fake)
    body = c.get("/api/targets/c1-p1-s5/updates").json()
    assert body["status"] == "ready" and body["newer_images"] == 1 and seen["pos"] == (10.0, 1.0)
    assert body["checked"] == PROV
    assert c.get("/api/targets/nope-1/updates").status_code == 404
    assert c.get("/api/targets/..%2f/updates").status_code == 404
    (root / "syn").mkdir()
    (root / "syn" / "target.json").write_text(json.dumps({**_target(), "synthetic": True}))
    assert c.get("/api/targets/syn/updates").json()["status"] == "no_data"
    monkeypatch.setattr(build, "cached_exposures", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("IRSA down")))
    r = c.get("/api/targets/c1-p1-s5/updates")
    assert r.status_code == 502 and "IRSA down" in r.json()["message"]


def test_new_release_and_checked_label():
    mirror_prov = {"service": "local mirror of IRSA SPHEREx ObsCore (pipeline.mirror)", "query": "q", "retrieved_utc": "2026-11-14T14:22:45Z"}
    r = compare(_target(), OLD, mirror_prov, {"releases": ["dr1", "qr2", "qr3", "qr4"]})
    assert r["new_releases"] == ["QR4"] and r["releases_published"] == ["DR1", "QR2", "QR3", "QR4"]
    assert "QR4" in r["release_note"] and "re-harvest" in r["release_note"]
    assert r["checked_label"] == "the local SPHEREx image index (harvested 2026-11-14)"
    r = compare(_target(), OLD + [_exp(9, 61300.0, 2, "spherex_qr4")], PROV, {"releases": ["dr1", "qr3", "qr4"]})
    assert "re-harvest" not in r["release_note"] and r["new_collections"] == ["spherex_qr4"] and r["checked_label"] == "IRSA (2026-11-14)"
    assert compare(_target(), OLD, PROV, {"releases": ["dr1", "qr2", "qr3"]})["release_note"] is None


def test_old_build_releases_from_source_url():
    t = _target(with_summary=False, frames_coll=False)
    t["frames"][0]["source_url"] = "https://nasa-irsa-spherex.s3.amazonaws.com/dr1/level2/2025W33_2C/v/6/x.fits#rows=1:2"
    r = compare(t, OLD + [_exp(4, 61230.0, 2, "spherex_dr1_deep"), _exp(5, 61231.0, 2, "spherex_qr3")], PROV)
    assert r["releases_built"] == ["DR1"] and r["new_collections"] == ["spherex_qr3"]   # dr1_deep: same release
