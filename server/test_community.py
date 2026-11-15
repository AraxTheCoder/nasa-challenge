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
    assert client.post(url, json={"browser": "a"}).json() == {"status": "ready", "views": 1, "counted": True,
        "coverage": {"level": "light", "label": "Light attention", "browsers": 1}}
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


def test_second_look_evidence_and_unanswered_feed(client):
    payload = {"kind": "second_look", "title": "A moving red source?", "text": "Can someone compare these epochs?",
               "ra_deg": 133.79, "dec_deg": -7.24, "fov_arcmin": 15,
               "evidence": {"target_id": "test-field", "frame_a": "f000", "frame_b": "f003",
                            "frame_a_time": "2025-01-01T00:00:00Z", "wavelength_um": 4.5, "synthetic": False}}
    r = client.post("/api/community/tiles/777/comments", json=payload)
    assert r.status_code == 201
    saved = r.json()["comment"]
    assert {key: saved[key] for key in payload} == payload
    client.post("/api/community/tiles/778/comments", json={"text": "ordinary discussion"})
    feed = client.get("/api/community/recent?unanswered=true").json()["latest"]
    assert [c["id"] for c in feed] == [saved["id"]]
    assert feed[0]["pix"] == 777 and feed[0]["evidence"] == payload["evidence"]
    assert client.get("/api/community/tiles/777").json()["comments"][0]["evidence"] == payload["evidence"]
    reply = client.post("/api/community/tiles/777/comments", json={"parent_id": saved["id"], "text": "I will check."})
    assert reply.status_code == 201
    assert client.get("/api/community/recent?unanswered=true").json()["latest"] == []
    assert len(client.get("/api/community/recent").json()["latest"]) == 3


@pytest.mark.parametrize("extra", [
    {"kind": "confirmed"}, {"kind": "second_look"}, {"title": "x" * 121},
    {"evidence": []}, {"evidence": {"url": "javascript:alert(1)"}},
    {"evidence": {"frame_a": "x" * 181}}, {"evidence": {"synthetic": "false"}},
    {"evidence": {"wavelength_um": "nan"}}, {"evidence": {"wavelength_um": True}},
    {"evidence": {"field_ra_deg": 360}}, {"evidence": {"field_dec_deg": -91}},
    {"evidence": {"field_size_arcmin": 0}}, {"evidence": {"layer": "bad\x00layer"}},
    {"parent_id": []}, {"parent_id": {}}, {"parent_id": True}, {"parent_id": "1"},
    {"ra_deg": 12}, {"fov_arcmin": 15},
])
def test_second_look_validation(client, extra):
    response = client.post("/api/community/tiles/777/comments", json={"text": "check this", **extra})
    assert response.status_code == 400
    assert client.get("/api/community/tiles/777").json()["n_comments"] == 0


def test_reply_cannot_create_second_look(client):
    parent = client.post("/api/community/tiles/777/comments", json={"text": "question"}).json()["comment"]["id"]
    r = client.post("/api/community/tiles/777/comments", json={"text": "reply", "parent_id": parent,
                    "kind": "second_look", "ra_deg": 10, "dec_deg": 0, "fov_arcmin": 15})
    assert r.status_code == 400


def test_old_database_migrates_without_losing_discussions(client):
    import sqlite3
    community.ROOT.mkdir(parents=True)
    with sqlite3.connect(community.ROOT / "community.db") as db:
        db.executescript(community.SCHEMA)
        db.execute("INSERT INTO comments (pix, author, text, created_utc) VALUES (777, 'Ada', 'old comment', '2026-11-14T00:00:00Z')")
        db.execute("INSERT INTO views (pix, n) VALUES (777, 42)")
    old = client.get("/api/community/tiles/777").json()
    assert old["views"] == 42 and old["comments"][0]["text"] == "old comment"
    assert old["comments"][0]["kind"] == "discussion" and old["comments"][0]["evidence"] is None
    # Reconnect to exercise the migration twice, as happens on API restarts.
    community._db.close()
    community._db = None
    assert client.get("/api/community/tiles/777").json() == old
    assert client.post("/api/community/tiles/777/comments", json={"text": "new reply", "parent_id": old["comments"][0]["id"]}).status_code == 201



def test_coverage_uses_distinct_browsers_not_repeat_visits(client, monkeypatch):
    now = 1000000.
    monkeypatch.setattr(community.time, "time", lambda: now)
    url = "/api/community/tiles/777/view"
    assert client.post(url, json={"browser": "a"}).json()["coverage"]["browsers"] == 1
    for _ in range(12):
        now += 3601
        response = client.post(url, json={"browser": "a"}).json()
    assert response["views"] == 13 and response["coverage"]["level"] == "light"
    assert response["coverage"]["browsers"] == 1
    client.post(url, json={"browser": "b"})
    third = client.post(url, json={"browser": "c"}).json()["coverage"]
    assert third == {"level": "moderate", "label": "Some attention", "browsers": 3}
    for i in range(7):
        client.post(url, json={"browser": f"other-{i}"})
    tile = client.get("/api/community/tiles/777").json()
    assert tile["coverage"] == {"level": "high", "label": "High attention", "browsers": 10}
    counts = client.get("/api/community/counts?pix=777,778").json()
    assert counts["coverage"]["777"] == tile["coverage"]
    assert counts["coverage"]["778"] == {"level": "unvisited", "label": "Unvisited", "browsers": 0}


def test_coverage_overview_summary_and_exploration_order(client):
    fresh = client.get("/api/community/coverage?limit=4").json()
    assert fresh["summary"] == {"unvisited": community.NPIX, "light": 0, "moderate": 0, "high": 0}
    assert len(fresh["tiles"]) == 4 and all(t["coverage"]["browsers"] == 0 for t in fresh["tiles"])
    assert len({t["pix"] for t in fresh["tiles"]}) == 4
    assert client.get("/api/community/coverage?sort=most").json()["tiles"] == []
    for pix, n in ((777, 1), (778, 3), (779, 10)):
        for i in range(n):
            client.post(f"/api/community/tiles/{pix}/view", json={"browser": str(i)})
    popular = client.get("/api/community/coverage?sort=most&limit=2").json()
    assert [t["pix"] for t in popular["tiles"]] == [779, 778]
    assert popular["summary"] == {"unvisited": community.NPIX - 3, "light": 1, "moderate": 1, "high": 1}
    assert sum(popular["summary"].values()) == community.NPIX
    assert popular["basis"] == "distinct_browser_ids"
    least = client.get("/api/community/coverage?sort=least&limit=5").json()["tiles"]
    assert all(t["coverage"]["browsers"] == 0 for t in least)
    assert all(-90 <= t["center"]["dec_deg"] <= 90 for t in least)
    assert len(client.get("/api/community/coverage?limit=1000").json()["tiles"]) == 100
    assert client.get("/api/community/coverage?sort=unknown").status_code == 400
