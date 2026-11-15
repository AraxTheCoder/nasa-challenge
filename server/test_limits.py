"""T58: limits for a public Live API (fixture mode, offline)."""
from __future__ import annotations

import os
import time

import pytest
from fastapi.testclient import TestClient

from server import limits
from server.app import create_app


@pytest.fixture(autouse=True)
def _reset():
    yield
    limits.configure(False)


def _ready(client, body):
    for _ in range(100):
        if body["status"] != "building":
            return body
        time.sleep(0.05)
        body = client.get(body["poll_url"]).json()
    raise AssertionError("build did not finish")


def test_off_by_default_changes_nothing(tmp_path):
    limits.configure(False)
    client = TestClient(create_app(tmp_path, fixture=True))
    for _ in range(50):
        assert client.get("/api/targets").status_code == 200
    assert client.post("/api/settings", json={}).status_code != 403


def test_per_ip_request_rate(tmp_path):
    # burst max(20, 0.25) = 20; refill 1 per 10 min, so a slow machine can't earn a 21st request mid-test
    limits.configure(True, api_per_min=0.1, token="t")
    client = TestClient(create_app(tmp_path, fixture=True))
    codes = [client.get("/api/targets").status_code for _ in range(21)]
    assert codes[:20] == [200] * 20 and codes[20] == 429
    r = client.get("/api/targets")
    assert int(r.headers["Retry-After"]) >= 1 and "too many" in r.json()["message"]
    assert client.get("/api/health").status_code == 200                  # never limited


def test_new_builds_per_ip_and_server_cap(tmp_path, monkeypatch):
    limits.configure(True, jobs_burst=2, jobs_per_hour=1, token="t")
    client = TestClient(create_app(tmp_path, fixture=True))
    a = _ready(client, client.get("/api/target", params={"ra": 10, "dec": 20}).json())
    assert a["status"] == "ready"
    assert client.get("/api/target", params={"ra": 10, "dec": 20}).status_code == 200    # cached: free
    _ready(client, client.get("/api/target", params={"ra": 11, "dec": 20}).json())
    r = client.get("/api/target", params={"ra": 12, "dec": 20})
    assert r.status_code == 429 and "new fields" in r.json()["message"]
    limits.configure(True, token="t", max_active=1)
    monkeypatch.setattr(limits, "active_jobs", lambda: 1)
    r = client.get("/api/target", params={"ra": 13, "dec": 20})
    assert r.status_code == 503 and r.json()["status"] == "busy" and r.headers["Retry-After"]


def test_refresh_and_settings_need_the_token(tmp_path):
    limits.configure(True, token="s3cret")
    client = TestClient(create_app(tmp_path, fixture=True))
    _ready(client, client.get("/api/target", params={"ra": 10, "dec": 20}).json())
    r = client.get("/api/target", params={"ra": 10, "dec": 20, "refresh": 1})
    assert r.json()["status"] == "ready"                                 # refresh ignored without the token
    r = client.get("/api/target", params={"ra": 10, "dec": 20, "refresh": 1, "token": "s3cret"})
    assert r.json()["status"] == "building"
    assert client.post("/api/settings", json={"tiles": "local"}).status_code == 403
    assert client.post("/api/settings", json={}, headers={"X-Admin-Token": "s3cret"}).status_code == 200


def test_cache_sweep_evicts_least_recently_used(tmp_path):
    data = tmp_path / "data"
    for name, age in (("old", 300), ("mid", 200), ("new", 100), ("busy", 400)):
        d = data / "targets" / name
        d.mkdir(parents=True)
        f = d / "frame.png"
        f.write_bytes(b"x" * 1000)
        t = time.time() - age
        os.utime(f, (t, t)); os.utime(d, (t, t))
    s = data / "spectra" / "1.0000_+2.0000.json"
    s.parent.mkdir(parents=True)
    s.write_bytes(b"y" * 1000)
    t = time.time() - 250
    os.utime(s, (t, t))
    r = limits.sweep(data, cap_bytes=2500, busy_ids=frozenset({"busy"}))
    left = sorted(p.name for p in (data / "targets").iterdir())
    assert left == ["busy", "new"] and not s.exists() and r["removed"] == 3


def test_cache_cap_without_public_mode_and_tile_chunks(tmp_path):
    """T97: the sweep has its own switch and covers data/raw/s3chunks."""
    data = tmp_path / "data"
    (data / "targets").mkdir(parents=True)
    chunks = data / "raw" / "s3chunks"
    chunks.mkdir(parents=True)
    for k in range(3):
        f = chunks / f"c{k}.npy"
        f.write_bytes(b"z" * 1000)
        t = time.time() - 100 * (3 - k)
        os.utime(f, (t, t))
    limits.configure(False, cache_gb=1.5e-6, sweep_s=3600)          # 1500 bytes, no other limits
    t = limits.start_sweeper(data)
    assert t is not None
    for _ in range(100):
        if len(list(chunks.iterdir())) == 1:
            break
        time.sleep(0.02)
    assert [p.name for p in chunks.iterdir()] == ["c2.npy"]
    client = TestClient(create_app(data / "targets", fixture=True))
    assert all(client.get("/api/targets").status_code == 200 for _ in range(40))   # no rate limit without --public


def test_sweep_frees_disk_space_beyond_the_cap(tmp_path, monkeypatch):
    """T125: with too little free disk space the sweep evicts LRU entries even under the size cap."""
    import os
    import shutil as sh
    data = tmp_path / "data"
    for k, name in enumerate(["old", "mid", "new"]):
        d = data / "targets" / name
        d.mkdir(parents=True)
        (d / "x.bin").write_bytes(b"x" * 1000)
        os.utime(d / "x.bin", (1000 + k, 1000 + k))
        os.utime(d, (1000 + k, 1000 + k))
    limits.configure(False, cache_gb=1.0, min_free_gb=1.0)        # cap far above 3000 bytes
    usage = sh.disk_usage(tmp_path)
    monkeypatch.setattr(limits.shutil, "disk_usage", lambda p: usage._replace(free=int(1e9) - 1500))
    short = limits.free_shortfall(data)
    assert short == 1500
    r = limits.sweep(data, int(1e9), frozenset(), short)
    assert r["removed"] == 2 and sorted(p.name for p in (data / "targets").iterdir()) == ["new"]
    monkeypatch.setattr(limits.shutil, "disk_usage", lambda p: usage._replace(free=int(5e9)))
    assert limits.free_shortfall(data) == 0
    limits.configure(False, cache_gb=1.0, min_free_gb=0)
    assert limits.free_shortfall(data) == 0
