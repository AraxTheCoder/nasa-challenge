"""T76: GET /api/discoveries (CONTRACTS v0.13 "Discoveries")."""
import json

import pytest
from fastapi.testclient import TestClient

from server import discoveries
from server.app import create_app


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(cache_root=tmp_path / "targets", fixture=True))


def _index(tmp_path, monkeypatch, candidates, **head):
    path = tmp_path / "discoveries.json"
    path.write_text(json.dumps({"synthetic": False, "survey": "test", "generated_utc": "2026-11-14T00:00:00Z",
                                "provenance": [], "candidates": candidates, **head}), encoding="utf-8")
    monkeypatch.setattr(discoveries, "SURVEY_INDEX", path)
    return path


def _c(i, cls, score, ra=10.0, dec=0.0):
    return {"id": f"c{i}", "ra_deg": ra, "dec_deg": dec, "class": cls, "score": score, "reason": "test"}


def test_sample_served_until_the_survey_delivers(client, tmp_path, monkeypatch):
    monkeypatch.setattr(discoveries, "SURVEY_INDEX", tmp_path / "missing.json")
    body = client.get("/api/discoveries").json()
    assert body["status"] == "ready" and body["synthetic"] is True
    assert body["source"] == "fixtures/discoveries-sample.json"
    assert body["count"] == body["total"] >= 5
    scores = [c["score"] for c in body["candidates"]]
    assert scores == sorted(scores, reverse=True)


def test_filters(client, tmp_path, monkeypatch):
    _index(tmp_path, monkeypatch, [_c(1, "mover", 0.2), _c(2, "brown_dwarf", 0.9, ra=200.0, dec=-30.0),
                                   _c(3, "variable", 0.5), _c(4, "brown_dwarf", 0.4)])
    ids = lambda **q: [c["id"] for c in client.get("/api/discoveries", params=q).json()["candidates"]]  # noqa: E731
    assert ids() == ["c2", "c3", "c4", "c1"]
    assert ids(**{"class": "brown_dwarf"}) == ["c2", "c4"]
    assert ids(**{"class": "mover,variable"}) == ["c3", "c1"]
    assert ids(min_score=0.45) == ["c2", "c3"]
    assert ids(limit=2) == ["c2", "c3"]
    assert ids(ra=10.5, dec=0.2, radius=1) == ["c3", "c4", "c1"]
    assert ids(ra=359.9, dec=0, radius=10.2) == ["c3", "c4", "c1"]     # across RA 0
    one = client.get("/api/discoveries", params={"random": 1, "class": "brown_dwarf"}).json()
    assert one["count"] == 1 and one["total"] == 4 and one["candidates"][0]["id"] in ("c2", "c4")
    assert client.get("/api/discoveries", params={"random": 1, "class": "nothing"}).json()["candidates"] == []


def test_reloads_when_the_file_changes(client, tmp_path, monkeypatch):
    path = _index(tmp_path, monkeypatch, [_c(1, "mover", 0.2)])
    assert client.get("/api/discoveries").json()["count"] == 1
    data = json.loads(path.read_text())
    data["candidates"].append(_c(2, "mover", 0.3))
    path.write_text(json.dumps(data))
    import os
    os.utime(path, (path.stat().st_atime, path.stat().st_mtime + 5))
    assert client.get("/api/discoveries").json()["count"] == 2


@pytest.mark.parametrize("q", [{"ra": 10}, {"ra": 10, "dec": 0}, {"ra": 400, "dec": 0, "radius": 1},
                               {"ra": 10, "dec": 0, "radius": 0}, {"limit": 0}])
def test_bad_requests(client, q):
    r = client.get("/api/discoveries", params=q)
    assert r.status_code == 400 and r.json()["status"] == "error"
