"""T120: citizen collaboration per map tile (CONTRACTS: "Community").

The tool is for citizen scientists (scope Decision 2026-11-14): they find things, so they need a place to talk about
them. Every tile of the map (HEALPix order 6, nested; the tiles the map builds fields for, ~55′) has a view counter
and a discussion thread: comments with one level of replies, each optionally carrying a position and field of view
("look here").

    GET  /api/community/tiles/<pix>              {"tile", "center", "views", "comments": [...]} (replies nested)
    POST /api/community/tiles/<pix>/view          count a view (once per browser id per tile per hour) -> {"views"}
    POST /api/community/tiles/<pix>/comments      {"author", "text", "parent_id"?, "ra_deg"?, "dec_deg"?, "fov_arcmin"?}
    GET  /api/community/recent?limit=            latest comments everywhere, most viewed / most discussed tiles
    GET  /api/community/counts?pix=1,2,3         views + comment counts for several tiles (map badges)

Stored in SQLite under data/community/ (not a cache: never swept). Plain text only: the viewer renders it as text,
never as HTML. Lengths are limited and posting is rate-limited per address.
"""
from __future__ import annotations

import math
import re
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from . import limits

router = APIRouter()
ORDER = 6
NPIX = 12 * 4 ** ORDER
MAX_TEXT = 2000
MAX_AUTHOR = 40
VIEW_WINDOW_S = 3600            # one view per browser per tile per hour
POSTS_PER_10MIN = 10            # per address
ROOT = Path("data/community")
_db: sqlite3.Connection | None = None
_db_path: Path | None = None
_lock = threading.Lock()
_posts: dict[str, list[float]] = {}
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

SCHEMA = """
CREATE TABLE IF NOT EXISTS comments (
  id INTEGER PRIMARY KEY AUTOINCREMENT, pix INTEGER NOT NULL, parent_id INTEGER, author TEXT NOT NULL,
  text TEXT NOT NULL, ra_deg REAL, dec_deg REAL, fov_arcmin REAL, created_utc TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS comments_pix ON comments(pix);
CREATE TABLE IF NOT EXISTS views (pix INTEGER PRIMARY KEY, n INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS seen (pix INTEGER NOT NULL, who TEXT NOT NULL, at REAL NOT NULL, PRIMARY KEY (pix, who));
"""


def _conn() -> sqlite3.Connection:
    global _db, _db_path
    path = ROOT / "community.db"
    if _db is None or _db_path != path:
        path.parent.mkdir(parents=True, exist_ok=True)
        _db = sqlite3.connect(path, check_same_thread=False)
        _db.row_factory = sqlite3.Row
        _db.executescript(SCHEMA)
        _db_path = path
    return _db


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean(s, n: int) -> str:
    return _CTRL.sub("", str(s or "")).strip()[:n]


def tile_center(pix: int) -> dict:
    from astropy_healpix import HEALPix
    import astropy.units as u
    lon, lat = HEALPix(nside=2 ** ORDER, order="nested").healpix_to_lonlat(pix)
    return {"ra_deg": round(float(lon.to_value(u.deg)), 4), "dec_deg": round(float(lat.to_value(u.deg)), 4)}


def _bad(msg: str, code: int = 400) -> JSONResponse:
    return JSONResponse({"status": "error", "message": msg}, status_code=code)


def _valid_pix(pix: int) -> bool:
    return 0 <= pix < NPIX


def _thread(pix: int) -> list[dict]:
    rows = [dict(r) for r in _conn().execute(
        "SELECT id, parent_id, author, text, ra_deg, dec_deg, fov_arcmin, created_utc FROM comments WHERE pix = ? "
        "ORDER BY id", (pix,))]
    top = [r for r in rows if r["parent_id"] is None]
    for t in top:
        t["replies"] = [r for r in rows if r["parent_id"] == t["id"]]
    return top


def _views(pix: int) -> int:
    r = _conn().execute("SELECT n FROM views WHERE pix = ?", (pix,)).fetchone()
    return int(r["n"]) if r else 0


@router.get("/api/community/tiles/{pix}")
def tile(pix: int):
    if not _valid_pix(pix):
        return _bad(f"tile must be 0..{NPIX - 1} (HEALPix order {ORDER}, nested)")
    with _lock:
        comments, views = _thread(pix), _views(pix)
    n = sum(1 + len(c["replies"]) for c in comments)
    return {"status": "ready", "tile": {"order": ORDER, "pix": pix}, "center": tile_center(pix), "views": views,
            "n_comments": n, "comments": comments}


@router.post("/api/community/tiles/{pix}/view")
async def view(pix: int, request: Request):
    if not _valid_pix(pix):
        return _bad(f"tile must be 0..{NPIX - 1}")
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001 - no body: the address stands in for the browser
        body = {}
    who = _clean((body or {}).get("browser") if isinstance(body, dict) else "", 64) or limits.client_ip(request)
    now = time.time()
    with _lock:
        db = _conn()
        r = db.execute("SELECT at FROM seen WHERE pix = ? AND who = ?", (pix, who)).fetchone()
        counted = r is None or now - float(r["at"]) > VIEW_WINDOW_S
        if counted:
            db.execute("INSERT INTO seen (pix, who, at) VALUES (?, ?, ?) ON CONFLICT(pix, who) DO UPDATE SET at = ?",
                       (pix, who, now, now))
            db.execute("INSERT INTO views (pix, n) VALUES (?, 1) ON CONFLICT(pix) DO UPDATE SET n = n + 1", (pix,))
            db.commit()
        views = _views(pix)
    return {"status": "ready", "views": views, "counted": counted}


@router.post("/api/community/tiles/{pix}/comments")
async def comment(pix: int, request: Request):
    if not _valid_pix(pix):
        return _bad(f"tile must be 0..{NPIX - 1}")
    try:
        body = await request.json()
        assert isinstance(body, dict)
    except Exception:  # noqa: BLE001
        return _bad("the body must be a JSON object")
    text, author = _clean(body.get("text"), MAX_TEXT + 1), _clean(body.get("author"), MAX_AUTHOR) or "anonymous"
    if not text:
        return _bad("the comment is empty")
    if len(text) > MAX_TEXT:
        return _bad(f"a comment can have at most {MAX_TEXT} characters")
    pos = []
    for k in ("ra_deg", "dec_deg", "fov_arcmin"):
        v = body.get(k)
        try:
            v = None if v is None else float(v)
        except (TypeError, ValueError):
            return _bad(f"{k} must be a number")
        if v is not None and not math.isfinite(v):
            return _bad(f"{k} must be finite")
        pos.append(v)
    ra, dec, fov = pos
    if ra is not None and not 0 <= ra < 360 or dec is not None and not -90 <= dec <= 90 or fov is not None and not 0 < fov <= 600:
        return _bad("position out of range (ra 0..360, dec -90..90, fov 0..600 arcmin)")
    ip = limits.client_ip(request)
    now = time.time()
    with _lock:
        recent = [t for t in _posts.get(ip, []) if now - t < 600]
        if len(recent) >= POSTS_PER_10MIN:
            return JSONResponse({"status": "error", "message": "too many comments from your address; try again in a few minutes"},
                                status_code=429, headers={"Retry-After": "120"})
        db = _conn()
        parent = body.get("parent_id")
        if parent is not None:
            r = db.execute("SELECT pix, parent_id FROM comments WHERE id = ?", (parent,)).fetchone()
            if r is None or r["pix"] != pix:
                return _bad("the comment you reply to is not in this tile's thread")
            if r["parent_id"] is not None:
                parent = r["parent_id"]           # one level: a reply to a reply joins the same thread
        cur = db.execute("INSERT INTO comments (pix, parent_id, author, text, ra_deg, dec_deg, fov_arcmin, created_utc) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (pix, parent, author, text, ra, dec, fov, _now()))
        db.commit()
        _posts[ip] = recent + [now]
        new = dict(db.execute("SELECT id, parent_id, author, text, ra_deg, dec_deg, fov_arcmin, created_utc FROM comments "
                              "WHERE id = ?", (cur.lastrowid,)).fetchone())
    return JSONResponse({"status": "ready", "comment": new}, status_code=201)


@router.get("/api/community/recent")
def recent(limit: int = 20):
    limit = max(1, min(int(limit), 100))
    with _lock:
        db = _conn()
        latest = [dict(r) for r in db.execute(
            "SELECT id, pix, parent_id, author, text, ra_deg, dec_deg, fov_arcmin, created_utc FROM comments "
            "ORDER BY id DESC LIMIT ?", (limit,))]
        discussed = [dict(r) for r in db.execute(
            "SELECT pix, COUNT(*) AS n_comments, MAX(created_utc) AS last_utc FROM comments GROUP BY pix "
            "ORDER BY n_comments DESC, last_utc DESC LIMIT ?", (limit,))]
        viewed = [dict(r) for r in db.execute("SELECT pix, n AS views FROM views ORDER BY n DESC LIMIT ?", (limit,))]
    for row in latest + discussed + viewed:
        row["center"] = tile_center(row["pix"])
    return {"status": "ready", "latest": latest, "most_discussed": discussed, "most_viewed": viewed}


@router.get("/api/community/counts")
def counts(pix: str):
    try:
        ids = sorted({int(p) for p in pix.split(",") if p.strip()})[:200]
    except ValueError:
        return _bad("pix must be a comma-separated list of tile numbers")
    if any(not _valid_pix(p) for p in ids):
        return _bad(f"tiles must be 0..{NPIX - 1}")
    with _lock:
        db = _conn()
        out = {p: {"views": 0, "comments": 0} for p in ids}
        if ids:
            q = ",".join("?" * len(ids))
            for r in db.execute(f"SELECT pix, n FROM views WHERE pix IN ({q})", ids):
                out[r["pix"]]["views"] = int(r["n"])
            for r in db.execute(f"SELECT pix, COUNT(*) AS c FROM comments WHERE pix IN ({q}) GROUP BY pix", ids):
                out[r["pix"]]["comments"] = int(r["c"])
    return {"status": "ready", "tiles": {str(k): v for k, v in out.items()}}
