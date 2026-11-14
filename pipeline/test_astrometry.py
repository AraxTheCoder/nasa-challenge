"""T91: proper motion from synthetic SPHEREx-like exposures (offline)."""
from __future__ import annotations

import math

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS

from pipeline import astrometry as AS
from pipeline import fieldspectra as FS
from pipeline import photometry
from pipeline.query import Exposure

RA0, DEC0 = 150.0, 10.0
SCALE = 6.15 / 3600
N = 120


def _wcs(shift_px=(0.0, 0.0)):
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [RA0, DEC0]
    w.wcs.crpix = [N / 2 + 0.5 + shift_px[0], N / 2 + 0.5 + shift_px[1]]
    w.wcs.cdelt = [-SCALE, SCALE]
    return w


def _write(path, stars, pointing_err_px, rng):
    """stars: [(ra, dec, flux)]. The header WCS is off by pointing_err_px (what the references must take out)."""
    true = _wcs()
    yy, xx = np.mgrid[0:N, 0:N]
    img = 0.5 + rng.normal(0, 0.002, (N, N))
    for ra, dec, f in stars:
        x, y = true.all_world2pix(ra, dec, 0)
        img += f * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * 1.1 ** 2))
    hdr = _wcs(pointing_err_px).to_header()
    fits.HDUList([fits.PrimaryHDU(), fits.ImageHDU(img.astype(np.float32), hdr, name="IMAGE"),
                  fits.ImageHDU(np.zeros((N, N), np.int32), name="FLAGS")]).writeto(path, overwrite=True)


def _setup(tmp_path, monkeypatch, pm_arcsec_yr=(3.0, -4.0), star_flux=0.5, neighbour=None):
    rng = np.random.default_rng(7)
    refs = [(RA0 + dx / 3600 / math.cos(math.radians(DEC0)), DEC0 + dy / 3600)
            for dx, dy in [(-200, -150), (180, -160), (-170, 170), (160, 190), (0, -220), (-230, 10), (220, 30), (60, 120)]]
    labels = [{"id": f"r{k}", "name": f"Gaia DR3 {k}", "source": "gaia_dr3", "mag": 12.0 + 0.1 * k,
               "positions": [{"frame_id": "f0", "ra_deg": ra, "dec_deg": dec}]} for k, (ra, dec) in enumerate(refs)]
    t_ref = 61000.0
    pe, pn = pm_arcsec_yr
    star_at = lambda mjd: (RA0 + pe * (mjd - t_ref) / 365.25 / 3600 / math.cos(math.radians(DEC0)),
                           DEC0 + pn * (mjd - t_ref) / 365.25 / 3600)
    labels.append({"id": "s", "name": "Test Star", "source": "simbad", "mag": 9.0, "named": True,
                   "positions": [{"frame_id": f"f{k}", "ra_deg": star_at(m)[0], "dec_deg": star_at(m)[1]}
                                 for k, m in enumerate((60800.0, 61000.0, 61200.0))]})
    target = {"id": "t-motion", "center": {"ra_deg": RA0, "dec_deg": DEC0}, "size_arcmin": 10,
              "frames": [{"id": f"f{k}", "mjd": m} for k, m in enumerate((60800.0, 61000.0, 61200.0))], "labels": labels}
    exps, files = [], {}
    for ep, base in enumerate((60800.0, 61000.0, 61200.0), start=1):
        for k in range(6):
            mjd = base + k * 0.5
            url = f"https://x/{ep}-{k}.fits"
            stars = [(ra, dec, 0.3) for ra, dec in refs] + [(*star_at(mjd), star_flux)]
            if neighbour:
                stars.append((RA0 + neighbour[0] / 3600 / math.cos(math.radians(DEC0)), DEC0 + neighbour[1] / 3600, 0.3))
            p = tmp_path / f"{ep}-{k}.fits"
            _write(p, stars, pointing_err_px=tuple(rng.normal(0, 0.3, 2)), rng=rng)
            files[url] = p
            exps.append(Exposure(obs_id=f"o{ep}{k}", collection="spherex_dr1", detector=1, mjd_start=mjd, mjd_mid=mjd,
                                 time_utc="", exptime_s=100, wave_min_um=0.7, wave_max_um=1.0, epoch=ep,
                                 fits_url=url, publisher_did=url))
    monkeypatch.setattr(AS.build, "cached_exposures", lambda ra, dec: (exps, {}))
    monkeypatch.setattr(photometry, "_spectrum_cutout", lambda url, ra, dec, size: files[url])
    monkeypatch.setattr(AS, "ROOT", tmp_path / "motion")
    monkeypatch.setattr(AS, "REF_MIN", 4)
    monkeypatch.setattr(AS, "_references", lambda sources, star: [s for s in sources if s["source"] == "gaia_dr3"])
    return target


def test_recovers_injected_motion_despite_pointing_errors(tmp_path, monkeypatch):
    target = _setup(tmp_path, monkeypatch)
    r = AS.measure_motion(target, "Test Star", processes=0)
    assert r["status"] == "ready"
    assert r["pm_east_arcsec_yr"] == pytest.approx(3.0, abs=0.3)
    assert r["pm_north_arcsec_yr"] == pytest.approx(-4.0, abs=0.3)
    assert "agrees" in r["verdict"] and r["n_measured"] == 18
    assert AS.cached(target, "s")["pm_total_arcsec_yr"] == r["pm_total_arcsec_yr"]     # cached per star


def test_faint_star_next_to_a_neighbour_is_not_found(tmp_path, monkeypatch):
    target = _setup(tmp_path, monkeypatch, pm_arcsec_yr=(0.0, 0.0), star_flux=0.0, neighbour=(-6.0, 4.5))
    r = AS.measure_motion(target, "Test Star", processes=0)
    assert r["status"] == "not_found" and "not found" in r["message"]


def test_parallax_factor_is_about_one_au():
    e, n = AS.parallax_factors(270.0, 66.56, 61000.0)        # near the ecliptic pole: always ~1 AU of wobble
    assert 0.9 < math.hypot(e, n) < 1.1
