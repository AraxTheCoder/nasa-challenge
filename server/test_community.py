"""T120: views and discussion threads per map tile."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server import community, limits
from server.app import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(community, "ROOT", tmp_path / "community")
    monkeypatch.setattr(community, "_posts", {})
    limits.configure(False)
    return TestClient(create_app(tmp_path / "targets", fixture=True))


def test_views_count_once_per_browser_per_hour(client):
    url = "/api/community/tiles/12345/view"
    assert client.post(url, json={"browser": "a"}).json() == {"status": "ready", "views": 1, "counted": True}
    assert client.post(url, json={"browser": "a"}).json()["counted"] is False
    assert client.post(url, json={"browser": "b"}).json()["views"] == 2
    t = client.get("/api/community/tiles/12345").json()
    assert t["views"] == 2 and t["tile"] == {"order": 6, "pix": 12345} and t["comments"] == []
    assert -90 <= t["center"]["dec_deg"] <= 90


def test_thread_with_replies_and_position(client):
    url = "/api/community/tiles/777/comments"
    r = client.post(url, json={"author": "Ada", "text": "Something red moves here?", "ra_deg": 133.79, "dec_deg": -7.24,
                               "fov_arcmin": 15})
    assert r.status_code == 201
    first = r.json()["comment"]
    reply = client.post(url, json={"author": "Ben", "text": "WISE 0855, a brown dwarf.", "parent_id": first["id"]}).json()["comment"]
    # a reply to a reply joins the same thread (one level)
    deeper = client.post(url, json={"text": "Thanks!", "parent_id": reply["id"]}).json()["comment"]
    assert deeper["parent_id"] == first["id"] and deeper["author"] == "anonymous"
    t = client.get("/api/community/tiles/777").json()
    assert t["n_comments"] == 3 and len(t["comments"]) == 1
    c = t["comments"][0]
    assert c["text"] == "Something red moves here?" and c["ra_deg"] == 133.79 and len(c["replies"]) == 2
    rec = client.get("/api/community/recent").json()
    assert rec["latest"][0]["text"] == "Thanks!" and rec["most_discussed"][0] == {**rec["most_discussed"][0], "pix": 777, "n_comments": 3}
    counts = client.get("/api/community/counts", params={"pix": "777,778"}).json()["tiles"]
    assert counts["777"]["comments"] == 3 and counts["778"] == {"views": 0, "comments": 0}


def test_text_is_stored_as_text_and_checked(client):
    url = "/api/community/tiles/5/comments"
    html = client.post(url, json={"text": "<script>alert(1)</script>\x00 hi"}).json()["comment"]
    assert html["text"] == "<script>alert(1)</script> hi"          # kept as text (the viewer never renders HTML)
    assert client.post(url, json={"text": "   "}).status_code == 400
    assert client.post(url, json={"text": "x" * 2001}).status_code == 400
    assert client.post(url, json={"text": "ok", "ra_deg": "nan"}).status_code == 400
    assert client.post(url, json={"text": "ok", "parent_id": 999}).status_code == 400
    other = client.post("/api/community/tiles/6/comments", json={"text": "elsewhere"}).json()["comment"]
    assert client.post(url, json={"text": "ok", "parent_id": other["id"]}).status_code == 400   # not this tile's thread
    assert client.get("/api/community/tiles/99999999").status_code == 400
    assert client.post(url, content=b"not json").status_code == 400


def test_posting_is_rate_limited(client):
    url = "/api/community/tiles/9/comments"
    codes = [client.post(url, json={"text": f"c{k}"}).status_code for k in range(11)]
    assert codes[:10] == [201] * 10 and codes[10] == 429
