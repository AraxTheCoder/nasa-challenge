"""How the Live API gets live tiles: in-process (local) or from a tilegen service (remote).

    gen = TileGenerator(remote_url="https://136-107-125-170.sslip.io")
    gen.use_remote(True)                   # switch at run time (viewer "Tiles" switch)
    png = gen.get(slice_, order, npix)     # bytes, or None (no SPHEREx data there)
"""
from __future__ import annotations

import threading


class TileGenerator:
    def __init__(self, remote_url: str | None = None, use_remote: bool = False):
        self.remote_url = remote_url.rstrip("/") if remote_url else None
        self.remote = bool(use_remote and self.remote_url)
        self._session = None
        self._lock = threading.Lock()

    @property
    def mode(self) -> str:
        return "remote" if self.remote else "local"

    def use_remote(self, on: bool) -> None:
        if on and not self.remote_url:
            raise ValueError("no remote tile generator configured (python -m server --tiles-remote <url>)")
        self.remote = bool(on)

    def info(self) -> dict:
        return {"tiles": self.mode, "remote_url": self.remote_url, "remote_available": bool(self.remote_url)}

    def get(self, slice_: int, order: int, npix: int) -> bytes | None:
        if self.remote:
            return self._remote(slice_, order, npix)
        from pipeline.mirror import IndexNotReady

        from . import render
        try:
            return render.render(slice_, order, npix)
        except IndexNotReady:
            if self.remote_url:            # fresh checkout: the remote generator stands in meanwhile
                return self._remote(slice_, order, npix)
            raise

    def _http(self):
        with self._lock:
            if self._session is None:
                import requests
                from requests.adapters import HTTPAdapter

                s = requests.Session()
                for scheme in ("https://", "http://"):
                    s.mount(scheme, HTTPAdapter(pool_maxsize=16, max_retries=1))
                self._session = s
            return self._session

    def _remote(self, slice_: int, order: int, npix: int) -> bytes | None:
        sl = f"_{slice_}" if slice_ else ""
        url = f"{self.remote_url}/tiles/live/Norder{order}/Dir{(npix // 10000) * 10000}/Npix{npix}{sl}.png"
        r = self._http().get(url, timeout=180)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.content
