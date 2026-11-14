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
