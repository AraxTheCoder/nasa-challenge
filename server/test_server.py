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
    with pytest.raises(CoordError):
        parse_size("120")


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
