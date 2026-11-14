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
        assert h["IMAGE"].data.shape == (4, 4) and h[0].header["VIA"] == "team-vm-us-east4"
    assert calls == [(URL, 269.4463, 4.7682, build.MIN_CUTOUT_DEG)]   # same size rule as local reads
    assert ";via=team-vm-us-east4" in build.source_of(p, URL, 269.4463, 4.7682)
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
    assert c.get("/cutout", params={"url": URL, "ra": 1, "dec": 2, "size": 7}).status_code == 400


def test_gzip_answer_is_the_fits_file(vm):
    client, _ = vm
    r = client.get("/cutout", params={"url": URL, "ra": 1, "dec": 2, "size": 0.4})
    assert r.status_code == 200 and r.headers["content-type"] == "application/gzip"
    assert gzip.decompress(r.content).startswith(b"SIMPLE")


class _R:
    def __init__(self, status, headers=None, text="", content=b""):
        self.status_code, self.headers, self.text, self.content = status, headers or {}, text, content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def _answering(resp):
    return lambda: type("S", (), {"get": staticmethod(lambda *a, **k: resp)})()


def test_missing_in_bucket_skips_s3_and_keeps_the_vm(monkeypatch, tmp_path):
    """A wrong derived path is one image's problem, not the VM's: no pause, no second S3 read."""
    monkeypatch.setattr(s3, "_session", _answering(_R(404, {"X-Cutout": s3.MISSING})))
    monkeypatch.setattr(s3, "REMOTE", "https://vm.example")
    monkeypatch.setattr(s3, "_remote_down_until", 0.0)
    monkeypatch.setattr(s3, "fetch_cutout", lambda *a, **k: (_ for _ in ()).throw(AssertionError("S3 read again")))
    monkeypatch.setattr(build, "_get_with_retry", lambda url: (_ for _ in ()).throw(RuntimeError("IRSA 404")))
    with pytest.raises(RuntimeError, match="IRSA 404"):
        build.fetch(URL, 1.0, 2.0, 0.3, raw_root=tmp_path)
    assert s3.remote_available()


def test_vm_s3_error_does_not_pause_the_vm(monkeypatch, tmp_path):
    monkeypatch.setattr(s3, "_session", _answering(_R(502, {"X-Cutout": s3.S3_ERROR})))
    monkeypatch.setattr(s3, "REMOTE", "https://vm.example")
    monkeypatch.setattr(s3, "_remote_down_until", 0.0)
    monkeypatch.setattr(s3, "fetch_cutout", lambda url, ra, dec, size, dest: dest.write_bytes(b"SIMPLE s3") and dest)
    assert build.fetch(URL, 1.0, 2.0, 0.3, raw_root=tmp_path).read_bytes() == b"SIMPLE s3"
    assert s3.remote_available()


def test_vm_answers_missing_for_a_404_in_the_bucket(monkeypatch, tmp_path):
    class NotFound(Exception):
        response = type("Resp", (), {"status_code": 404})()

    def cut(*a, **k):
        raise NotFound("404 Client Error")
    monkeypatch.setattr(s3, "fetch_cutout", cut)
    c = TestClient(create_app(tmp_path, prefetch=False))
    r = c.get("/cutout", params={"url": URL, "ra": 1, "dec": 2, "size": 0.4})
    assert r.status_code == 404 and r.headers["X-Cutout"] == s3.MISSING


def test_find_in_bucket_finds_the_retry_version(monkeypatch):
    week = "dr1/level2/2025W47_2A/"
    wrong = ("https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/level2/2025W47_2A/l2b-v27-2026-208/6/"
             "level2_2025W47_2A_0695_3D6_spx_l2b-v27-2026-208.fits")
    key = f"{week}l2b_retry-v27-2026-210/6/level2_2025W47_2A_0695_3D6_spx_l2b_retry-v27-2026-210.fits"
    asked = []

    def get(url, params=None, timeout=None):
        asked.append(params["prefix"])
        if params.get("delimiter"):
            return _R(200, text=f"<Prefix>{week}</Prefix><CommonPrefixes><Prefix>{week}l2b-v27-2026-208/</Prefix>"
                                f"</CommonPrefixes><CommonPrefixes><Prefix>{week}l2b_retry-v27-2026-210/</Prefix>"
                                "</CommonPrefixes>")
        return _R(200, text=f"<Key>{key}</Key>" if "retry" in params["prefix"] else "")
    monkeypatch.setattr(s3, "_session", lambda: type("S", (), {"get": staticmethod(get)})())
    assert s3.find_in_bucket(wrong) == s3.IBE_PREFIX + key
    assert len(asked) == 2                                   # week listing + the retry version, first
    assert s3.find_in_bucket("https://example.org/x.fits") is None
