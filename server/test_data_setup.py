"""T71: background data setup decides correctly what to fetch (fakes, no network)."""
from detect import mpcorb
from pipeline import mirror
from server import data_setup


def test_orbits_fetched_when_missing_or_old_skipped_when_fresh(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(mpcorb, "fetch", lambda root: calls.append("fetch"))
    monkeypatch.setattr(mpcorb, "build", lambda src, out: calls.append("build") or 10)
    monkeypatch.setattr(mpcorb, "build_comets", lambda src, out: calls.append("comets") or 2)
    for age, expect in ((None, ["fetch", "build", "comets"]), (30.0, ["fetch", "build", "comets"]), (1.0, [])):
        calls.clear()
        monkeypatch.setattr(mpcorb, "age_days", lambda root, age=age: age)
        data_setup.ensure_orbits(tmp_path)
        assert calls == expect, age


def test_index_harvested_only_when_missing(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(mirror, "harvest", lambda root: calls.append("harvest"))
    monkeypatch.setattr(mirror, "build", lambda root: calls.append("build"))
    monkeypatch.setattr(mirror, "available", lambda root: False)
    data_setup.ensure_image_index(tmp_path)
    monkeypatch.setattr(mirror, "available", lambda root: True)
    data_setup.ensure_image_index(tmp_path)
    assert calls == ["harvest", "build"]


def test_a_failure_does_not_stop_the_other_step(tmp_path, monkeypatch):
    done = []
    monkeypatch.setattr(data_setup, "ensure_orbits", lambda root: (_ for _ in ()).throw(OSError("MPC down")))
    monkeypatch.setattr(data_setup, "ensure_image_index", lambda root: done.append(root.name))
    data_setup.start(tmp_path).join(5)
    assert done == ["mirror"]
