"""T75: pipeline.variability on synthetic fields (the T86 field generator)."""
from pipeline.test_fieldspectra import _field
from pipeline.variability import find_variables


def _scale(fs, i, epoch, factor):
    for k, e in enumerate(fs["exposures"]):
        if e["epoch"] == epoch:
            fs["flux_ujy"][i][k] *= factor
            fs["err_ujy"][i][k] *= factor
    return fs


def test_steady_field_is_quiet():
    out = find_variables(_field())
    assert out["items"] == [] and out["pairs"] == 3 and out["n_judged"] == 60


def test_a_brightening_source_is_found_and_described():
    fs = _scale(_field(), 7, 3, 1.4)
    out = find_variables(fs)
    assert [v["name"] for v in out["items"]] == ["star 7"]
    v = out["items"][0]
    assert v["sign"] == 1 and 30 < v["pct"] < 50 and v["epochs"][1] == 3 and v["bands"] >= 10
    assert v["reason"].startswith("Brighter by 4") and "same wavelength" in v["reason"]


def test_calibration_drift_of_a_whole_epoch_is_not_variability():
    fs = _field()
    for i in range(len(fs["sources"])):
        _scale(fs, i, 2, 1.15)                    # every star 15 % brighter in epoch 2: calibration, not the sky
    assert find_variables(fs)["items"] == []


def test_small_changes_and_known_variables():
    fs = _scale(_field(), 3, 2, 1.06)             # 6 %: below MIN_PCT
    assert find_variables(fs)["items"] == []
    fs = _scale(_field(), 4, 2, 0.6)
    fs["sources"][4]["otype"] = "Mi*"
    v = find_variables(fs)["items"][0]
    # a dip in epoch 2 is "fainter 1 → 2" or "brighter 2 → 3": either pair is right
    assert v["known_variable"] and 2 in v["epochs"] and "Catalogued as variable" in v["reason"]


def test_a_fast_pulsator_is_found_within_the_epochs():
    import math
    fs = _field()
    for k in range(len(fs["exposures"])):        # ±30 % over hours: epoch averages stay put, the scatter doesn't
        f = 1 + 0.3 * math.sin(k * 2.399)
        fs["flux_ujy"][11][k] *= f
        fs["err_ujy"][11][k] *= f
    out = find_variables(fs)
    assert [v["name"] for v in out["items"]] == ["star 11"]
    v = out["items"][0]
    assert v["kind"] == "within" and v["pct"] > 15 and v["reason"].startswith("Varies within days")
