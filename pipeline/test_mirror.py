"""pytest pipeline/test_mirror.py  (offline: tiny CSVs, no IRSA)."""
from __future__ import annotations

import json

from pipeline import mirror


def _write(root):
    root.mkdir(parents=True, exist_ok=True)
    head = "obs_id,obs_collection,t_min,t_max,t_exptime,em_min,em_max,s_ra,s_dec\n"
    for d in range(1, 7):
        rows = head
        if d == 2:
            rows += "2025W35_1A_0444_1,spherex_dr1,60900.0,60900.01,100,1.1e-6,1.6e-6,150.5,2.0\n"   # covers (150,2)
            rows += "2025W35_1A_0445_1,spherex_dr1,61080.0,61080.01,100,1.1e-6,1.6e-6,153.0,2.0\n"   # 3 deg away
            rows += "2026W38_1A_0001_1,spherex_qr3,61100.0,61100.01,100,1.1e-6,1.6e-6,149.0,3.0\n"   # covers, new week
        (root / f"obscore_d{d}.csv").write_text(rows)
        (root / f"obscore_d{d}.prov.json").write_text(json.dumps({"service": "s", "query": f"q{d}", "retrieved_utc": "2026-11-14T12:00:00Z"}))
    (root / "uri_sample.csv").write_text(
        "uri\nibe/data/spherex/dr1/level2/2025W35_1A/l2b-v27-2026-230/1/level2_2025W35_1A_0001_1D1_spx_l2b-v27-2026-230.fits\n")


def test_build_and_find(tmp_path, monkeypatch):
    root = tmp_path / "mirror"
    _write(root)
    mirror.build(root, learn_weeks=False)
    asked = []
    monkeypatch.setattr(mirror, "learn_weeks_from_bucket", lambda images, index: 0)   # T57: bucket "down"
    monkeypatch.setattr(mirror, "resolve_urls", lambda dids: asked.extend(dids) or {
        d: "https://irsa.ipac.caltech.edu/ibe/data/spherex/qr3/level2/2026W38_1A/l2b-v27-2026-261/2/"
           "level2_2026W38_1A_0001_1D2_spx_l2b-v27-2026-261.fits" for d in dids})
    idx = mirror.Index(root / "index.npz")
    ex, prov = mirror.find_exposures_local(150.0, 2.0, index=idx)
    assert [e.obs_id for e in ex] == ["2025W35_1A_0444_1", "2026W38_1A_0001_1"]
    assert ex[0].fits_url.endswith("2025W35_1A/l2b-v27-2026-230/2/level2_2025W35_1A_0444_1D2_spx_l2b-v27-2026-230.fits")
    assert ex[0].publisher_did == "ivo://irsa.ipac/spherex_dr1?2025W35_1A_0444_1/D2"
    assert asked == ["ivo://irsa.ipac/spherex_qr3?2026W38_1A_0001_1/D2"]     # only the unknown week
    assert [e.epoch for e in ex] == [1, 2] and prov["retrieved_utc"] == "2026-11-14T12:00:00Z"
    # the learnt week is remembered: a second search asks TAP for nothing
    asked.clear()
    mirror.find_exposures_local(150.0, 2.0, index=mirror.Index(root / "index.npz"))
    assert asked == []


def test_unknown_week_learnt_from_the_bucket_not_tap(tmp_path, monkeypatch):
    """T57: one bucket listing per unknown week instead of a TAP query (20-145 s)."""
    from pipeline import s3
    root = tmp_path / "mirror"
    _write(root)
    mirror.build(root, learn_weeks=False)
    weeks = []
    monkeypatch.setattr(s3, "week_version", lambda rel, week: weeks.append((rel, week)) or "l2b-v27-2026-261")
    monkeypatch.setattr(mirror, "resolve_urls", lambda dids: (_ for _ in ()).throw(AssertionError("TAP asked")))
    ex, _ = mirror.find_exposures_local(150.0, 2.0, index=mirror.Index(root / "index.npz"))
    assert weeks == [("qr3", "2026W38_1A")]
    assert ex[1].fits_url.endswith("qr3/level2/2026W38_1A/l2b-v27-2026-261/2/"
                                   "level2_2026W38_1A_0001_1D2_spx_l2b-v27-2026-261.fits")
    weeks.clear()                                  # remembered in uri_learned.csv: no listing next time
    mirror.find_exposures_local(150.0, 2.0, index=mirror.Index(root / "index.npz"))
    assert weeks == []


def test_week_version_prefers_the_plain_folder(monkeypatch):
    from pipeline import s3
    p = "dr1/level2/2025W47_2A/"
    text = (f"<Prefix>{p}</Prefix><CommonPrefixes><Prefix>{p}l2b_retry-v27-2026-210/</Prefix></CommonPrefixes>"
            f"<CommonPrefixes><Prefix>{p}l2b-v27-2026-208/</Prefix></CommonPrefixes>")
    resp = type("R", (), {"text": text, "raise_for_status": lambda self: None})()
    monkeypatch.setattr(s3, "_session", lambda: type("S", (), {"get": staticmethod(lambda *a, **k: resp)})())
    assert s3.week_version("dr1", "2025W47_2A") == "l2b-v27-2026-208"
