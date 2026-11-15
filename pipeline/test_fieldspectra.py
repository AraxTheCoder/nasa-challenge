"""T85 field spectra + T86 spectral outliers, offline (synthetic cutouts and synthetic fields)."""
from __future__ import annotations

import numpy as np
import pytest

from pipeline import fieldspectra as FS
from pipeline import photometry
from pipeline import spectral_outliers as SO
from pipeline.query import Exposure
from pipeline.test_photometry import DEC0, RA0, SCALE_DEG, write_cutout


def test_measure_many_matches_single(tmp_path):
    write_cutout(tmp_path / "c.fits", star_ujy=1000.0, star_offset=(5.0, -4.0))
    star = (RA0 - 5.0 * SCALE_DEG / np.cos(np.radians(DEC0)), DEC0 - 4.0 * SCALE_DEG)
    off = (RA0 + 1.0, DEC0)
    many = photometry.measure_cutout_many(tmp_path / "c.fits", [star, off, (RA0, DEC0)])
    assert many[1] is None
    assert many[0] == photometry.measure_cutout(tmp_path / "c.fits", *star)
    assert many[0]["flux_ujy"] == pytest.approx(1000.0, rel=0.03)
    assert abs(many[2]["flux_ujy"]) < many[0]["flux_ujy"] / 3        # empty sky next to it


def _target():
    frames = [{"id": f"f{k}", "mjd": 60800.0 + 180 * k} for k in range(3)]
    lab = lambda i, name, src, mag, ra, dec, **kw: {"id": f"l{i}", "name": name, "source": src, "mag": mag,
                                                    "positions": [{"frame_id": f["id"], "ra_deg": ra, "dec_deg": dec + kw.get("pm", 0) * k}
                                                                  for k, f in enumerate(frames)], **kw}
    return {"id": "t1", "center": {"ra_deg": RA0, "dec_deg": DEC0}, "size_arcmin": 5, "frames": frames, "labels": [
        lab(0, "HD 1", "simbad", 8.0, RA0, DEC0, named=True),
        lab(1, "Gaia DR3 1", "gaia_dr3", 8.1, RA0 + 1 / 3600, DEC0),        # SIMBAD's Gaia twin: one source
        lab(2, "Fast star", "simbad", 10.0, RA0 + 0.01, DEC0, pm=0.001),
        {"id": "l3", "name": "(1) Ceres", "kind": "asteroid", "positions": [{"frame_id": "f0", "ra_deg": RA0, "dec_deg": DEC0}]},
    ]}


def test_sources_dedupe_track_and_skip_movers():
    src = FS.sources_of(_target())
    assert [s["name"] for s in src] == ["HD 1", "Fast star"] and src[0]["aliases"] == ["Gaia DR3 1"]
    fast = src[1]
    (ra, dec), = FS.positions_at([fast], 60800.0 + 360)
    assert dec == pytest.approx(DEC0 + 0.002, abs=1e-7)                # followed along its track


def test_measure_field_reads_each_exposure_once(tmp_path, monkeypatch):
    monkeypatch.setattr(FS, "ROOT", tmp_path / "fs")
    calls = []

    def fake_cutout(url, ra, dec, size_deg):
        calls.append(url)
        p = tmp_path / f"{len(calls)}.fits"
        write_cutout(p, star_ujy=1000.0, wavelength=1.0 + len(calls) * 0.1)
        return p

    monkeypatch.setattr(photometry, "_spectrum_cutout", fake_cutout)
    exps = [Exposure(obs_id=f"o{k}", collection="spherex_dr1", detector=1, mjd_start=60800.0 + k,
                     mjd_mid=60800.0 + k, time_utc="", exptime_s=100, wave_min_um=0.7, wave_max_um=1.0, epoch=1,
                     fits_url=f"https://x/{k}.fits", publisher_did=f"d{k}") for k in range(4)]
    monkeypatch.setattr(FS.build, "cached_exposures", lambda ra, dec: (exps, {}))
    fs = FS.measure_field(_target(), processes=0)
    assert len(calls) == 4 and len(fs["exposures"]) == 4 and len(fs["sources"]) == 2
    assert fs["flux_ujy"][0][0] == pytest.approx(1000.0, rel=0.03)       # HD 1 sits on the synthetic star
    sp = FS.source_spectrum(fs, 0)
    assert len(sp["frames"]) == 4 and sp["name"] == "HD 1"
    assert FS.measure_field(_target(), processes=0) == fs and len(calls) == 4     # cached


# --- T86 --------------------------------------------------------------------------------------------------

def _field(n=60, seed=3, odd=None):
    """A synthetic field-spectra result: n stars of different temperatures (power-law slopes) seen in 3 epochs,
    2 % noise; odd = {index: function(wavelength) -> factor} for peculiar sources."""
    rng = np.random.default_rng(seed)
    exps, rows = [], []
    for ep in (1, 2, 3):
        for k in range(80):
            exps.append({"frame_id": f"e{ep}-{k}", "epoch": ep, "mjd": 60800 + 180 * ep + k * 0.1, "detector": 1,
                         "time_utc": ""})
    wl = rng.uniform(0.75, 5.0, (n, len(exps)))
    slope = rng.uniform(-2.2, -1.2, n)
    level = 10 ** rng.uniform(3, 4, n)
    flux = level[:, None] * wl ** slope[:, None]
    for i, f in (odd or {}).items():
        flux[i] *= f(wl[i])
    flux *= 1 + 0.02 * rng.normal(size=flux.shape)
    err = 0.02 * flux
    srcs = [{"id": f"s{i}", "name": f"star {i}", "source": "gaia_dr3", "otype": "*", "mag": 12.0,
             "ra_deg": 10 + i * 0.01, "dec_deg": 20.0} for i in range(n)]
    tolist = lambda a: [[round(float(v), 4) for v in row] for row in a]
    return {"sources": srcs, "exposures": exps, "flux_ujy": tolist(flux), "err_ujy": tolist(err),
            "wavelength_um": tolist(wl), "bandwidth_um": tolist(wl * 0.02), "masked_fraction": [[0.0] * len(exps)] * n,
            "n_exposures": len(exps), "aperture_px": 3, "annulus_px": [5, 8], "note": ""}


def test_ordinary_field_is_quiet():
    out = SO.find_outliers(_field())
    assert out["items"] == [] and out["summary"].startswith("Nothing out of the ordinary")


def test_ir_excess_and_ice_dip_found():
    excess = lambda w: 1 + 0.8 * np.clip((w - 2.8) / 2.0, 0, None)        # warm dust: rising beyond ~3 µm
    ice = lambda w: 1 - 0.5 * np.exp(-0.5 * ((w - 3.05) / 0.08) ** 2)    # water ice at 3.05 µm
    out = SO.find_outliers(_field(odd={5: excess, 17: ice}))
    names = [it["name"] for it in out["items"]]
    assert set(names[:2]) == {"star 5", "star 17"} and len(names) == 2
    by = {it["name"]: it for it in out["items"]}
    d = by["star 5"]["deviations"][0]
    assert d["sign"] > 0 and d["um_max"] > 4.5 and "long wavelengths" in d["meaning"]
    d = by["star 17"]["deviations"][0]
    assert d["sign"] < 0 and d["um_min"] < 3.05 < d["um_max"] and "water ice" in d["meaning"]


def test_saturated_source_not_judged_and_said_why():
    fs = _field()
    fs["masked_fraction"] = [row[:] for row in fs["masked_fraction"]]
    fs["masked_fraction"][4] = [0.1] * len(fs["exposures"])              # flagged core in every exposure
    out = SO.find_outliers(fs)
    nj = {n["name"]: n["why"] for n in out["not_judged"]}
    assert nj["star 4"].startswith("saturated") and out["n_judged"] == 59


def test_isolated_galaxy_is_not_scored_against_stars():
    fs = _field(odd={5: lambda w: 1 + 0.8 * np.clip((w - 2.8) / 2.0, 0, None)})
    fs["sources"][5]["otype"] = "G"
    out = SO.find_outliers(fs)
    assert not out["items"]
    assert out["n_judged"] == 59
    assert any(n["id"] == "s5" and "peers" in n["why"] for n in out["not_judged"])


def test_chart_data_points_and_envelope():
    excess = lambda w: 1 + 1.5 * np.clip((w - 2.8) / 2.0, 0, None)
    out = SO.find_outliers(_field(odd={5: excess}))
    pts = {p["id"]: p for p in out["points"]}
    env = out["groups"]["stars"]["envelope"]
    assert len(pts) == 60 and len(out["bands_um"]) == 22 and len(env["p16"]) == 22
    assert pts["s5"]["outlier"] and not pts["s6"]["outlier"]
    ordinary_y = np.median([p["y"] for p in pts.values() if not p["outlier"]])
    assert pts["s5"]["y"] > ordinary_y + 0.2          # more light at 3.4-4.8 µm: up in the colour diagram
    assert all(a <= b for a, b in zip(env["p16"], env["p84"]) if a is not None and b is not None)


def test_separate_galaxy_population_has_own_model():
    fs = _field(n=80)
    for i in range(60, 80):
        fs["sources"][i]["otype"] = "QSO" if i == 60 else "G"
        # Strongly different slope, but ordinary within this population.
        fs["flux_ujy"][i] = [f * w ** 2 for f, w in zip(fs["flux_ujy"][i], fs["wavelength_um"][i])]
        fs["err_ujy"][i] = [f * .02 for f in fs["flux_ujy"][i]]
    out = SO.find_outliers(fs)
    assert not out["items"]
    assert out["groups"]["galaxies"]["n_sources"] == 20
    assert out["n_judged"] == 80
    assert {p["peer_group"] for p in out["points"]} == {"stars", "galaxies"}


def test_cross_population_blend_is_still_flagged():
    fs = _field(odd={5: lambda w: 1 + .8 * np.clip((w - 2.8) / 2, 0, None)})
    fs['sources'][59].update(otype='G', ra_deg=fs['sources'][5]['ra_deg'] + 1 / 3600)
    out = SO.find_outliers(fs)
    match = next(it for it in out['items'] if it['id'] == 's5')
    assert match['peer_group'] == 'stars'
    assert any('blended' in c for c in match['caveats'])
