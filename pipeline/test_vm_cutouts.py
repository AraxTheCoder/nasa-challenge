"""pytest pipeline/test_vm_cutouts.py  (T57, offline: the VM is tilegen's app in a TestClient)."""
from __future__ import annotations

import gzip

import numpy as np
import pytest
from astropy.io import fits
from fastapi.testclient import TestClient

from pipeline import build, s3
from tilegen.app import create_app

URL = "https://irsa.ipac.caltech.edu/ibe/data/spherex/qr2/level2/2025W35/l2b-v20/1/a.fits"


def _fake_cut(calls):
    """Stands in for the S3 read on the VM: writes a tiny cutout FITS like fetch_cutout does."""
    def cut(url, ra, dec, size, dest, via=None):
        calls.append((url, round(ra, 4), round(dec, 4), size))
        if "off" in url:
            raise LookupError("field is not on this image")
        dest.parent.mkdir(parents=True, exist_ok=True)
        hdus = fits.HDUList([fits.PrimaryHDU(), fits.ImageHDU(np.ones((4, 4), np.float32), name="IMAGE")])
        hdus[0].header["S3SRC"] = s3.s3_url(url)[:68]
        hdus[0].header["S3CUT"] = "x 0:4 y 0:4"
        if via:
            hdus[0].header["VIA"] = via
        hdus.writeto(dest, overwrite=True)
        return dest
    return cut


@pytest.fixture
def vm(monkeypatch, tmp_path):
    """REMOTE points at tilegen's /cutout (in-process); S3 on 'the VM' is faked."""
    calls = []
    monkeypatch.setattr(s3, "fetch_cutout", _fake_cut(calls))
    client = TestClient(create_app(tmp_path / "vm" / "tilegen_cache", prefetch=False))
    monkeypatch.setattr(s3, "_session", lambda: client)
    monkeypatch.setattr(s3, "REMOTE", "http://testserver")
    monkeypatch.setattr(s3, "_remote_down_until", 0.0)
    return client, calls


def test_build_fetch_gets_the_cutout_from_the_vm(vm, tmp_path):
    client, calls = vm
    p = build.fetch(URL, 269.4463, 4.7682, 0.385, raw_root=tmp_path / "raw")
    with fits.open(p) as h:
        assert h["IMAGE"].data.shape == (4, 4) and "team VM" in h[0].header["VIA"]
    assert calls == [(URL, 269.4463, 4.7682, build.MIN_CUTOUT_DEG)]   # same size rule as local reads
    assert ";via=team VM" in build.source_of(p, URL, 269.4463, 4.7682)
    # the VM keeps a gzip copy: a second Europe-side cache asks again and the VM doesn't re-read S3
    build.fetch(URL, 269.4463, 4.7682, 0.385, raw_root=tmp_path / "raw2")
    assert len(calls) == 1 and client.get("/cutout/health").json()["served_from_cache"] == 1


def test_off_image_is_a_lookup_error_and_cached_on_the_vm(vm, tmp_path):
    _, calls = vm
    off = URL.replace("a.fits", "off.fits")
    for _ in range(2):
        with pytest.raises(LookupError):
            build.fetch(off, 1.0, 2.0, 0.3, raw_root=tmp_path / "raw")
    assert len(calls) == 1


def test_vm_down_falls_back_to_s3_and_pauses_the_vm(monkeypatch, tmp_path):
    asked = []

    class Down:
        def get(self, *a, **k):
            asked.append(a[0])
            raise ConnectionError("refused")
    monkeypatch.setattr(s3, "_session", lambda: Down())
    monkeypatch.setattr(s3, "REMOTE", "https://vm.example")
    monkeypatch.setattr(s3, "_remote_down_until", 0.0)
    monkeypatch.setattr(s3, "fetch_cutout", lambda url, ra, dec, size, dest: dest.write_bytes(b"SIMPLE s3") and dest)
    for name in ("a.fits", "b.fits"):
        p = build.fetch(URL.replace("a.fits", name), 1.0, 2.0, 0.3, raw_root=tmp_path)
        assert p.read_bytes() == b"SIMPLE s3"
    assert len(asked) == 1 and not s3.remote_available()        # second image went straight to S3


def test_old_vm_without_cutout_route_falls_back(monkeypatch, tmp_path):
    class Old:
        def get(self, *a, **k):
            return type("R", (), {"status_code": 404, "headers": {}, "text": "Not Found", "content": b""})()
    monkeypatch.setattr(s3, "_session", lambda: Old())
    monkeypatch.setattr(s3, "REMOTE", "https://vm.example")
    monkeypatch.setattr(s3, "_remote_down_until", 0.0)
    monkeypatch.setattr(s3, "fetch_cutout", lambda url, ra, dec, size, dest: dest.write_bytes(b"SIMPLE s3") and dest)
    assert build.fetch(URL, 1.0, 2.0, 0.3, raw_root=tmp_path).read_bytes() == b"SIMPLE s3"
    assert not s3.remote_available()


def test_cutout_route_rejects_other_urls(tmp_path):
    c = TestClient(create_app(tmp_path, prefetch=False))
    for url in ("https://example.org/a.fits", URL.replace(".fits", ".txt"), URL.replace("/1/", "/../")):
        assert c.get("/cutout", params={"url": url, "ra": 1, "dec": 2, "size": 0.4}).status_code == 400
    assert c.get("/cutout", params={"url": URL, "ra": 1, "dec": 2, "size": 5}).status_code == 400


def test_gzip_answer_is_the_fits_file(vm):
    client, _ = vm
    r = client.get("/cutout", params={"url": URL, "ra": 1, "dec": 2, "size": 0.4})
    assert r.status_code == 200 and r.headers["content-type"] == "application/gzip"
    assert gzip.decompress(r.content).startswith(b"SIMPLE")
