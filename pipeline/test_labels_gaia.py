"""pytest pipeline/test_labels_gaia.py (T141): Gaia labels from VizieR when ESA's TAP doesn't answer. No network."""
import numpy as np
import pytest

from pipeline import labels
from pipeline.labels import J2016_MJD, Grid

FRAME_MJD = 60900.0
TARGET = {"center": {"ra_deg": 269.4463, "dec_deg": 4.7682},
          "image": {"width": 146, "height": 146, "pixel_scale_arcsec": 6.15},
          "frames": [{"id": "a", "mjd": FRAME_MJD}]}
ROWS = [  # what VizieR's I/355/gaiadr3 sends (strings), brightest first: Barnard's Star, then a star without motion
    {"Source": "4472832130942575872", "RA_ICRS": "269.44850252544", "DE_ICRS": "+04.73942005111",
     "pmRA": "-801.551", "pmDE": "10362.394", "Gmag": "8.193974"},
    {"Source": "4472836460256445696", "RA_ICRS": "269.44000000000", "DE_ICRS": "+04.76000000000",
     "pmRA": "", "pmDE": "", "Gmag": "10.600650"},
]
VIZIER_URL = "https://vizier.cfa.harvard.edu/viz-bin/asu-tsv"


@pytest.fixture(autouse=True)
def _esa_not_paused(monkeypatch):
    monkeypatch.setattr(labels, "_gaia_tap_down_until", 0.0)


def test_vizier_when_esa_does_not_answer(monkeypatch):
    calls = {"tap": 0, "asu": []}

    def dead_tap(url, adql):
        calls["tap"] += 1
        raise ConnectionError("HTTPSConnectionPool(host='gea.esac.esa.int'): Max retries exceeded")

    def asu(params):
        calls["asu"].append(params)
        return ROWS, VIZIER_URL

    monkeypatch.setattr(labels, "_tap", dead_tap)
    monkeypatch.setattr(labels, "_asu", asu)
    got, prov = labels.gaia_labels(TARGET, Grid(TARGET))
    assert [l["name"] for l in got] == [f"Gaia DR3 {r['Source']}" for r in ROWS]
    assert got[0]["source"] == "gaia_dr3" and got[0]["mag"] == 8.19 and got[0]["pm_mas_yr"] > 10000
    assert got[1]["pm_mas_yr"] is None                  # no motion in the catalogue: unknown, not 0
    assert "VizieR" in prov["service"] and labels.GAIA_VIZIER in prov["service"] and prov["retrieved_utc"]
    assert calls["asu"][0]["Gmag"] == f"<{labels.GAIA_MAX_G}" and calls["asu"][0]["-sort"] == "Gmag"
    # positions from J2016.0 moved by the motion to the frame's time, as with ESA: Barnard's ~100" north
    years = (FRAME_MJD - J2016_MJD) / 365.25
    assert abs(got[0]["positions"][0]["dec_deg"] - (4.73942005111 + years * 10.362394 / 3600)) < 1e-3
    # the next field doesn't wait for ESA again (a dead host costs TIMEOUT_S per field)
    labels.gaia_labels(TARGET, Grid(TARGET))
    assert calls["tap"] == 1 and len(calls["asu"]) == 2


def test_esa_first_when_it_answers(monkeypatch):
    def tap(url, adql):
        return {"source_id": np.ma.asarray(np.array([7], dtype=np.int64)), "ra": np.ma.asarray([269.44]),
                "dec": np.ma.asarray([4.76]), "pmra": np.ma.asarray([1.0]), "pmdec": np.ma.asarray([2.0]),
                "phot_g_mean_mag": np.ma.asarray([12.0])}

    monkeypatch.setattr(labels, "_tap", tap)
    monkeypatch.setattr(labels, "_asu", lambda params: pytest.fail("VizieR asked although ESA answered"))
    got, prov = labels.gaia_labels(TARGET, Grid(TARGET))
    assert [l["name"] for l in got] == ["Gaia DR3 7"] and prov["service"].startswith("Gaia DR3 TAP (ESA)")


def test_neither_answers(monkeypatch):
    def down(*a, **k):
        raise ConnectionError("down")

    monkeypatch.setattr(labels, "_tap", down)
    monkeypatch.setattr(labels, "_asu", down)
    assert labels.gaia_labels(TARGET, Grid(TARGET)) == ([], None)
