"""T128: pipeline.catcheck with the services faked (no network)."""
import numpy as np

from pipeline import catcheck as K
from pipeline import labels as L


def _simbad_rows(rows):
    cols = {k: [r[i] for r in rows] for i, k in enumerate(("main_id", "ra", "dec", "pmra", "pmdec", "otype"))}
    return lambda url, adql: {k: np.ma.asarray(np.array(v, dtype=object if k in ("main_id", "otype") else float))
                              for k, v in cols.items()}


def test_a_fast_mover_matches_after_its_motion(tmp_path, monkeypatch):
    """A brown dwarf moving 4.7″/yr sits 122″ from its SIMBAD (2000) position in 2026: matched after moving it;
    a catalogue without motions (2MASS) does not match it; an empty spot matches nothing."""
    spot = (331.0953, -56.8002)
    pmra, pmdec = 3962.0, -2539.0                                  # mas/yr (pmra with cos dec)
    years = 2026.0 - 2000.0
    ra0 = spot[0] - pmra / 1000 * years / 3600 / np.cos(np.radians(spot[1]))
    dec0 = spot[1] - pmdec / 1000 * years / 3600
    monkeypatch.setattr(L, "_tap", _simbad_rows([("* eps Ind B", ra0, dec0, pmra, pmdec, "BD*"),
                                                 ("[XX] 1", ra0 + 0.01, dec0, 0.0, 0.0, "X")]))
    monkeypatch.setattr(L, "_asu", lambda params: ([{"RAJ2000": f"{ra0:.6f}", "DEJ2000": f"{dec0:.6f}",
                                                     "JD": "2451544.5", "2MASS": "J1", "Kmag": "11.2"}], "url"))
    r = K.check(tmp_path, [spot, (10.0, 10.0)], ["simbad", "2mass"], 2026.0)
    assert r["failed"] == []
    assert r["matches"][0]["simbad"]["name"] == "* eps Ind B" and r["matches"][0]["simbad"]["sep_arcsec"] < 1
    assert r["matches"][0]["2mass"] is None                       # no motion in 2MASS: 122″ away
    assert r["matches"][1] == {"simbad": None, "2mass": None}
    assert (tmp_path / "chemistry" / "catcheck.json").is_file()     # cached: no service needed the second time
    monkeypatch.setattr(L, "_tap", lambda url, adql: (_ for _ in ()).throw(AssertionError("asked again")))
    assert K.check(tmp_path, [spot], ["simbad"], 2026.0)["matches"][0]["simbad"]["name"] == "* eps Ind B"


def test_a_failed_catalogue_is_reported_not_counted_as_empty(tmp_path, monkeypatch):
    def down(*a, **k):
        raise ConnectionError("no answer")
    monkeypatch.setattr(L, "_tap", down)
    monkeypatch.setattr(L, "_asu", lambda params: ([], "url"))
    r = K.check(tmp_path, [(10.0, 10.0)], ["simbad", "gaia"], 2026.0)
    assert r["failed"] == ["simbad"] and r["matches"] == [{"gaia": None}]
    assert "simbad" not in (tmp_path / "chemistry" / "catcheck.json").read_text()   # a failure is not cached


def test_tags_and_order():
    items = [{"id": k} for k in "abcd"]
    res = {"matches": [{"simbad": {"otype": "BD*"}}, {"simbad": {"otype": "*"}}, {"simbad": None, "gaia": {"name": "g"}},
                       {"simbad": None, "gaia": None}]}
    out = K.tag(items, res, ["BD*", "BD?"])
    assert [(it["id"], it["tag"]) for it in out] == [("d", "new"), ("b", "other"), ("c", "untyped"), ("a", "known")]
    assert K.tag([{"id": "q"}], {"matches": [{"simbad": {"otype": "Sy2"}}]}, "galaxies")[0]["tag"] == "known"
    assert K.tag([{"id": "p"}], {"matches": [{"simbad": {"otype": "BD*"}}]}, None)[0]["tag"] == "other"   # places
