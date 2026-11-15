"""T135: pipeline.srcfind on synthetic images (no files, no network)."""
import json

import numpy as np

from pipeline import fieldspectra, srcfind
from pipeline.build import output_wcs


def _star(img, r, c, amp, sig=1.2):
    yy, xx = np.mgrid[0:img.shape[0], 0:img.shape[1]]
    img += amp * np.exp(-((yy - r) ** 2 + (xx - c) ** 2) / (2 * sig ** 2))


def test_epoch_median_drops_a_one_epoch_transient():
    shape = (40, 40)
    sums, counts = {}, {}
    for ep in (1, 2, 3):
        img = np.zeros(shape, np.float32)
        _star(img, 20, 20, 10.0)                          # a real source: in every epoch
        if ep == 2:
            _star(img, 10, 30, 50.0)                      # an asteroid: one epoch only
        sums[(0, ep)], counts[(0, ep)] = img, np.ones(shape, np.uint16)
    imgs, covs = srcfind.deep_images(sums, counts)
    assert imgs[0][20, 20] > 9 and abs(imgs[0][10, 30]) < 1e-3 and not covs[1].any()


def test_red_uncatalogued_source_kept_catalogued_bright_glow_and_edge_left_out():
    n = 80
    rng = np.random.default_rng(1)
    target = {"id": "t", "center": {"ra_deg": 133.76, "dec_deg": -7.24}, "image": {"width": n}, "size_arcmin": 8,
              "frames": [{"mjd": 61000.0}]}
    w = output_wcs(133.76, -7.24, n)
    sky = lambda x, y: tuple(float(v) for v in w.all_pix2world(x, n - 1 - y, 0))      # noqa: E731
    imgs = []
    for g in range(4):
        img = rng.normal(0, 1.0, (n, n)).astype(np.float32) + 5.0                     # sky + noise
        _star(img, 20, 20, 40.0)                          # catalogued star: everywhere
        if g >= 2:
            _star(img, 50, 30, 15.0)                      # cold brown dwarf: only at 3.8-5 µm
        _star(img, 40, 60, 30.0)                          # beside a bright catalogued star (its glow)
        _star(img, 1, 40, 30.0)                           # at the edge
        imgs.append(img)
    covs = [np.ones((n, n), bool) for _ in range(4)]
    snrs = [srcfind.snr_map(d, c) for d, c in zip(imgs, covs)]
    peaks = srcfind.find_peaks(snrs, covs)
    assert not any(p["y"] < srcfind.EDGE_PX for p in peaks)                        # edge out
    ra1, dec1 = sky(20, 20)
    rab, decb = sky(62, 42)                                                         # bright star 2-3 px away
    cat = [{"id": "l1", "name": "HD 1", "mag": 11.0, "ra_deg": ra1, "dec_deg": dec1, "mjd0": 61000.0,
            "dra_deg_day": 0.0, "ddec_deg_day": 0.0},
           {"id": "l2", "name": "HD 2", "mag": 6.0, "ra_deg": rab, "dec_deg": decb, "mjd0": 61000.0,
            "dra_deg_day": 0.0, "ddec_deg_day": 0.0}]
    kept = srcfind._keep(peaks, target, cat, 61000.0)
    assert len(kept) == 1, kept
    s = kept[0]
    assert s["source"] == "spherex" and s["id"] == "x001" and s["red"] and "only at 3.8–5 µm" in s["kind"]
    ra, dec = sky(30, 50)
    assert abs(s["ra_deg"] - ra) * 3600 < 8 and abs(s["dec_deg"] - dec) * 3600 < 8
    assert s["name"].startswith("SPHEREx J0855")


def test_stored_only_without_compute_and_found_again_when_labels_change(tmp_path, monkeypatch):
    monkeypatch.setattr(fieldspectra, "ROOT", tmp_path)
    target = {"id": "t", "center": {"ra_deg": 1.0, "dec_deg": 1.0}, "image": {"width": 10}}
    cat = [{"id": "l1", "ra_deg": 1.0, "dec_deg": 1.0}]
    assert srcfind.spherex_sources(target, cat) == []                               # nothing stored: no work
    calls = []
    monkeypatch.setattr(srcfind, "_find", lambda t, c, p=None: calls.append(1) or {"sources": [{"id": "x001"}]})
    assert srcfind.spherex_sources(target, cat, compute=True) == [{"id": "x001"}]
    assert srcfind.spherex_sources(target, cat) == [{"id": "x001"}] and len(calls) == 1   # stored
    assert srcfind.spherex_sources(target, cat + [{"id": "l2", "ra_deg": 2.0, "dec_deg": 2.0}]) == []   # labels changed
    assert json.loads((tmp_path / "t.sources.json").read_text())["version"] == srcfind.VERSION


def test_spherex_only_judged_with_stars_and_uncatalogued_listed_first(monkeypatch):
    from pipeline import catcheck
    from pipeline.spectral_outliers import peer_group
    assert peer_group({"source": "spherex", "otype": None, "kind": "SPHEREx-only source"}) == "stars"
    sources = [{"id": "l1", "source": "simbad"}, {"id": "x001", "source": "spherex", "ra_deg": 1.0, "dec_deg": 1.0},
               {"id": "x002", "source": "spherex", "ra_deg": 2.0, "dec_deg": 2.0}]
    monkeypatch.setattr(catcheck, "check", lambda d, pos, cats, year: {
        "matches": [{"simbad": None, "gaia": {"name": "Gaia DR3 1"}}, {"simbad": None, "gaia": None}], "failed": []})
    items = srcfind.tag_items([{"id": "l1"}, {"id": "x001"}, {"id": "x002"}], "/tmp/x", sources, 2026.0)
    assert [it["id"] for it in items] == ["x002", "l1", "x001"]
    assert items[0]["tag"] == "new" and items[2]["tag"] == "untyped" and "tag" not in items[1]
