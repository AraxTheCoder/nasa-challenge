"""T52: VSX, CatWISE2020 and planet labels, offline (VizieR / SIMBAD / Horizons replaced by fakes)."""
import pytest

from pipeline import labels as L

TARGET = {"center": {"ra_deg": 180.0, "dec_deg": 0.0}, "image": {"width": 146, "height": 146, "pixel_scale_arcsec": 6.15},
          "frames": [{"id": "f0", "mjd": 60800.0}, {"id": "f1", "mjd": 61000.0}], "provenance": []}


def _vsx_row(name, ra, dec, typ="M", mx="7.1", f_min="", mn="13.2", per="245.6", band="V"):
    return {"Name": name, "RAJ2000": str(ra), "DEJ2000": str(dec), "Type": typ, "max": mx, "n_max": band,
            "f_min": f_min, "min": mn, "Period": per}


def test_vsx_note_type_period_range_and_amplitude(monkeypatch):
    rows = [_vsx_row("R Tst", 180.0, 0.0), _vsx_row("V9 Tst", 180.01, 0.0, typ="BY", mx="9.55", f_min="Y", mn="0.02", per="130"),
            _vsx_row("ASASSN-V J1200", 180.0, 0.01, typ="ROT", mx="18.5", per="")]   # survey name, too faint: dropped
    monkeypatch.setattr(L, "_asu", lambda params: (rows, "fake"))
    monkeypatch.setattr(L, "_simbad_by_id", lambda names: {})
    labels, prov = L.vsx_labels(TARGET, L.Grid(TARGET))
    assert [l["name"] for l in labels] == ["R Tst", "V9 Tst"]
    assert labels[0]["note"] == "Mira variable (M), period 245.6 d, range 7.1 to 13.2 mag"
    assert labels[1]["note"] == "rotating variable (spots) (BY), period 130 d, max 9.55 mag, amplitude 0.02"
    assert labels[0]["source"] == "vsx" and labels[0]["named"] and labels[0]["mag_band"] == "V"
    assert prov["service"].startswith("VSX")


def test_vsx_takes_proper_motion_from_simbad(monkeypatch):
    monkeypatch.setattr(L, "_asu", lambda params: ([_vsx_row("V2500 Oph", 180.0, 0.0)], "fake"))
    # SIMBAD: 10"/yr north from J2000
    monkeypatch.setattr(L, "_simbad_by_id", lambda names: {"V2500 Oph": (180.0, 0.0, 0.0, 10000.0)})
    labels, _ = L.vsx_labels(TARGET, L.Grid(TARGET))
    yrs = (60800.0 - L.J2000_MJD) / 365.25
    assert labels[0]["positions"][0]["dec_deg"] == pytest.approx(10 * yrs / 3600, abs=1e-5)


def _cw_row(name, ra, dec, pmra, pmde, w1, w2, n_seen="12", chi2="1.0", ccf="0000", abf="00", e="0.05"):
    return {"Name": name, "RAPMdeg": str(ra), "DEPMdeg": str(dec), "MJD": "57200", "pmRA": str(pmra), "pmDE": str(pmde),
            "e_pmRA": e, "e_pmDE": e, "W1mproPM": "" if w1 is None else str(w1), "W2mproPM": str(w2),
            "nW2": n_seen, "mW2": "12", "chi2pm": chi2, "ccf": ccf, "abf": abf}


def test_catwise_keeps_only_clean_red_movers(monkeypatch):
    rows = [_cw_row("J1", 180.0, 0.0, -7.9, 0.5, None, 13.9),          # Y dwarf: not in W1, fast -> kept
            _cw_row("J2", 180.02, 0.0, 0.0, 0.01, 15.0, 13.5),           # red, not moving (quasar) -> dropped
            _cw_row("J3", 180.0, 0.02, 1.0, 1.0, 14.0, 13.9),            # moving, not red (star) -> dropped
            _cw_row("J4", 180.01, 0.01, 2.0, 2.0, 16.0, 14.0, n_seen="4"),   # seen in 4 of 12 visits -> artefact
            _cw_row("J5", 179.99, 0.01, 2.0, 2.0, 16.0, 14.0, chi2="208"),   # bad motion fit -> artefact
            _cw_row("J6", 179.99, -0.01, 2.0, 2.0, 16.0, 14.0, ccf="HHH0")]  # flagged halo -> artefact
    monkeypatch.setattr(L, "_asu", lambda params: (rows, "fake"))
    labels, _ = L.catwise_labels(TARGET, L.Grid(TARGET))
    real = [l for l in labels if l["source"] == "catwise2020"]
    assert [l["name"] for l in real] == ["CWISE J1"]
    assert real[0]["kind"].startswith("brown dwarf candidate") and real[0]["mag_band"] == "W2"
    assert "not seen in W1" in real[0]["note"] and real[0]["pm_mas_yr"] == pytest.approx(7915.8, abs=0.1)


def _lab(source, ra, dec, mag=None, pm=None, named=False, name="x", at_epoch=True, note=None):
    l = {"name": name, "kind": "star", "otype": "*", "source": source, "named": named, "mag": mag, "pm_mas_yr": pm,
         "positions": [{"frame_id": "f0", "ra_deg": ra, "dec_deg": dec, "x": 0, "y": 0}]}
    if at_epoch:
        l["_at_epoch"] = {"ra_deg": ra, "dec_deg": dec}
    if note:
        l["note"] = note
    return l


def test_drop_glare_echoes_and_twins():
    star = _lab("gaia_dr3", 180.0, 0.0, mag=8.0, pm=10000, name="bright fast star")
    in_glare = _lab("catwise2020", 180.0, 40 / 3600, mag=14, pm=2000, name="glare")
    echo = _lab("catwise2020", 180.0, 150 / 3600, mag=14, pm=8000, name="echo")              # 2.5' away, similar rate
    real = _lab("catwise2020", 180.0, 0.1, mag=14.0, pm=500, name="real")                     # 6' away
    twin = _lab("catwise2020", 180.0, 0.1 + 10 / 3600, mag=14.5, pm=600, name="twin of real")
    out = L._drop_glare([star, in_glare, echo, real, twin])
    assert [l["name"] for l in out] == ["bright fast star", "real"]
    assert not any("_at_epoch" in l for l in out)


def test_merge_keeps_catalogue_name_and_takes_vsx_note():
    sim = _lab("simbad", 180.0, 0.0, name="WISEA J085510", named=False, at_epoch=False)
    cw = _lab("catwise2020", 180.0, 0.5 / 3600, name="CWISE J085506", named=True, at_epoch=False)
    vsx = _lab("vsx", 180.0, 1 / 3600, name="CI Ind", named=True, at_epoch=False, note="variable star (VBD)")
    out = L.merge_duplicates([cw, sim, vsx])
    assert len(out) == 1
    assert out[0]["name"] == "CI Ind"                  # VSX name in front, never the CatWISE one
    assert out[0]["note"] == "variable star (VBD)"
    assert set(out[0]["aliases"]) == {"WISEA J085510", "CWISE J085506"}


def test_planets_none_near_means_no_horizons_call(monkeypatch):
    import detect.known_objects as ko
    monkeypatch.setattr(ko.Jpl, "positions_id", lambda *a: (_ for _ in ()).throw(AssertionError("Horizons asked")))
    t = {**TARGET, "center": {"ra_deg": 90.0, "dec_deg": 85.0}}   # far from the ecliptic
    assert L.planet_labels(t, L.Grid(t)) == ([], None)


def test_sky_region_snaps_to_grid():
    assert L.sky_region(269.4463, 4.7682, 0.4) == L.sky_region(269.43, 4.76, 0.3)    # same cache entry
    ra, dec, r = L.sky_region(10.68, 41.27, 0.8)
    assert (dec, r) == (41.25, 1.0) and abs(ra - 10.68) < 0.34
    assert L.sky_region(359.99, 0.0, 9)[2] == L.SKY_RADII[-1] and 0 <= L.sky_region(359.99, 0.0, 1)[0] < 360


def test_sky_labels_rows_and_order(monkeypatch):
    def fake_add(t, sources=None):
        assert L.planet_labels not in sources          # planets move: not on the all-epoch map
        p = [{"frame_id": "s0", "ra_deg": 1.0, "dec_deg": 2.0, "x": 0, "y": 0}]
        t["labels"] = [
            {"name": "HD  1", "kind": "star", "otype": "*", "source": "simbad", "named": True, "mag": 7.0, "importance": 2, "positions": p},
            {"name": "M  31", "kind": "galaxy", "otype": "G", "source": "simbad", "named": True, "mag": None, "importance": 0, "positions": p},
            {"name": "Gaia DR3 1", "kind": "star", "otype": "*", "source": "gaia_dr3", "named": False, "mag": 9.0, "importance": 4, "positions": p}]
        t["provenance"].append({"service": "SIMBAD"})
        return t
    monkeypatch.setattr(L, "add_labels", fake_add)
    out = L.sky_labels(10.0, 41.0, 0.5)
    assert [r["name"] for r in out["labels"]] == ["M 31", "HD 1"]          # Gaia only for merging; names tidied
    assert out["labels"][0]["ra_deg"] == 1.0 and "positions" not in out["labels"][0]
