"""pytest pipeline/test_build.py  (offline: no IRSA calls)."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from astropy.io import fits
from PIL import Image

from pipeline.build import cutout_url, output_wcs, render_png, select, wavelength_at


def _exp(epoch, det, mjd):
    return SimpleNamespace(epoch=epoch, detector=det, mjd_mid=mjd)


def test_select_spreads_per_epoch_and_detector():
    ex = [_exp(1, 1, 60000 + i) for i in range(10)] + [_exp(2, 1, 60200)] + [_exp(1, 6, 60001)]
    got = select(ex, per_group=2)
    assert [(e.epoch, e.detector, e.mjd_mid) for e in got] == \
        [(1, 1, 60000), (1, 6, 60001), (1, 1, 60009), (2, 1, 60200)]


def test_cutout_url():
    assert cutout_url("https://x/y.fits", 1.5, -2.25, 0.3) == "https://x/y.fits?center=1.500000,-2.250000&size=0.3000deg"


def test_output_grid_north_up_east_left():
    w = output_wcs(150.0, 2.0, 101)
    ra_c, dec_c = w.all_pix2world(50, 50, 0)
    assert abs(ra_c - 150) < 1e-9 and abs(dec_c - 2) < 1e-9
    ra_r, _ = w.all_pix2world(60, 50, 0)
    _, dec_u = w.all_pix2world(50, 60, 0)
    assert ra_r < 150 and dec_u > 2      # east is left, north is up (FITS y)


def test_wavelength_at_uses_detector_offset():
    gx = gy = np.array([1, 1021, 2041])
    vals = np.zeros((3, 3, 2), np.float32)
    vals[..., 0] = np.array([1.0, 2.0, 3.0])[None, :]    # wavelength grows with detector x
    vals[..., 1] = 0.05
    table = fits.BinTableHDU.from_columns([
        fits.Column("X", "3J", array=gx[None]), fits.Column("Y", "3J", array=gy[None]),
        fits.Column("VALUES", "18E", dim="(2,3,3)", array=vals[None])], name="WCS-WAVE")
    img = fits.ImageHDU(np.zeros((5, 5)), name="IMAGE")
    img.header.update({"CRPIX1W": -1019.0, "CRPIX2W": 0.0, "CRVAL1W": 1, "CRVAL2W": 1})
    hd = fits.HDUList([fits.PrimaryHDU(), img, table])
    # cutout pixel x0=0 -> detector x = 0 + 1 + 1019 + 1 = 1021 -> wavelength 2.0
    wave, bw = wavelength_at(hd, 0.0, 0.0)
    assert abs(wave - 2.0) < 1e-6 and abs(bw - 0.05) < 1e-6


def test_render_png_alpha_marks_no_data(tmp_path):
    a = np.random.default_rng(0).normal(size=(20, 20))
    a[:5] = np.nan
    render_png(a, tmp_path / "f.png")
    im = np.array(Image.open(tmp_path / "f.png"))
    assert im.shape == (20, 20, 2)
    assert (im[:5, :, 1] == 0).all() and (im[5:, :, 1] == 255).all()


# -- T26 retry, T28 cutout reuse, T27 exposure cache ---------------------------------------------

class _Resp:
    def __init__(self, status, content=b""):
        self.status_code, self.content, self.text = status, content, content.decode(errors="replace")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def test_retry_on_503_then_success(monkeypatch):
    import requests
    from pipeline import build

    answers = iter([_Resp(503, b"Server busy, retry later."), _Resp(200, b"oops"), _Resp(200, b"SIMPLE  = T")])
    monkeypatch.setattr(requests, "get", lambda url, timeout: next(answers))
    waits = []
    assert build._get_with_retry("u", sleep=waits.append) == b"SIMPLE  = T"
    assert len(waits) == 2


def test_retry_gives_up(monkeypatch):
    import pytest
    import requests
    from pipeline import build

    monkeypatch.setattr(requests, "get", lambda url, timeout: _Resp(503, b"busy"))
    with pytest.raises(RuntimeError, match="gave up"):
        build._get_with_retry("u", sleep=lambda s: None)


def test_cutout_reuse_across_fov(monkeypatch, tmp_path):
    from pipeline import build

    calls = []
    monkeypatch.setattr(build, "_get_with_retry", lambda url: calls.append(url) or b"SIMPLE  = T")
    p1 = build.fetch("https://x/a.fits", 10.0, 20.0, 0.2, raw_root=tmp_path)    # -> MIN_CUTOUT_DEG
    assert float(p1.stem) == build.MIN_CUTOUT_DEG and len(calls) == 1
    assert build.fetch("https://x/a.fits", 10.0, 20.0, 0.385, raw_root=tmp_path) == p1   # smaller/equal: cache
    p2 = build.fetch("https://x/a.fits", 10.0, 20.0, 1.5, raw_root=tmp_path)    # larger: download
    assert len(calls) == 2 and float(p2.stem) == 1.5
    assert build.fetch("https://x/a.fits", 10.0, 20.0, 0.8, raw_root=tmp_path) == p2     # smallest that fits
    assert len(calls) == 2


def test_exposure_list_cached(monkeypatch, tmp_path):
    from pipeline import build
    from pipeline.query import Exposure

    e = Exposure("o", "spherex_dr1", 1, 1.0, 1.5, "2025-01-01T00:00:00Z", 100.0, 0.75, 1.1, 1, "https://x", "d")
    calls = []
    monkeypatch.setattr(build, "find_exposures", lambda ra, dec: calls.append(1) or ([e], {"service": "s", "query": "q", "retrieved_utc": "t"}))
    a, _ = build.cached_exposures(1.0, 2.0, raw_root=tmp_path)
    b, prov = build.cached_exposures(1.0, 2.0, raw_root=tmp_path)
    assert a == b == [e] and prov["retrieved_utc"] == "t" and len(calls) == 1
    build.cached_exposures(1.0, 2.0, refresh=True, raw_root=tmp_path)
    assert len(calls) == 2


def test_fetch_prefers_s3_and_falls_back(monkeypatch, tmp_path):
    from pipeline import build, s3

    def fake_s3(url, ra, dec, size, dest):
        dest.write_bytes(b"SIMPLE  = T s3")
        return dest
    monkeypatch.setattr(s3, "fetch_cutout", fake_s3)
    monkeypatch.setattr(build, "_get_with_retry", lambda url: (_ for _ in ()).throw(AssertionError("IRSA used")))
    p = build.fetch("https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/a.fits", 1.0, 2.0, 0.3, raw_root=tmp_path)
    assert p.read_bytes().endswith(b"s3")

    monkeypatch.setattr(s3, "fetch_cutout", lambda *a: (_ for _ in ()).throw(RuntimeError("404")))
    monkeypatch.setattr(build, "_get_with_retry", lambda url: b"SIMPLE  = T irsa")
    p = build.fetch("https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/b.fits", 1.0, 2.0, 0.3, raw_root=tmp_path)
    assert p.read_bytes().endswith(b"irsa")


def test_s3_url():
    from pipeline.s3 import s3_url
    assert s3_url("https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/level2/W/v/1/f.fits") == \
        "https://nasa-irsa-spherex.s3.amazonaws.com/dr1/level2/W/v/1/f.fits"
    assert s3_url("https://example.org/x.fits") is None
