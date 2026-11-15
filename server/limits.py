"""T58: limits for a public Live API (CONTRACTS v0.20). Off unless the server runs with --public.

A public server must not be made to download unlimited SPHEREx data, flood JPL / SIMBAD, or fill its disk:

- **Rate limit per IP** on every API call (token bucket): `api` requests and the much more numerous map `tile`
  requests have separate allowances. Beyond: 429 + Retry-After.
- **New expensive work per IP and globally:** starting a field build, an all-exposure spectrum or a field's
  spectra costs one "job" from the IP's job bucket; and no more than MAX_ACTIVE such jobs run at once on the
  whole server. Polling a running job or reading a cached result is free. Beyond: 429 (this IP) or 503
  {"status": "busy"} + Retry-After (everyone).
- **refresh=1 and POST /api/settings only with the admin token** (env SPHEREX_ADMIN_TOKEN, `?token=` or header
  `X-Admin-Token`); without it `refresh` is ignored and settings answer 403.
- **Cache cap:** a background sweep keeps data/targets, data/raw/cutouts, data/raw/s3chunks, data/spectra,
  data/field_spectra and data/sky_labels under `--cache-gb` / SPHEREX_CACHE_GB (default 20 with --public),
  evicting the least recently used first; a field that is being built is never evicted. The orbit catalogue,
  image index and HiPS tile cache are left alone. T97: the cap also works without --public (a team server that
  runs for days): set the size and only the sweep runs, none of the other limits.

Configured once at start (`configure(...)`, from server/__main__.py); every check is a no-op when disabled, so the
team's servers behave exactly as before.
"""
from __future__ import annotations

import hmac
import math
import os
import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse


@dataclass
class Config:
    enabled: bool = False
    token: str | None = None
    api_per_min: float = 300.0          # ordinary API calls per IP
    tile_per_min: float = 2400.0        # map tiles per IP (a pan at deep zoom asks for dozens at once)
    jobs_per_hour: float = 30.0         # new expensive jobs per IP ...
    jobs_burst: float = 10.0            # ... of which this many at once
    max_active: int = 4                 # expensive jobs running on the whole server
    cache_gb: float = 0.0               # 0 = no cache sweep (T97: its own switch, also without --public)
    sweep_s: float = 600.0
    min_free_gb: float = 5.0            # T125: free disk space kept on top of the size cap (0 = off)
    disk_check_s: float = 60.0          # T125: how often free space is checked (cheap)
    trust_proxy: bool = False           # take the client IP from X-Forwarded-For (behind a reverse proxy)


CFG = Config()
_active: list = []                      # callables -> number of running expensive jobs (registered by modules)
_buckets: dict[tuple[str, str], list[float]] = {}
_lock = threading.Lock()


def configure(enabled: bool, **kw) -> Config:
    global CFG
    CFG = Config(enabled=enabled, **{k: v for k, v in kw.items() if v is not None})
    if CFG.token is None:
        CFG.token = os.environ.get("SPHEREX_ADMIN_TOKEN") or None
    with _lock:
        _buckets.clear()
    return CFG


def register_active(fn) -> None:
    """fn() -> number of expensive jobs running now (builder, spectra, field spectra)."""
    _active.append(fn)


def active_jobs() -> int:
    n = 0
    for fn in _active:
        try:
            n += int(fn())
        except Exception:  # noqa: BLE001 - a counter must never break a request
            pass
    return n


def client_ip(request: Request) -> str:
    if CFG.trust_proxy:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "?"


def _take(ip: str, kind: str, rate_per_s: float, burst: float) -> float:
    """Token bucket: 0 if allowed (one token taken), else seconds until the next token."""
    now = time.monotonic()
    with _lock:
        tokens, last = _buckets.get((ip, kind), [burst, now])
        tokens = min(burst, tokens + (now - last) * rate_per_s)
        if tokens >= 1:
            _buckets[(ip, kind)] = [tokens - 1, now]
            return 0.0
        _buckets[(ip, kind)] = [tokens, now]
        return (1 - tokens) / rate_per_s


def _too_many(wait: float, what: str) -> JSONResponse:
    s = max(1, math.ceil(wait))
    return JSONResponse({"status": "error", "message": f"too many {what} from your address; try again in {s} s"},
                        status_code=429, headers={"Retry-After": str(s)})


def busy(retry_s: int = 20) -> JSONResponse:
    return JSONResponse({"status": "busy", "message": "the server is busy with other people's requests; "
                                                      f"try again in {retry_s} s"},
                        status_code=503, headers={"Retry-After": str(retry_s)})


async def middleware(request: Request, call_next):
    """Per-IP request rate (api / tile)."""
    if CFG.enabled and request.url.path.startswith("/api/") and request.url.path != "/api/health":
        tile = request.url.path.startswith(("/api/sky/", "/api/hips/"))
        per_min = CFG.tile_per_min if tile else CFG.api_per_min
        wait = _take(client_ip(request), "tile" if tile else "api", per_min / 60.0, max(20.0, per_min / 4))
        if wait:
            return _too_many(wait, "map tiles" if tile else "requests")
    return await call_next(request)


def new_job(request: Request | None) -> JSONResponse | None:
    """Call before starting an expensive job; None = go ahead, else the answer to send instead."""
    if not CFG.enabled:
        return None
    if active_jobs() >= CFG.max_active:
        return busy()
    if request is not None:
        wait = _take(client_ip(request), "job", CFG.jobs_per_hour / 3600.0, CFG.jobs_burst)
        if wait:
            return _too_many(wait, "new fields / spectra")
    return None


def is_admin(request: Request | None) -> bool:
    if not CFG.enabled:
        return True
    if request is None or not CFG.token:
        return False
    given = request.query_params.get("token") or request.headers.get("x-admin-token") or ""
    return hmac.compare_digest(given, CFG.token)


# ---------- cache cap ----------

def _entries(data_root: Path) -> list[Path]:
    out: list[Path] = []
    for sub, kind in (("targets", "dir"), ("raw/cutouts", "dir"), ("raw/s3chunks", "any"), ("spectra", "file"),
                      ("field_spectra", "file"), ("sky_labels", "file")):
        d = data_root / sub
        if not d.is_dir():
            continue
        out += [p for p in d.iterdir() if kind == "any" or (p.is_dir() if kind == "dir" else p.is_file())]
    return out


def _size(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def _last_used(p: Path) -> float:
    st = p.stat()
    t = max(st.st_mtime, st.st_atime)
    if p.is_dir():
        for f in p.iterdir():
            fs = f.stat()
            t = max(t, fs.st_mtime, fs.st_atime)
    return t


def sweep(data_root: Path, cap_bytes: int, busy_ids=frozenset(), free_bytes_needed: int = 0) -> dict:
    """Evict least-recently-used cache entries until the total is under cap_bytes and (T125) at least
    free_bytes_needed more bytes are freed. Returns what it did."""
    entries = []
    for p in _entries(data_root):
        try:
            entries.append((_last_used(p), _size(p), p))
        except OSError:
            continue
    total = sum(s for _, s, _ in entries)          # a field being built counts, but is never evicted
    removed, freed = 0, 0
    for _, s, p in sorted(entries, key=lambda e: e[0]):
        if total <= cap_bytes and freed >= free_bytes_needed:
            break
        if p.parent.name == "targets" and p.name in busy_ids:
            continue
        try:
            shutil.rmtree(p) if p.is_dir() else p.unlink()
        except OSError:
            continue
        total -= s
        freed += s
        removed += 1
    return {"total_bytes": total, "removed": removed, "freed_bytes": freed}


def free_shortfall(data_root: Path) -> int:
    """T125: bytes missing to keep min_free_gb free on the disk holding data_root (0 = enough, or the guard is off)."""
    if CFG.min_free_gb <= 0:
        return 0
    try:
        free = shutil.disk_usage(data_root if data_root.exists() else data_root.parent).free
    except OSError:
        return 0
    return max(0, int(CFG.min_free_gb * 1e9) - free)


def start_sweeper(data_root: Path, busy_ids_fn=lambda: frozenset()) -> threading.Thread | None:
    if CFG.cache_gb <= 0:               # T97: runs whenever a size is set, with or without --public
        return None

    def loop():
        last = 0.0
        while True:
            try:
                short = free_shortfall(data_root)
                if short > 0 or time.monotonic() - last >= CFG.sweep_s:
                    r = sweep(data_root, int(CFG.cache_gb * 1e9), busy_ids_fn(), short)
                    last = time.monotonic()
                    if r["removed"]:
                        why = f" (disk had {short / 1e9:.2f} GB too little free)" if short > 0 else ""
                        print(f"cache sweep: removed {r['removed']} entries, {r['freed_bytes'] / 1e9:.2f} GB; "
                              f"now {r['total_bytes'] / 1e9:.2f} GB{why}", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"cache sweep failed: {e}", flush=True)
            time.sleep(min(CFG.sweep_s, CFG.disk_check_s) if CFG.min_free_gb > 0 else CFG.sweep_s)

    t = threading.Thread(target=loop, daemon=True, name="cache-sweep")
    t.start()
    return t
