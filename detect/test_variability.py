"""T61: brightness changes on a made-up field spectra set (no network, no files)."""
import numpy as np

from detect.variability import find_variables


def _fs(n=40, var_amp=0.6, var_otype="*", blend=False, seed=61):
    """n sources x 60 exposures (3 epochs x 2 detectors x 10); source 0 changes brightness by var_amp mag."""
    rng = np.random.default_rng(seed)
    exps, lam = [], []
    for k in range(60):
        ep, d = 1 + k // 20, 1 + (k // 10) % 2
        exps.append({"frame_id": f"e{k:02d}", "epoch": ep, "detector": d, "mjd": 61000.0 + 180 * (ep - 1) + k % 10})
        lam.append(1.0 + 0.1 * d + 0.002 * (k % 10))      # the same wavelengths come back each pass
    sources, flux, err = [], [], []
    for i in range(n):
        sources.append({"id": f"l{i:03d}", "name": f"star {i}", "otype": var_otype if i == 0 else "*",
                        "ra_deg": 150.0 + 0.01 * i, "dec_deg": 2.0, "mag": 12.0})
        base = 1000.0 * (1 + i % 5)
        f = base * (1 + rng.normal(0, 0.01, 60))
        if i == 0:
            f = f * 10 ** (-0.4 * var_amp * np.sin(np.arange(60) * 1.3))
        flux.append(f.tolist())
        err.append((0.01 * base * np.ones(60)).tolist())
    if blend:                                               # a bright neighbour 10" from source 0
        sources.append({"id": "lnb", "name": "neighbour", "otype": "*", "ra_deg": 150.0 + 10 / 3600, "dec_deg": 2.0})
        flux.append((5000.0 * np.ones(60)).tolist())
        err.append((50.0 * np.ones(60)).tolist())
    m = len(sources)
    return {"sources": sources, "exposures": exps, "flux_ujy": flux, "err_ujy": err,
            "wavelength_um": [lam] * m, "bandwidth_um": [[0.03] * 60] * m, "masked_fraction": [[0.0] * 60] * m}


def test_the_changing_star_is_found_and_only_it():
    out = find_variables(_fs())
    assert [v["id"] for v in out["variables"]] == ["l000"]
    v = out["variables"][0]
    assert v["amplitude_mag"] > 0.5 and not v["catalogued_variable"] and "new variable" in v["reason"]


def test_a_catalogued_variable_says_so():
    v = find_variables(_fs(var_otype="Mi*"))["variables"][0]
    assert v["catalogued_variable"] and "Mira" in v["reason"]


def test_small_changes_are_not_flagged():
    assert find_variables(_fs(var_amp=0.05))["variables"] == []


def test_a_bright_neighbour_means_not_judged():
    out = find_variables(_fs(blend=True))
    assert out["variables"] == [] and [b["id"] for b in out["blended"]] == ["l000"]
    assert "neighbour" in out["blended"][0]["why"]


def test_field_wide_calibration_change_is_not_variability():
    fs = _fs(var_amp=0.0)
    for row in fs["flux_ujy"]:                            # pass 3 is 30 % brighter for every star
        for k in range(40, 60):
            row[k] *= 1.3
    assert find_variables(fs)["variables"] == []


def test_masked_and_wrong_wavelength_exposures_are_not_compared():
    fs = _fs()
    fs["masked_fraction"][0] = [0.1] * 60                   # the variable's apertures all hit a flagged pixel
    assert find_variables(fs)["variables"] == []


def test_empty_field():
    assert find_variables({"sources": [], "exposures": []})["variables"] == []
