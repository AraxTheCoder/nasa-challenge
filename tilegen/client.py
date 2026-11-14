"""How the Live API gets live tiles: in-process (local), from a tilegen service (remote), or both (balanced).

    gen = TileGenerator(remote_url="https://136-107-125-170.sslip.io")   # balanced when a remote is given
    gen.set_mode("remote")                 # "local" | "remote" | "balanced" (viewer "Tiles" switch)
    png = gen.get(slice_, order, npix)     # bytes, or None (no SPHEREx data there)

Balanced (T55, default with a remote): every tile goes to whichever side is expected to finish it first.
Each side measures its throughput at the load it had (Little's law: tiles in flight / seconds per tile,
moving average), and a new tile costs (tiles in flight there + 1) / throughput. So the share follows
whichever side is faster right now (on 2026-11-14 this PC rendered pass tiles ~3x faster than the 2-vCPU VM
under load); a side not used for a while gets the next tile while idle, so both stay measured. Tiles look
the same from either side: local renders use the VM's images per tile.
"""
from __future__ import annotations

import threading
import time

MODES = ("local", "remote", "balanced")
ALPHA = 0.3                  # weight of the newest tile in the moving average
PRIOR_RATE = {"local": 1.0, "remote": 1.5}   # tiles per second before the first measurement (VM: next to the bucket)
REMEASURE_S = 20.0           # a side unused this long gets the next tile while it is idle


class _NoPassRoute(Exception):
    pass


class _Side:
    def __init__(self, name: str):
        self.name, self.avg, self.rate, self.inflight, self.done, self.failed, self.last = name, None, None, 0, 0, 0, 0.0

    def cost(self) -> float:
        """Expected seconds until a new tile sent here is done."""
        return (self.inflight + 1) / (self.rate or PRIOR_RATE[self.name])

    def info(self) -> dict:
        return {"avg_s": round(self.avg, 2) if self.avg is not None else None,
                "tiles_per_s": round(self.rate, 2) if self.rate is not None else None,
                "inflight": self.inflight, "done": self.done, "failed": self.failed}


class TileGenerator:
    def __init__(self, remote_url: str | None = None, use_remote: bool = False, mode: str | None = None):
        self.remote_url = remote_url.rstrip("/") if remote_url else None
        self._mode = mode or ("remote" if use_remote and self.remote_url else "balanced" if self.remote_url else "local")
        if self._mode != "local" and not self.remote_url:
            self._mode = "local"
        self._session = None
        self._lock = threading.Lock()
        self._remote_passes = True       # False once the VM answered that it has no pass route (old deploy)
        self._remote_images = None       # the VM's images per combined tile (its /health), for local renders
        self.sides = {"local": _Side("local"), "remote": _Side("remote")}

    # ---- mode ----
    @property
    def mode(self) -> str:
        return self._mode

    @property
    def remote(self) -> bool:            # kept for callers that only know local / remote
        return self._mode == "remote"

    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            raise ValueError(f"tiles must be one of {', '.join(MODES)}")
        if mode != "local" and not self.remote_url:
            raise ValueError("no remote tile generator configured (python -m server --tiles-remote <url>)")
        self._mode = mode

    def use_remote(self, on: bool) -> None:
        self.set_mode("remote" if on else "local")

    def info(self) -> dict:
        out = {"tiles": self.mode, "remote_url": self.remote_url, "remote_available": bool(self.remote_url)}
        if self.remote_url:
            out["balance"] = {k: s.info() for k, s in self.sides.items()}
        return out

    # ---- tiles ----
    def get(self, slice_: int, order: int, npix: int, pass_: int | None = None) -> bytes | None:
        from pipeline.mirror import IndexNotReady

        side, counted = self._choose(pass_)
        if side == "remote":
            try:
                return self._timed("remote", lambda: self._remote(slice_, order, npix, pass_), counted)
            except _NoPassRoute:              # VM older than T82 pass tiles: render those here
                self._remote_passes = False
            except Exception:  # noqa: BLE001 - VM down / overloaded
                if self._mode == "remote":
                    raise
                # balanced: the side's average was raised in _timed; this tile renders here
        try:
            return self._timed("local", lambda: self._local(slice_, order, npix, pass_), counted and side == "local")
        except IndexNotReady:
            if self.remote_url and (pass_ is None or self._remote_passes):   # fresh checkout: the VM stands in
                return self._remote(slice_, order, npix, pass_)
            raise

    def _choose(self, pass_: int | None) -> tuple[str, bool]:
        """(side that renders this tile, whether it is already counted as in flight there)."""
        if self._mode == "local" or not self.remote_url:
            return "local", False
        if pass_ and not self._remote_passes:
            return "local", False
        if self._mode == "remote":
            return "remote", False
        from pipeline import mirror
        if not mirror.available():            # no local index yet: only the VM can render
            return "remote", False
        now = time.time()
        with self._lock:
            loc, rem = self.sides["local"], self.sides["remote"]
            stale = [s for s in (loc, rem) if s.inflight == 0 and now - s.last > REMEASURE_S]
            pick = stale[0] if stale else min((loc, rem), key=_Side.cost)
            pick.inflight += 1
            pick.last = now
            return pick.name, True

    def _timed(self, name: str, fn, counted: bool = False):
        """Run fn on side name and update its average. counted: _choose already added it to inflight."""
        side = self.sides[name]
        if not counted:
            with self._lock:
                side.inflight += 1
                side.last = time.time()
        load0 = side.inflight                 # tiles in flight there while this one runs (incl. itself)
        t0 = time.time()
        ok = False
        try:
            out = fn()
            ok = True
            return out
        finally:
            dt = time.time() - t0
            with self._lock:
                side.inflight -= 1
                if ok:
                    side.done += 1
                    side.avg = dt if side.avg is None else (1 - ALPHA) * side.avg + ALPHA * dt
                    rate = max(load0, side.inflight + 1) / max(dt, 0.05)       # Little's law: L / W
                    side.rate = rate if side.rate is None else (1 - ALPHA) * side.rate + ALPHA * rate
                else:
                    side.failed += 1                                           # back off from a failing side
                    side.rate = min(side.rate or PRIOR_RATE[name], PRIOR_RATE[name]) / 4

    def _local(self, slice_: int, order: int, npix: int, pass_: int | None):
        from . import render
        if pass_:
            return render.render(slice_, order, npix, pass_=pass_)
        if self.remote_url and self._mode == "balanced":    # combined tiles like the VM's: no mixed looks
            return render.render(slice_, order, npix, images=self.remote_images())
        return render.render(slice_, order, npix)

    def remote_images(self) -> int:
        if self._remote_images is None:
            try:
                self._remote_images = int(self._http().get(f"{self.remote_url}/health", timeout=10).json()["images_per_tile"])
            except Exception:  # noqa: BLE001 - VM down: our own setting, asked again next time
                from . import render
                return render.IMAGES_PER_TILE
        return self._remote_images

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
