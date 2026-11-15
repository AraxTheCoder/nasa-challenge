"""Offline tests for pipeline.photometry (T49) and its API route, on synthetic SPHEREx-like cutouts."""
from __future__ import annotations

import json
import math

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS

from pipeline import build
from pipeline.photometry import image_url, measure, measure_cutout

RA0, DEC0 = 76.9566, 30.4013
SCALE_DEG = 6.15 / 3600
PIX_SR = (SCALE_DEG * math.pi / 180) ** 2
N = 64


def write_cutout(path, star_ujy=1000.0, zodi=0.5, flag_core=False, wavelength=1.5, star_offset=(0.0, 0.0), s3=False):
    """A 64x64 SPHEREx-like cutout: IMAGE (MJy/sr) with a Gaussian star of known total flux, ZODI,
    VARIANCE, FLAGS and a WCS-WAVE table, TAN WCS centred on (RA0, DEC0)."""
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [RA0, DEC0]
    w.wcs.crpix = [N / 2 + 0.5, N / 2 + 0.5]
    w.wcs.cdelt = [-SCALE_DEG, SCALE_DEG]
    hdr = w.to_header()
    hdr.update({"CRPIX1W": 1.0, "CRPIX2W": 1.0, "CRVAL1W": 1, "CRVAL2W": 1, "BUNIT": "MJy/sr"})
    yy, xx = np.mgrid[0:N, 0:N]
    cx, cy = N / 2 - 0.5 + star_offset[0], N / 2 - 0.5 + star_offset[1]
    g = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * 1.0 ** 2))
    g /= g.sum()
    star_mjy_sr = star_ujy / 1e12 / PIX_SR  # total flux spread over pixels, in MJy/sr per pixel
    image = zodi + g * star_mjy_sr
    flags = np.zeros((N, N), np.int32)
    if flag_core:
        flags[int(cy) - 1:int(cy) + 2, int(cx) - 1:int(cx) + 2] = 1  # bit 0 is in HW_MASK
    gx, gy = np.linspace(1, N, 9).astype(np.int32), np.linspace(1, N, 14).astype(np.int32)
    vals = np.zeros((14, 9, 2), np.float32)
    vals[..., 0], vals[..., 1] = wavelength, 0.04
    table = fits.BinTableHDU.from_columns([
        fits.Column(name="X", format="9J", array=gx[None, :]),
        fits.Column(name="Y", format="14J", array=gy[None, :]),
        fits.Column(name="VALUES", format="252E", dim="(2,9,14)", array=vals[None, ...]),
    ], name="WCS-WAVE")
    rng = np.random.default_rng(1)
    if s3:  # since T33: AWS cutouts carry only IMAGE, FLAGS, WCS-WAVE (no VARIANCE, no ZODI)
        image = image + rng.normal(0, 0.002, image.shape)
        hdus = [fits.PrimaryHDU(header=fits.Header({"S3SRC": "test"})), fits.ImageHDU(image.astype(np.float32), hdr, name="IMAGE"),
                fits.ImageHDU(flags, name="FLAGS"), table]
    else:
        hdus = [fits.PrimaryHDU(), fits.ImageHDU(image.astype(np.float32), hdr, name="IMAGE"), fits.ImageHDU(flags, name="FLAGS"),
                fits.ImageHDU(np.full((N, N), 1e-4, np.float32), name="VARIANCE"),
                fits.ImageHDU(np.full((N, N), zodi, np.float32), name="ZODI"), table]
    fits.HDUList(hdus).writeto(path, overwrite=True)


def test_image_url_maps_irsa_and_s3_back_to_the_image():
    irsa = "https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/level2/x/img.fits"
    assert image_url(irsa + "?center=76.9,30.4&size=0.4deg") == irsa
    assert image_url("https://nasa-irsa-spherex.s3.amazonaws.com/dr1/level2/x/img.fits#rows=10-200") == irsa


def test_known_star_flux_and_wavelength(tmp_path):
    write_cutout(tmp_path / "c.fits", star_ujy=1000.0, wavelength=1.5)
    m = measure_cutout(tmp_path / "c.fits", RA0, DEC0)
    assert m["flux_ujy"] == pytest.approx(1000.0, rel=0.02)   # zodi removed, Gaussian sigma 1 px inside r=3
    assert m["err_ujy"] > 0 and not m["masked"]
    assert m["wavelength_um"] == pytest.approx(1.5, abs=1e-3) and m["bandwidth_um"] == pytest.approx(0.04, abs=1e-3)


def test_s3_cutout_without_variance_or_zodi(tmp_path):
    # the zodiacal light (here 0.5 MJy/sr) is removed by the local annulus; errors from its scatter
    write_cutout(tmp_path / "c.fits", star_ujy=1000.0, s3=True)
    m = measure_cutout(tmp_path / "c.fits", RA0, DEC0)
    assert m["flux_ujy"] == pytest.approx(1000.0, rel=0.05) and m["err_ujy"] > 0 and not m["masked"]


def test_empty_sky_measures_about_zero(tmp_path):
    write_cutout(tmp_path / "c.fits", star_ujy=1000.0)
    off = measure_cutout(tmp_path / "c.fits", RA0 + 20 * SCALE_DEG / math.cos(math.radians(DEC0)), DEC0)
    assert abs(off["flux_ujy"]) < 5


def test_flagged_core_is_masked(tmp_path):
    write_cutout(tmp_path / "c.fits", flag_core=True)
    assert measure_cutout(tmp_path / "c.fits", RA0, DEC0)["masked"]


def test_position_off_the_cutout_is_none(tmp_path):
    write_cutout(tmp_path / "c.fits")
    assert measure_cutout(tmp_path / "c.fits", RA0 + 1.0, DEC0) is None


def _target_with_cache(tmp_path, fluxes):
    """A target whose frames point at cached cutouts laid out exactly like pipeline.build caches them."""
    raw = tmp_path / "raw"
    frames = []
    for i, (flux, wave, epoch) in enumerate(fluxes):
        url = f"https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/level2/f{i}.fits"
        d = build._cutout_dir(url, RA0, DEC0, raw)
        d.mkdir(parents=True)
        write_cutout(d / "0.4000.fits", star_ujy=flux, wavelength=wave)
        frames.append({"id": f"f{i:03d}", "mjd": 60900.0 + 180 * (epoch - 1) + i * 0.01, "epoch": epoch,
                       "time_utc": "2025-08-15T00:00:00Z", "detector": 1, "wavelength_um": wave,
                       "source_url": f"{url}?center={RA0},{DEC0}&size=0.4deg", "image": f"frames/f{i:03d}.png"})
    target = {"id": "t", "synthetic": False, "center": {"ra_deg": RA0, "dec_deg": DEC0},
              "image": {"width": 146, "height": 146, "pixel_scale_arcsec": 6.15}, "frames": frames}
    return target, raw


def test_measure_all_frames_light_curve(tmp_path):
    target, raw = _target_with_cache(tmp_path, [(1000, 1.2, 1), (1500, 2.5, 1), (2000, 1.2, 2)])
    res = measure(target, RA0, DEC0, raw_root=raw)
    assert [r["frame_id"] for r in res["frames"]] == ["f000", "f001", "f002"] and res["missing"] == []
    assert [round(r["flux_ujy"] / 100) * 100 for r in res["frames"]] == [1000, 1500, 2000]
    assert res["frames"][2]["epoch"] == 2 and res["unit"] == "uJy" and "approximate" in res["note"]


def test_frames_without_cached_cutout_are_listed_as_missing(tmp_path):
    target, raw = _target_with_cache(tmp_path, [(1000, 1.2, 1)])
    target["frames"].append({**target["frames"][0], "id": "f009", "source_url": "https://irsa.ipac.caltech.edu/ibe/data/spherex/none.fits"})
    res = measure(target, RA0, DEC0, raw_root=raw)
    assert res["missing"] == ["f009"] and len(res["frames"]) == 1


def test_api_route(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from server.app import create_app

    target, raw = _target_with_cache(tmp_path, [(1000, 1.2, 1), (2000, 1.2, 2)])
    monkeypatch.setattr(build, "RAW_ROOT", raw)
    cache = tmp_path / "targets"
    (cache / "t").mkdir(parents=True)
    (cache / "t" / "target.json").write_text(json.dumps(target))
    client = TestClient(create_app(cache))
    r = client.get("/api/targets/t/photometry")
    assert r.status_code == 200 and r.json()["status"] == "ready"
    assert [round(f["flux_ujy"] / 100) * 100 for f in r.json()["frames"]] == [1000, 2000]
    r = client.get("/api/targets/t/photometry", params={"x": 72.5, "y": 72.5})  # grid centre = field centre
    assert r.status_code == 200 and abs(r.json()["ra_deg"] - RA0) < 1e-3
    assert client.get("/api/targets/t/photometry", params={"ra": 400, "dec": 0}).status_code == 400
    assert client.get("/api/targets/nope/photometry").status_code == 404
    target["synthetic"] = True
    (cache / "t" / "target.json").write_text(json.dumps(target))
    r = client.get("/api/targets/t/photometry")
    assert r.status_code == 200 and r.json()["status"] == "no_data"


def test_measure_all_every_exposure_retry_moved_path_and_cache(tmp_path, monkeypatch):
    """T66/T83: all exposures at a position; a moved image found by a bucket listing; tiny cutouts; cached."""
    from types import SimpleNamespace

    from pipeline import photometry, s3

    exps = [SimpleNamespace(fits_url=f"u{i}", obs_id=f"o{i}", detector=1 + i % 6, epoch=1 + i // 3,
                            mjd_mid=60800.0 + i, time_utc=f"t{i}", publisher_did=f"did{i}") for i in range(6)]
    monkeypatch.setattr(photometry, "SPECTRA_ROOT", tmp_path)
    monkeypatch.setattr(build, "RAW_ROOT", tmp_path / "raw")
    monkeypatch.setattr(build, "cached_exposures", lambda ra, dec: (exps, {}))
    fetched = []

    def fake_fetch(url, ra, dec, size, dest):
        fetched.append((url, size))
        if url == "u2":
            err = RuntimeError("404 Client Error: Not Found")          # moved (reprocessed)
            err.response = SimpleNamespace(status_code=404)
            raise err
        if url == "u4":
            raise LookupError("not on the image")
        return dest

    monkeypatch.setattr(s3, "fetch_cutout", fake_fetch)
    monkeypatch.setattr(s3, "find_in_bucket", lambda url: "u2-retry" if url == "u2" else None)
    monkeypatch.setattr(photometry, "measure_cutout", lambda path, ra, dec: {
        "flux_ujy": 1.0, "err_ujy": 0.1, "wavelength_um": 1.0, "bandwidth_um": 0.02, "masked_fraction": 0.0, "masked": False})
    seen = []
    res = photometry.measure_all(10.0, 20.0, progress=lambda d, n: seen.append((d, n)), threads=2, processes=0)
    assert res["n_exposures"] == 6 and res["all_exposures"] is True
    assert sorted(f["frame_id"] for f in res["frames"]) == ["o0-D1", "o1-D2", "o2-D3", "o3-D4", "o5-D6"]
    assert res["missing"] == ["o4-D5"]
    assert seen[-1] == (6, 6)
    assert ("u2-retry", photometry.SPECTRUM_CUT_DEG) in fetched                 # found by the bucket listing
    assert all(size == photometry.SPECTRUM_CUT_DEG for _, size in fetched)     # tiny cutouts, not the 0.4 deg default
    fetched.clear()
    assert photometry.measure_all(10.0, 20.0, processes=0)["frames"] == res["frames"] and not fetched   # cached


def test_flags_in_the_aperture_are_named(tmp_path):
    """T60: every quality flag set in the aperture comes back by name, with its meaning."""
    from pipeline import flags
    write_cutout(tmp_path / "c.fits", flag_core=True)          # bit 0 on the star's core
    m = measure_cutout(tmp_path / "c.fits", RA0, DEC0)
    assert m["flags"] == ["TRANSIENT"] and m["masked_fraction"] > 0
    write_cutout(tmp_path / "d.fits")
    assert measure_cutout(tmp_path / "d.fits", RA0, DEC0)["flags"] == []
    assert flags.names((1 << 1) | (1 << 21)) == ["OVERFLOW", "SOURCE"]
    mean = flags.meanings([m, {"flags": ["SOURCE"]}])
    assert mean["TRANSIENT"]["kind"] == "bad" and mean["SOURCE"]["kind"] == "info" and "cosmic ray" in mean["TRANSIENT"]["meaning"]
