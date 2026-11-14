"""T41: server-side cache + prefetch for the all-sky HiPS maps the sky map shows.

IRSA's HiPS answers each tile after ~0.7 s and speaks HTTP/1.1 (a browser opens 6 connections),
its Allsky mosaic takes ~4 s. The viewer asks us instead:

    GET /api/sky/<survey>/properties
    GET /api/sky/<survey>/Norder<k>/Dir<d>/Npix<p>[_<slice>].<ext>
    GET /api/sky/<survey>/Norder3/Allsky[_<slice>].<ext>

First request: fetched upstream (mirrors in order), stored under data/hips_cache/<survey>/, then
served from disk in milliseconds. Each tile request also prefetches, in the background, its 8
neighbours and 4 children, so panning and zooming find the next tiles already here.
"""
from __future__ import annotations

import re
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SURVEYS = {
    "spherex-cube": ["https://irsa.ipac.caltech.edu/data/hips/SPHEREx/spherex_allsky_cube"],
    **{f"spherex-d{d}": [f"https://alasky.cds.unistra.fr/SPHEREx/D{d}", f"https://alaskybis.cds.unistra.fr/SPHEREx/D{d}"]
       for d in range(1, 7)},
    # T42: IRSA's cube up to order 5, our own live tiles from the AWS level-2 images at 6-7
    "spherex-live": [],
    # T82: one layer per survey pass, live orders only (the IRSA cube below them combines passes)
    **{f"spherex-live-p{n}": [] for n in range(1, 7)},
    "2mass": ["https://irsa.ipac.caltech.edu/data/hips/CDS/2MASS/Color"],
    "allwise": ["https://irsa.ipac.caltech.edu/data/hips/CDS/AllWISE/RGB-W4-W2-W1"],
}
TILE_RE = re.compile(r"^Norder(\d+)/Dir(\d+)/Npix(\d+)(_\d+)?\.(png|jpg|jpeg)$")
ALLSKY_RE = re.compile(r"^Norder3/Allsky(_\d+)?\.(png|jpg|jpeg)$")
MISSING = b"MISSING"
TIMEOUT_S = 30


class SkyCache:
    def __init__(self, root: Path, tiles=None):
        from tilegen.client import TileGenerator

        self.root = Path(root)
        self.tiles = tiles or TileGenerator()
        self._session = None
        self._inflight: dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        self._prefetch = ThreadPoolExecutor(16, thread_name_prefix="sky-prefetch")
        self._props: dict[str, dict] = {}
        # Live tiles rendered (or asked of the remote generator) at once. Taken by the API endpoint,
        # which stops waiting when the browser hangs up (it aborts tiles that left the screen).
        self.live_slots = threading.BoundedSemaphore(6)

    def _http(self):
        if self._session is None:
            import requests
            from requests.adapters import HTTPAdapter

            s = requests.Session()
            s.mount("https://", HTTPAdapter(pool_connections=8, pool_maxsize=48, max_retries=2))
            s.headers["User-Agent"] = "spherex-blink tile cache"
            self._session = s
        return self._session

    @staticmethod
    def valid(survey: str, path: str) -> bool:
        return survey in SURVEYS and (path == "properties" or bool(TILE_RE.match(path)) or bool(ALLSKY_RE.match(path)))

    def get(self, survey: str, path: str) -> bytes | None:
        """Bytes of the file (from disk or upstream), or None if upstream doesn't have it."""
        if survey.startswith("spherex-live"):
            live = self._live_route(path, survey)
            if live is not None:
                return live()
        f = self.root / survey / path
        if f.exists():
            data = f.read_bytes()
            return None if data == MISSING else data
        key = f"{survey}/{path}"
        with self._lock:
            ev = self._inflight.get(key)
            owner = ev is None
            if owner:
                ev = self._inflight[key] = threading.Event()
        if not owner:                                  # someone is fetching it: wait for them
            ev.wait(TIMEOUT_S + 5)
            return self.get(survey, path) if f.exists() else None
        try:
            data = self._fetch(survey, path)
            f.parent.mkdir(parents=True, exist_ok=True)
            tmp = f.with_name(f.name + f".{threading.get_ident()}.part")
            tmp.write_bytes(data if data is not None else MISSING)
            tmp.replace(f)
            return data
        finally:
            with self._lock:
                self._inflight.pop(key, None)
            ev.set()

    def _live_route(self, path: str, survey: str = "spherex-live"):
        """spherex-live: properties and orders <= 5 come from the cube, 6-7 are rendered by us.
        spherex-live-p<n> (T82): the same, but orders <= 5 are empty (no per-pass cube)."""
        from tilegen.render import LIVE_ORDERS, survey_passes

        if survey != "spherex-live":
            n = survey.rsplit("-p", 1)[1]
            if path == "properties":            # the live map's (102-band cube depth etc.), relabelled
                def props():
                    live = (self._live_route("properties")() or b"").decode("utf-8", "replace").splitlines()
                    keep = [l for l in live if not l.startswith(("obs_title", "creator_did", "hips_order_min"))]
                    keep += [f"obs_title            = SPHEREx survey pass {n}: live tiles from that pass's level-2 images",
                             f"creator_did          = ivo://spherex-blink/live-p{n}",
                             f"hips_order_min       = {min(LIVE_ORDERS)}"]
                    return ("\n".join(keep) + "\n").encode()
                return props
            m = TILE_RE.match(path)
            if ALLSKY_RE.match(path) or (m and int(m.group(1)) not in LIVE_ORDERS):
                return lambda: None
            return None
        if path == "properties":
            def props():
                cube = (self.get("spherex-cube", "properties") or b"").decode("utf-8", "replace")
                lines = [l for l in cube.splitlines() if not l.startswith(("hips_order ", "obs_title", "creator_did"))]
                lines += [f"hips_order           = {max(LIVE_ORDERS)}",
                          "obs_title            = SPHEREx DR1: IRSA cube to order 5, live tiles from AWS level-2 images above",
                          "creator_did          = ivo://spherex-blink/live",
                          "x_live_orders        = " + " ".join(map(str, LIVE_ORDERS)),
                          # T55: passes with images in the index (spherex-live-p<n> layers to blink)
                          "x_survey_passes      = " + " ".join(map(str, survey_passes()))]
                return ("\n".join(lines) + "\n").encode()
            return props
        if ALLSKY_RE.match(path):
            return lambda: self.get("spherex-cube", path)
        m = TILE_RE.match(path)
        if m and int(m.group(1)) not in LIVE_ORDERS:
            return lambda: self.get("spherex-cube", path)
        return None                                   # live order: cached on disk like any tile

    def _fetch(self, survey: str, path: str) -> bytes | None:
        if survey.startswith("spherex-live"):         # live order: tile generator (local or remote)
            m = TILE_RE.match(path)
            slice_ = int(m.group(4)[1:]) if m.group(4) else 0
            pass_ = int(survey.rsplit("-p", 1)[1]) if survey != "spherex-live" else None
            if pass_:
                return self.tiles.get(slice_, int(m.group(1)), int(m.group(3)), pass_=pass_)
            return self.tiles.get(slice_, int(m.group(1)), int(m.group(3)))
        last = None
        for base in SURVEYS[survey]:
            try:
                r = self._http().get(f"{base}/{path}", timeout=TIMEOUT_S)
            except Exception as e:  # noqa: BLE001 - next mirror
                last = e
                continue
            if r.status_code == 404:
                return None
            if r.ok and (path == "properties" or not r.content.startswith(b"<")):
                return r.content
            last = RuntimeError(f"HTTP {r.status_code}")
        raise RuntimeError(f"{survey}/{path}: {last}")

    # -- prefetch ----------------------------------------------------------------------------------

    def is_live_render(self, survey: str, path: str) -> bool:
        """True if this request would run the (slow) tile generator: live order, not cached yet."""
        if not survey.startswith("spherex-live"):
            return False
        from tilegen.render import LIVE_ORDERS

        m = TILE_RE.match(path)
        return bool(m) and int(m.group(1)) in LIVE_ORDERS and not (self.root / survey / path).exists()

    def prefetch_around(self, survey: str, path: str) -> None:
        m = TILE_RE.match(path)
        if not m:
            return
        if survey.startswith("spherex-live-p"):     # T82: pass layers: nothing below the live orders
            return
        if survey == "spherex-live":
            # Never prefetch into live orders: each is a slow render that would take a slot from a
            # visible tile (Joerg's diagnosis, TEAM.md 2026-11-14). Below them the cube does the work.
            from tilegen.render import LIVE_ORDERS
            if int(m.group(1)) in LIVE_ORDERS or int(m.group(1)) + 1 in LIVE_ORDERS:
                return
            survey = "spherex-cube"
        order, pix, sl, ext = int(m.group(1)), int(m.group(3)), m.group(4) or "", m.group(5)
        max_order = self._max_order(survey)
        want = []
        try:
            from astropy_healpix import HEALPix

            nb = HEALPix(nside=2 ** order, order="nested").neighbours(pix)
            want += [(order, int(p)) for p in nb if p >= 0]
        except Exception:  # noqa: BLE001
            pass
        if order < max_order:
            want += [(order + 1, pix * 4 + i) for i in range(4)]
        for k, p in want:
            sub = f"Norder{k}/Dir{(p // 10000) * 10000}/Npix{p}{sl}.{ext}"
            if not (self.root / survey / sub).exists():
                self._prefetch.submit(self._quiet_get, survey, sub)

    def _quiet_get(self, survey: str, path: str) -> None:
        try:
            self.get(survey, path)
        except Exception:  # noqa: BLE001 - prefetch is best effort
            pass

    def _max_order(self, survey: str) -> int:
        if survey not in self._props:
            props = {}
            try:
                for line in (self.get(survey, "properties") or b"").decode("utf-8", "replace").splitlines():
                    if "=" in line:
                        k, v = line.split("=", 1)
                        props[k.strip()] = v.strip()
            except Exception:  # noqa: BLE001
                pass
            self._props[survey] = props
        return int(self._props[survey].get("hips_order", 3))

    def warm(self, survey: str = "spherex-cube") -> None:
        """Background: properties + the default band's Allsky, so the first zoomed-out view is instant."""
        def run():
            try:
                self._max_order(survey)
                first = self._props[survey].get("hips_cube_firstframe", "0")
                ext = "png" if "png" in self._props[survey].get("hips_tile_format", "png") else "jpg"
                sl = f"_{first}" if first not in ("", "0") else ""
                self.get(survey, f"Norder3/Allsky{sl}.{ext}")
            except Exception:  # noqa: BLE001
                pass
        self._prefetch.submit(run)
