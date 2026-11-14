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
    g = TileGenerator("https://vm.example/", mode="local")
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
    info = g.info()
    assert (info["tiles"], info["remote_url"], info["remote_available"]) == ("remote", "https://vm.example", True)
    assert info["balance"]["remote"]["done"] == 2


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
    assert c.get("/api/settings").json()["tiles"] == "balanced"          # T55: default with a remote
    assert c.post("/api/settings", json={"tiles": "remote"}).json()["tiles"] == "remote"
    assert c.post("/api/settings", json={"tiles": "local"}).json()["tiles"] == "local"
    assert c.post("/api/settings", json={"tiles": "balanced"}).json()["tiles"] == "balanced"
    assert c.post("/api/settings", json={"tiles": "nonsense"}).status_code == 400
    c2 = TestClient(api(tmp_path / "t2", fixture=True))
    assert c2.get("/api/settings").json()["tiles"] == "local"
    assert c2.post("/api/settings", json={"tiles": "balanced"}).status_code == 400


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


def test_pass_tile_renders_the_other_passes_too(tmp_path, monkeypatch):
    """T55: asking for one pass tile starts the same tile of the other passes in the background."""
    import time

    from server.skycache import SkyCache

    monkeypatch.setattr(render, "survey_passes", lambda: [1, 2, 3])
    asked = []

    class Gen:
        def get(self, sl, o, n, pass_=None):
            asked.append(pass_)
            return b"png"
    sky = SkyCache(tmp_path, tiles=Gen())
    assert sky.get("spherex-live-p2", "Norder7/Dir0/Npix5_20.png") == b"png"
    sky.prefetch_around("spherex-live-p2", "Norder7/Dir0/Npix5_20.png")
    done = tmp_path / "spherex-live-p3/Norder7/Dir0/Npix5_17.png"
    for _ in range(250):
        if len(asked) == 3 and done.exists() and (tmp_path / "spherex-live-p1/Norder7/Dir0/Npix5_17.png").exists():
            break
        time.sleep(0.02)
    assert sorted(asked) == [1, 2, 3]
    assert (tmp_path / "spherex-live-p3/Norder7/Dir0/Npix5_17.png").exists()   # T89: slice per detector


def test_api_pass_dates(tmp_path, monkeypatch):
    from server.app import create_app as api

    monkeypatch.setattr(render, "pass_dates", lambda ra, dec: [{"pass": 1, "start": "2025-08-18", "end": "2025-09-30", "n_images": 3}])
    c = TestClient(api(tmp_path / "targets", fixture=True))
    body = c.get("/api/pass-dates?ra=-90.5&dec=4.7").json()
    assert body["ra"] == 269.5 and body["passes"][0]["start"] == "2025-08-18"
    assert c.get("/api/pass-dates?ra=1&dec=95").status_code == 400


def test_client_balanced_sends_tiles_where_they_finish_first(monkeypatch):
    """T55 balanced: cost = average seconds x (in flight + 1); the faster side gets more tiles, a busy
    side less, and a side unused for a while is measured again."""
    from pipeline import mirror
    from tilegen import client

    monkeypatch.setattr(mirror, "available", lambda root=None: True)
    calls = []
    monkeypatch.setattr(render, "render", lambda sl, o, n, pass_=None, images=None: calls.append(("local", images)) or b"local")
    g = TileGenerator("https://vm.example")
    assert g.mode == "balanced"

    class VM:
        def get(self, url, timeout):
            if url.endswith("/health"):
                return type("R", (), {"json": lambda self: {"images_per_tile": 3}})()
            calls.append(("remote", url))
            return _Resp(200, b"vm")
    g._session = VM()
    g.sides["remote"].rate, g.sides["local"].rate = 4.0, 1.0        # VM measured 4x the throughput
    now = __import__("time").time()
    for s_ in g.sides.values():
        s_.last = now
    assert g.get(20, 7, 1) == b"vm"                                 # idle: the faster side
    g.sides["remote"].rate, g.sides["remote"].inflight = 4.0, 4     # VM busy: 5 / 4 > 1 / 1
    assert g.get(20, 7, 2) == b"local" and calls[-1] == ("local", 3)   # combined tile like the VM's
    g.sides["remote"].inflight = 0
    g.sides["remote"].rate, g.sides["local"].rate = 4.0, 1.0
    assert g.get(20, 7, 3, pass_=2) == b"vm"
    g.sides["local"].last = now - 2 * client.REMEASURE_S            # local not measured for a while
    assert g.get(20, 7, 4) == b"local"
    assert g.sides["local"].inflight == 0 and g.sides["remote"].inflight == 0


def test_client_balanced_falls_back_when_the_vm_fails(monkeypatch):
    from pipeline import mirror

    monkeypatch.setattr(mirror, "available", lambda root=None: True)
    monkeypatch.setattr(render, "render", lambda sl, o, n, pass_=None, images=None: b"local")
    g = TileGenerator("https://vm.example")
    g._remote_images = 3

    class Down:
        def get(self, url, timeout):
            raise ConnectionError("down")
    g._session = Down()
    g.sides["local"].last = g.sides["remote"].last = __import__("time").time()
    assert g.get(20, 7, 1) == b"local"                              # remote chosen (prior), failed, local
    assert g.sides["remote"].failed == 1 and g.sides["remote"].rate <= 0.75
    assert g.get(20, 7, 2) == b"local" and g.sides["remote"].failed == 1   # failing side avoided now


def test_live_tiles_one_per_detector_and_false_colour(tmp_path, monkeypatch):
    """T89: the 17 channels of a detector share one live tile; -rgb composes the 6 detectors."""
    import io

    import numpy as np
    from PIL import Image

    from server.skycache import SkyCache, live_path

    assert live_path("Norder7/Dir0/Npix5_20.png") == "Norder7/Dir0/Npix5_17.png"
    assert live_path("Norder7/Dir0/Npix5_16.png") == "Norder7/Dir0/Npix5.png"
    assert live_path("Norder7/Dir0/Npix5_101.png") == "Norder7/Dir0/Npix5_85.png"
    assert live_path("Norder5/Dir0/Npix5_20.png") == "Norder5/Dir0/Npix5_20.png"     # cube order: unchanged

    def png(v):
        b = io.BytesIO()
        Image.fromarray(np.dstack([np.full((512, 512), v, np.uint8), np.full((512, 512), 255, np.uint8)]), "LA").save(b, "PNG")
        return b.getvalue()

    asked = []

    class Gen:
        def get(self, sl, o, n, pass_=None):
            asked.append(sl)
            return png(10 * (sl // 17 + 1))          # detector d -> grey 10 d
    sky = SkyCache(tmp_path, tiles=Gen())
    for sl in (3, 9, 16):
        sky.get("spherex-live-p1", f"Norder7/Dir0/Npix5_{sl}.png")
    assert asked == [0]                                  # one render for all of detector 1
    # LRGB: detail = the grey tile of the band in the path (detector 3 here: grey 30), colour from the cube
    sky.chroma = lambda order, npix: np.broadcast_to(np.array([1.5, 1.0, 0.5], np.float32), (512, 512, 3))
    rgb = sky.get("spherex-live-p1-rgb", "Norder7/Dir0/Npix5_40.png")
    px = np.asarray(Image.open(io.BytesIO(rgb)).convert("RGBA"))[0, 0]
    assert tuple(px) == (45, 30, 15, 255)
    assert asked == [0, 34]                              # one render (detector 3), not one per detector
    props = sky.get("spherex-live-p1-rgb", "properties").decode()
    assert "false colour" in props


def test_blank_cube_slices_and_false_colour_map(tmp_path):
    """T89: IRSA cube slices 50/51 are blank -> neighbours; spherex-live-rgb composes cube slices."""
    import io

    import numpy as np
    from PIL import Image

    from server.skycache import SkyCache, cube_path, with_slice

    assert cube_path("Norder3/Allsky_50.png") == "Norder3/Allsky_49.png"
    assert cube_path("Norder2/Dir0/Npix7_51.png") == "Norder2/Dir0/Npix7_52.png"
    assert cube_path("Norder2/Dir0/Npix7_49.png") == "Norder2/Dir0/Npix7_49.png"
    assert with_slice("Norder2/Dir0/Npix7.png", 25) == "Norder2/Dir0/Npix7_25.png"
    assert with_slice("Norder3/Allsky_4.png", 0) == "Norder3/Allsky.png"

    sky = SkyCache(tmp_path)
    asked = []

    def fake_get(survey, path, _orig=sky.get):
        if survey != "spherex-cube":
            return _orig(survey, path)
        asked.append(path)
        sl = int(path.rsplit("_", 1)[1].split(".")[0])
        b = io.BytesIO()
        Image.fromarray(np.full((4, 4), sl, np.uint8), "L").save(b, "PNG")
        return b.getvalue()
    sky.get = fake_get
    rgb = sky.get("spherex-live-rgb", "Norder2/Dir0/Npix7.png")
    px = np.asarray(Image.open(io.BytesIO(rgb)).convert("RGBA"))[0, 0]
    assert tuple(px) == ((76 + 93) // 2, (42 + 59) // 2, (8 + 25) // 2, 255)
    assert sorted(asked) == sorted(f"Norder2/Dir0/Npix7_{s}.png" for s in (8, 25, 42, 59, 76, 93))


def test_chroma_takes_the_childs_part_of_the_order5_colour_tile(tmp_path):
    """T89 LRGB: an order-7 tile's colour is its 128 x 128 part of the order-5 cube colour tile, stretched."""
    import io

    import numpy as np
    from PIL import Image

    from server.skycache import SkyCache

    sky = SkyCache(tmp_path)
    img = np.zeros((512, 512, 3), np.uint8)
    img[:128, 128:256] = (200, 100, 0)                   # row block 0, col block 1 of the parent tile
    img[128:256, :128] = (0, 100, 200)                   # row block 1, col block 0
    b = io.BytesIO(); Image.fromarray(img, "RGB").save(b, "PNG")
    sky.get = lambda survey, path, _png=b.getvalue(): _png if survey == "spherex-live-rgb" else None
    parent = 7
    # child bits: row in even bits, col in odd bits -> (row 0, col 1) = 0b10 = 2; (row 1, col 0) = 0b01 = 1
    ch = sky.chroma(7, parent * 16 + 2)
    assert ch[256, 256].argmax() == 0 and ch[256, 256][2] < 0.1      # reddish
    ch = sky.chroma(7, parent * 16 + 1)
    assert ch[256, 256].argmax() == 2                                # bluish
    assert sky.chroma(5, parent).shape == (512, 512, 3)



def test_janitor_trims_oldest_first_and_keeps_free_space(tmp_path, monkeypatch):
    """T94: caches stay under their cap (oldest written files go first); low disk space trims further."""
    import os
    import shutil
    from collections import namedtuple

    from tilegen import janitor

    a, b = tmp_path / "chunks", tmp_path / "tiles"
    for d in (a, b):
        d.mkdir()
    for i in range(10):
        f = a / f"c{i}.npz"
        f.write_bytes(b"x" * 100)
        os.utime(f, (1000 + i, 1000 + i))
    (b / "t.png").write_bytes(b"y" * 50)
    assert janitor.trim([(a, 450), (b, 1000)]) == 600            # 10 x 100 bytes -> 4 newest kept
    assert sorted(p.name for p in a.iterdir()) == ["c6.npz", "c7.npz", "c8.npz", "c9.npz"]
    Usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(shutil, "disk_usage", lambda p: Usage(10_000, 9_900, 100))
    janitor.trim([(a, 1e9), (b, 1e9)], keep_free=300)            # needs 200 more bytes: two oldest go
    assert sorted(p.name for p in a.iterdir()) == ["c8.npz", "c9.npz"] and (b / "t.png").exists()
