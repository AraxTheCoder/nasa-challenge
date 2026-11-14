"""T73–T75: pipeline.survey offline (fake Live API, synthetic field spectra)."""
import json

import jsonschema

from pipeline import survey
from pipeline.test_fieldspectra import _field
from pipeline.test_variability import _scale

FIELD = {"name": "Test field", "ra_deg": 10.0, "dec_deg": 20.0, "size_arcmin": 15, "group": "test"}
OUTLIERS = {"status": "ready", "summary": "1 of 60 sources stand out", "n_sources": 60, "n_judged": 60, "items": [
    {"id": "s5", "name": "Gaia DR3 5", "otype": None, "ra_deg": 10.05, "dec_deg": 20.0, "score": 23.0, "chi2": 9.0,
     "reason": "Brighter than ordinary sources here at 3.4–4.8 µm (+40 %): warm dust?", "caveats": [],
     "deviations": [{"um_min": 3.4, "um_max": 4.8, "sign": 1, "pct": 40.0, "z": 9.0, "n_bands": 4,
                     "epochs_agree": 3, "epochs_seen": 3, "meaning": "warm dust"}]},
    {"id": "s9", "name": "2MASS J1", "otype": "BD*", "ra_deg": 10.09, "dec_deg": 20.0, "score": 12.0, "chi2": 5.0,
     "reason": "Fainter at 3.2–3.45 µm", "caveats": ["blended: X is 10″ away"],
     "deviations": [{"um_min": 3.2, "um_max": 3.45, "sign": -1, "pct": -30.0, "z": 5.0, "n_bands": 2,
                     "epochs_agree": 2, "epochs_seen": 3, "meaning": "methane absorption (3.3 µm): a T/Y brown dwarf?"}]}]}


class FakeApi:
    """/api/target: 202 once then ready; /labels ready; /spectral-outliers building until started + polled."""
    def __init__(self):
        self.calls = []

    def __call__(self, url, params=None, timeout=None):
        self.calls.append((url.split("/api/")[1], dict(params or {})))
        path = url.split("/api/")[1]
        n = sum(1 for c in self.calls if c[0] == path)
        if path == "target":
            return _R(202 if n == 1 else 200, {"status": "building" if n == 1 else "ready", "id": "c1-p1-s15"})
        if path.endswith("/labels"):
            return _R(200, {"status": "ready"})
        return _R(202, {"status": "building"}) if n == 1 else _R(200, OUTLIERS)


class _R:
    def __init__(self, code, body):
        self.status_code, self._b, self.headers = code, body, {"content-type": "application/json"}

    def json(self):
        return self._b


def test_run_field_drives_the_api(monkeypatch):
    monkeypatch.setattr(survey, "POLL_S", 0)
    api = FakeApi()
    r = survey.run_field("http://x", FIELD, get=api, log=lambda *a: None)
    assert r["target_id"] == "c1-p1-s15" and r["outliers"] is OUTLIERS
    starts = [p for path, p in api.calls if path.endswith("spectral-outliers")]
    assert starts[0] == {"start": 1} and starts[1] == {}          # start once, then poll


def test_judge_and_index(tmp_path):
    fs = _scale(_field(), 7, 3, 1.4)
    (tmp_path / "field_spectra").mkdir()
    (tmp_path / "field_spectra" / "c1-p1-s15.json").write_text(json.dumps(fs))
    res = survey.judge_field(tmp_path, FIELD, "c1-p1-s15", OUTLIERS)
    by = {c["id"]: c for c in res["candidates"]}
    s5, s9, v7 = by["c1-p1-s15-s-s5"], by["c1-p1-s15-s-s9"], by["c1-p1-s15-v-s7"]
    assert s5["class"] == "spectral" and s5["known"] is None and s5["lam_um"] == 4.1 and s5["score"] > 0.7
    assert s9["class"] == "brown_dwarf" and s9["known"] == "2MASS J1" and s9["score"] < 0.3 and "Caveats" in s9["reason"]
    assert v7["class"] == "variable" and v7["reason"].startswith("Brighter by 4")
    idx = survey.write_index(tmp_path, "http://x")
    schema = json.loads((survey.REPO / "docs" / "discoveries.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(idx, schema)
    assert idx["synthetic"] is False and [c["score"] for c in idx["candidates"]] == sorted(
        (c["score"] for c in idx["candidates"]), reverse=True)


def test_pilot_fields():
    f = survey.pilot_fields()
    assert len(f) >= 20 and f[0]["group"] == "official test field" and all(x["size_arcmin"] >= 15 for x in f)
