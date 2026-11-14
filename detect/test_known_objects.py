"""Offline tests for detect.known_objects (T07): no network, the JPL client is faked."""
from __future__ import annotations

import pytest

from detect.known_objects import (Jpl, add_known_objects, find_known_objects, group_visits, horizons_command,
                                  parse_horizons_table, sexagesimal)
from pipeline.labels import Grid


def frame(fid, mjd):
    return {"id": fid, "mjd": mjd, "time_utc": "2025-08-15T00:00:00Z", "epoch": 1, "detector": 1,
            "wavelength_um": 1.0, "image": f"frames/{fid}.png", "obs_id": None, "source_url": None}


TARGET = {
    "id": "t", "center": {"ra_deg": 323.8, "dec_deg": -13.9}, "size_arcmin": 15,
    "image": {"width": 146, "height": 146, "pixel_scale_arcsec": 6.15},
    # two visits: f0+f1 two minutes apart, f2 six days later
    "frames": [frame("f0", 60902.8654), frame("f1", 60902.8668), frame("f2", 60908.98)],
    "known_objects": [], "detections": [], "provenance": [],
}


def test_group_visits_splits_on_gaps():
    visits = group_visits(TARGET["frames"])
    assert [[f["id"] for f in v] for v in visits] == [["f0", "f1"], ["f2"]]


@pytest.mark.parametrize("deg,hours,expected", [
    (269.4463, True, "17-57-47.11"),
    (4.7682, False, "04-46-05.52"),
    (-14.0, False, "M14-00-00.00"),
    (-7.2422, False, "M07-14-31.92"),
    (0.0, True, "00-00-00.00"),
])
def test_sexagesimal(deg, hours, expected):
    assert sexagesimal(deg, hours) == expected


@pytest.mark.parametrize("name,expected", [
    ("6779 Perrine (1990 DM1)", "6779;"),
    ("41991 (2000 YJ34)", "41991;"),
    ("(2000 YJ34)", "DES=2000 YJ34;"),
    ("C/2020 F3 (NEOWISE)", "DES=C/2020 F3;CAP;"),
    ("29P/Schwassmann-Wachmann 1", "DES=29P;CAP;NOFRAG;"),
    ("332P/Ikeya-Murakami", "DES=332P;CAP;NOFRAG;"),
])
def test_horizons_command(name, expected):
    assert horizons_command(name) == expected


def test_parse_horizons_table():
    text = "header\n$$SOE\n 2025-Aug-15 20:46:08.832, , ,   323.83627,  -13.88650,\n$$EOE\nfooter"
    assert parse_horizons_table(text) == [["2025-Aug-15 20:46:08.832", "", "", "323.83627", "-13.88650", ""]]
    with pytest.raises(ValueError):
        parse_horizons_table("No ephemeris for target")


class FakeJpl(Jpl):
    """Visit 1 finds one asteroid crossing the field and one far outside; visit 2 finds nothing."""

    def __init__(self):
        super().__init__(session=None)
        self.calls = []

    def _get(self, url, params, service):  # never reach the network
        raise AssertionError("network used in an offline test")

    def spherex_states(self, jds):
        self.calls.append(("states", len(jds)))
        self.log.append({"service": "JPL Horizons (SPHEREx state vectors)", "query": "q", "retrieved_utc": "2026-11-14T00:00:00Z"})
        return {jd: [-3735.9, -5521.7, 2220.4, -2.25, -1.34, -7.07] for jd in jds}

    def candidates(self, jd, state, ra_deg, dec_deg, half_width_deg, vmag_lim):
        self.calls.append(("candidates", round(jd, 3), vmag_lim))
        self.log.append({"service": "JPL SB Identification (sb_ident, first pass)", "query": "q", "retrieved_utc": "2026-11-14T00:00:01Z"})
        return ["6779 Perrine (1990 DM1)", "(1927 LA)"] if jd < 2460905 else []

    def positions(self, name, jds):
        self.calls.append(("positions", name, len(jds)))
        if name.startswith("6779"):
            return [(323.80, -13.90), (323.79, -13.899)][: len(jds)]  # in the field, moving west
        return [(258.66, -1.77)] * len(jds)  # far away: dropped


def test_find_known_objects_end_to_end():
    jpl = FakeJpl()
    objs = find_known_objects(TARGET, jpl, vmag_lim=19)
    assert [o["name"] for o in objs] == ["6779 Perrine (1990 DM1)"]
    o = objs[0]
    assert o["source"] == "jpl-sbident" and o["synthetic"] is False
    assert [p["frame_id"] for p in o["positions"]] == ["f0", "f1"]
    grid = Grid(TARGET)
    x, y = (float(v) for v in grid.to_xy(323.80, -13.90))
    assert o["positions"][0]["x"] == pytest.approx(x, abs=0.01) and o["positions"][0]["y"] == pytest.approx(y, abs=0.01)
    assert o["positions"][1]["x"] > o["positions"][0]["x"]  # moving west = to the right (east left)
    # one state-vector call for both visits, one candidate search per visit, the vmag limit passed on
    assert ("states", 2) in jpl.calls
    assert sum(1 for c in jpl.calls if c[0] == "candidates") == 2
    assert all(c[2] == 19 for c in jpl.calls if c[0] == "candidates")


def test_add_known_objects_writes_only_its_fields_and_provenance():
    t = {**TARGET, "frames": list(TARGET["frames"]), "provenance": [{"service": "x", "query": "y", "retrieved_utc": "z"}],
         "labels": [{"id": "l0"}], "detections": [{"id": "d1"}]}
    add_known_objects(t, FakeJpl(), vmag_lim=19)
    assert len(t["known_objects"]) == 1
    assert t["labels"] == [{"id": "l0"}] and t["detections"] == [{"id": "d1"}]
    services = [p["service"] for p in t["provenance"]]
    assert services[0] == "x"
    assert "JPL Horizons (SPHEREx state vectors)" in services and "JPL SB Identification (sb_ident, first pass)" in services
    assert all(p["retrieved_utc"] for p in t["provenance"])
