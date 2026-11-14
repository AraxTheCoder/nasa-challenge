"""How the Live API gets live tiles: in-process (local) or from a tilegen service (remote).

    gen = TileGenerator(remote_url="https://136-107-125-170.sslip.io")
    gen.use_remote(True)                   # switch at run time (viewer "Tiles" switch)
    png = gen.get(slice_, order, npix)     # bytes, or None (no SPHEREx data there)
"""
from __future__ import annotations

import threading


class _NoPassRoute(Exception):
    pass


class TileGenerator:
    def __init__(self, remote_url: str | None = None, use_remote: bool = False):
        self.remote_url = remote_url.rstrip("/") if remote_url else None
        self.remote = bool(use_remote and self.remote_url)
        self._session = None
        self._lock = threading.Lock()
        self._remote_passes = True       # False once the VM answered that it has no pass route (old deploy)

    @property
    def mode(self) -> str:
        return "remote" if self.remote else "local"

    def use_remote(self, on: bool) -> None:
        if on and not self.remote_url:
            raise ValueError("no remote tile generator configured (python -m server --tiles-remote <url>)")
        self.remote = bool(on)

    def info(self) -> dict:
        return {"tiles": self.mode, "remote_url": self.remote_url, "remote_available": bool(self.remote_url)}

    def get(self, slice_: int, order: int, npix: int, pass_: int | None = None) -> bytes | None:
        if self.remote and (pass_ is None or self._remote_passes):
            try:
                return self._remote(slice_, order, npix, pass_)
            except _NoPassRoute:              # VM older than T82 pass tiles: render those here
                self._remote_passes = False
        from pipeline.mirror import IndexNotReady

        from . import render
        try:
            return render.render(slice_, order, npix, pass_=pass_) if pass_ else render.render(slice_, order, npix)
        except IndexNotReady:
            if self.remote_url and (pass_ is None or self._remote_passes):   # fresh checkout: the VM stands in
                return self._remote(slice_, order, npix, pass_)
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

    def _remote(self, slice_: int, order: int, npix: int, pass_: int | None = None) -> bytes | None:
        sl = f"_{slice_}" if slice_ else ""
        live = f"live-p{pass_}" if pass_ else "live"
        url = f"{self.remote_url}/tiles/{live}/Norder{order}/Dir{(npix // 10000) * 10000}/Npix{npix}{sl}.png"
        r = self._http().get(url, timeout=180)
        if r.status_code == 404:
            # "no data here" is an empty 404; FastAPI's unknown-route 404 is JSON {"detail": ...}
            if pass_ and r.content.startswith(b"{"):
                raise _NoPassRoute()
            return None
        r.raise_for_status()
        return r.content
