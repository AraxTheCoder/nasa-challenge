"""T51: detect.run offline (fake JPL)."""
import json
import re

from detect.known_objects import Jpl
from detect.run import detect, detect_target
from detect.test_known_objects import TARGET, FakeJpl

# web/objects.js detectionRan(): a provenance service matching this means "mover detection ran"
VIEWER_DETECTION_RAN = re.compile(r"\bdetect(ion|\.run)?\b", re.I)


def _target(**extra):
    return {**TARGET, "frames": list(TARGET["frames"]), "provenance": [], "known_objects": [],
            "detections": [], "labels": [], **extra}


def test_fills_known_objects_without_claiming_mover_detection():
    t = detect_target(_target(), FakeJpl(), vmag_lim=19)
    assert [o["name"] for o in t["known_objects"]] == ["6779 Perrine (1990 DM1)"]
    assert t["detections"] == []
    assert not any(VIEWER_DETECTION_RAN.search(p["service"]) for p in t["provenance"])


class BrokenJpl(Jpl):
    def __init__(self):
        super().__init__(session=None)

    def spherex_states(self, jds):
        raise ConnectionError("ssd.jpl.nasa.gov unreachable")


def test_jpl_failure_keeps_the_build():
    t = detect_target(_target(), BrokenJpl())
    assert t["known_objects"] == []
    assert any("failed" in p["service"] and "unreachable" in p["query"] for p in t["provenance"])
    assert not any(VIEWER_DETECTION_RAN.search(p["service"]) for p in t["provenance"])


def test_classifies_when_there_are_detections():
    t = detect_target(_target(), FakeJpl(), vmag_lim=19)
    ko = t["known_objects"][0]
    t["detections"] = [{"id": "d1", "track": [dict(p) for p in ko["positions"]]}]
    t = detect_target(t, FakeJpl(), vmag_lim=19)
    assert t["detections"][0].get("status") in ("known", "unknown", "artifact")


def test_synthetic_fixture_untouched():
    t = _target(synthetic=True, known_objects=[{"name": "fake"}])
    assert detect_target(t, FakeJpl())["known_objects"] == [{"name": "fake"}]


def test_detect_writes_target_json(tmp_path):
    (tmp_path / "target.json").write_text(json.dumps(_target()), encoding="utf-8")
    detect(tmp_path, FakeJpl(), vmag_lim=19)
    t = json.loads((tmp_path / "target.json").read_text(encoding="utf-8"))
    assert len(t["known_objects"]) == 1
    assert not (tmp_path / "target.json.tmp").exists()


class _Resp:
    def __init__(self, status, body=None, headers=None):
        self.status_code, self._body, self.headers = status, body or {}, headers or {}

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class _Session:
    def __init__(self, answers):
        self.answers, self.calls, self.headers = list(answers), 0, {}

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        return self.answers.pop(0)


def test_sb_ident_waits_out_429_then_caches(tmp_path, monkeypatch):
    import detect.known_objects as ko
    slept = []
    monkeypatch.setattr(ko.time, "sleep", slept.append)
    monkeypatch.setattr(ko, "CACHE_DIR", tmp_path)
    ok = {"fields_first": ["Object name"], "data_first_pass": [["433 Eros"]]}
    s = _Session([_Resp(429, headers={"Retry-After": "300"}), _Resp(200, ok)])
    jpl = ko.Jpl(session=s)
    args = (2460900.5, [1, 2, 3, 4, 5, 6], 180.0, 0.0, 0.3, 20)
    assert jpl.candidates(*args) == ["433 Eros"]
    assert s.calls == 2 and slept == [301]           # waited as long as JPL said, once
    assert jpl.candidates(*args) == ["433 Eros"]     # second time from the disk cache
    assert s.calls == 2 and len(jpl.log) == 2         # still in provenance


def test_sb_ident_rate_window(monkeypatch):
    import detect.known_objects as ko
    now = [1000.0]
    monkeypatch.setattr(ko.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(ko.time, "sleep", lambda s: now.__setitem__(0, now[0] + s))
    monkeypatch.setattr(ko, "_sb_sent", ko.deque())
    for _ in range(ko.SB_IDENT_PER_WINDOW):
        ko._sb_ident_slot()
    assert now[0] == 1000.0                           # the first 18 go straight out
    ko._sb_ident_slot()
    assert now[0] > 1000.0 + ko.SB_IDENT_WINDOW_S     # the 19th waits for the window
