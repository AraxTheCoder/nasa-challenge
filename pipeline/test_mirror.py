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
    mirror.build(root)
    asked = []
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
