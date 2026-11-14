"""pytest tilegen/  (offline: rendering and HTTP are faked)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from tilegen import render
from tilegen.app import create_app
from tilegen.client import TileGenerator


def test_service_renders_once_and_caches(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(render, "render", lambda sl, o, n: calls.append((sl, o, n)) or (None if n == 9 else b"\x89PNGtile"))
    c = TestClient(create_app(tmp_path, prefetch=False))
    r = c.get("/tiles/live/Norder7/Dir0/Npix123_20.png")
    assert r.status_code == 200 and r.content == b"\x89PNGtile"
    assert c.get("/tiles/live/Norder7/Dir0/Npix123_20.png").content == b"\x89PNGtile"
    assert c.get("/tiles/live/Norder6/Dir0/Npix9.png").status_code == 404
    assert c.get("/tiles/live/Norder6/Dir0/Npix9.png").status_code == 404
    assert c.get("/tiles/live/Norder5/Dir0/Npix1.png").status_code == 404        # not a live order
    assert calls == [(20, 7, 123), (0, 6, 9)]
    h = c.get("/health").json()
    assert h["ok"] and h["rendered"] == 2 and h["orders"] == [6, 7]


class _Resp:
    def __init__(self, status, content=b""):
        self.status_code, self.content = status, content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def test_client_local_and_remote(monkeypatch):
    monkeypatch.setattr(render, "render", lambda sl, o, n: b"local")
    g = TileGenerator("https://vm.example/")
    assert g.mode == "local" and g.get(1, 7, 5) == b"local"
    g.use_remote(True)
    urls = []

    class S:
        def get(self, url, timeout):
            urls.append(url)
            return _Resp(404) if "Npix6." in url else _Resp(200, b"remote")
    g._session = S()
    assert g.get(20, 7, 12345) == b"remote" and g.get(0, 6, 6) is None
    assert urls == ["https://vm.example/tiles/live/Norder7/Dir10000/Npix12345_20.png",
                    "https://vm.example/tiles/live/Norder6/Dir0/Npix6.png"]
    assert g.info() == {"tiles": "remote", "remote_url": "https://vm.example", "remote_available": True}


def test_client_without_remote_refuses_switch():
    g = TileGenerator()
    try:
        g.use_remote(True)
        raise AssertionError("should refuse")
    except ValueError:
        pass
    assert g.mode == "local"


def test_api_settings_switch(tmp_path):
    from server.app import create_app as api

    c = TestClient(api(tmp_path / "targets", fixture=True, tiles_remote="https://vm.example"))
    assert c.get("/api/settings").json()["tiles"] == "local"
    assert c.post("/api/settings", json={"tiles": "remote"}).json()["tiles"] == "remote"
    assert c.post("/api/settings", json={"tiles": "local"}).json()["tiles"] == "local"
    c2 = TestClient(api(tmp_path / "t2", fixture=True))
    assert c2.post("/api/settings", json={"tiles": "remote"}).status_code == 400


def test_fresh_checkout_without_index(monkeypatch, tmp_path):
    """data/ is gitignored: no index -> it gets built in the background, the remote generator
    stands in meanwhile, and without a remote the API answers 503 (retry), not 502."""
    import threading

    from pipeline import mirror

    started = threading.Event()
    monkeypatch.setattr(mirror, "MIRROR", tmp_path / "mirror")
    monkeypatch.setattr(mirror, "harvest", lambda root=None: started.set())
    monkeypatch.setattr(mirror, "build", lambda root=None: None)
    monkeypatch.setattr(mirror, "_building", {"thread": None, "error": None})
    monkeypatch.setattr(mirror.ensure_background, "__defaults__", (tmp_path / "mirror",))
    monkeypatch.setattr(render, "_index", None)

    g = TileGenerator("https://vm.example")

    class S:
        def get(self, url, timeout):
            return _Resp(200, b"from-vm")
    g._session = S()
    assert g.get(20, 7, 1) == b"from-vm"            # local index missing -> remote stands in
    assert started.wait(5)                          # ... and the index build was started

    from server.app import create_app as api
    c = TestClient(api(tmp_path / "targets", fixture=True))
    r = c.get("/api/sky/spherex-live/Norder7/Dir0/Npix5_20.png")
    assert r.status_code == 503 and r.headers["retry-after"] == "20"


def test_service_pass_tiles_cached_apart(tmp_path, monkeypatch):
    """T82/T55: /tiles/live-p<n>/ renders from pass n's images only, cached apart from the combined tile."""
    calls = []

    def fake(sl, o, n, pass_=None):
        calls.append((sl, o, n, pass_))
        return f"png-{pass_}".encode()
    monkeypatch.setattr(render, "render", fake)
    c = TestClient(create_app(tmp_path, prefetch=False))
    assert c.get("/tiles/live-p2/Norder7/Dir0/Npix5_20.png").content == b"png-2"
    assert c.get("/tiles/live-p2/Norder7/Dir0/Npix5_20.png").content == b"png-2"     # cached
    assert c.get("/tiles/live-p3/Norder7/Dir0/Npix5_20.png").content == b"png-3"
    assert c.get("/tiles/live/Norder7/Dir0/Npix5_20.png").content == b"png-None"
    assert c.get("/tiles/live-p2/Norder5/Dir0/Npix1.png").status_code == 404           # not a live order
    assert calls == [(20, 7, 5, 2), (20, 7, 5, 3), (20, 7, 5, None)]
    assert (tmp_path / "p2/Norder7/Dir0/Npix5_20.png").exists()
    assert c.get("/health").json()["passes"] is True


def test_client_pass_tiles_remote_then_local_on_old_vm(monkeypatch):
    monkeypatch.setattr(render, "render", lambda sl, o, n, pass_=None: b"local")
    g = TileGenerator("https://vm.example", use_remote=True)
    urls = []

    class New:
        def get(self, url, timeout):
            urls.append(url)
            return _Resp(200, b"vm-pass")
    g._session = New()
    assert g.get(20, 7, 5, pass_=2) == b"vm-pass"
    assert urls == ["https://vm.example/tiles/live-p2/Norder7/Dir0/Npix5_20.png"]

    class Old:                                     # deploy without the pass route: FastAPI's JSON 404
        def get(self, url, timeout):
            urls.append(url)
            return _Resp(404, b'{"detail":"Not Found"}')
    g._session = Old()
    assert g.get(20, 7, 5, pass_=2) == b"local"
    n = len(urls)
    assert g.get(20, 7, 6, pass_=2) == b"local" and len(urls) == n   # not asked again
