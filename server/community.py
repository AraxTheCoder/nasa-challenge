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

import json
import math
import os
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
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""
CLEAR_ONCE = True     # T146: remove the comments written before posting was closed, once per database


def _conn() -> sqlite3.Connection:
    global _db, _db_path
    path = ROOT / "community.db"
    if _db is None or _db_path != path:
        path.parent.mkdir(parents=True, exist_ok=True)
        if _db is not None:
            _db.close()
        _db = sqlite3.connect(path, check_same_thread=False)
        _db.row_factory = sqlite3.Row
        _db.executescript(SCHEMA)
        # Additive migration: keep the existing community database and all comments.
        columns = {r["name"] for r in _db.execute("PRAGMA table_info(comments)")}
        for name, definition in (("kind", "TEXT NOT NULL DEFAULT 'discussion'"),
                                 ("title", "TEXT NOT NULL DEFAULT ''"), ("evidence", "TEXT")):
            if name not in columns:
                _db.execute(f"ALTER TABLE comments ADD COLUMN {name} {definition}")
        _db.execute("CREATE INDEX IF NOT EXISTS comments_parent ON comments(parent_id)")
        _db.commit()
        _clear_once(_db, path)
        _db_path = path
    return _db


def _clear_once(db: sqlite3.Connection, path: Path) -> None:
    """T146: people trolled the public discussion (2026-11-15), so posting is closed and the comments written so far
    are removed, once per database. A copy of the whole database is saved next to it first
    (community-before-T146-<UTC time>.db). Visit counts and coverage stay."""
    if not CLEAR_ONCE or db.execute("SELECT 1 FROM meta WHERE key = 'comments_cleared_t146'").fetchone():
        return
    if db.execute("SELECT COUNT(*) FROM comments").fetchone()[0]:
        backup = path.with_name(f"community-before-T146-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.db")
        dst = sqlite3.connect(backup)
        try:
            db.backup(dst)
        finally:
            dst.close()
        db.execute("DELETE FROM comments")
    db.execute("INSERT INTO meta (key, value) VALUES ('comments_cleared_t146', ?)", (_now(),))
    db.commit()


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


# T146: posting is closed (people trolled the public site, 2026-11-15); the discussion stays readable.
# SPHEREX_COMMUNITY_POSTING=open in the server's environment opens it again (read at start).
POSTING_OPEN = os.environ.get("SPHEREX_COMMUNITY_POSTING", "closed").strip().lower() == "open"


def _valid_pix(pix: int) -> bool:
    return 0 <= pix < NPIX


COMMENT_FIELDS = "id, parent_id, author, text, ra_deg, dec_deg, fov_arcmin, created_utc, kind, title, evidence"


def _record(row) -> dict:
    result = dict(row)
    result["evidence"] = json.loads(result["evidence"]) if result.get("evidence") else None
    return result


def _evidence(value) -> dict | None:
    """An explicit, bounded snapshot, never a user-supplied URL or executable markup."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("evidence must be an object")
    allowed = {"target_id", "frame_a", "frame_b", "frame_a_time", "frame_b_time", "frame_a_obs", "frame_b_obs", "release",
               "wavelength_um", "field_ra_deg", "field_dec_deg",
               "field_size_arcmin", "synthetic", "layer", "flags"}
    if set(value) - allowed:
        raise ValueError("unknown evidence field")
    result = {}
    for key, val in value.items():
        if key in {"synthetic", "flags"}:
            if not isinstance(val, bool):
                raise ValueError(f"{key} must be a boolean")
        elif key in {"wavelength_um", "field_ra_deg", "field_dec_deg", "field_size_arcmin"}:
            bounds = {"wavelength_um": (0.1, 10), "field_ra_deg": (0, 360),
                      "field_dec_deg": (-90, 90), "field_size_arcmin": (0, 600)}
            low, high = bounds[key]
            if isinstance(val, bool) or not isinstance(val, (float, int)) or not math.isfinite(val):
                raise ValueError(f"{key} must be a finite number")
            if not low <= val <= high or (key == "field_ra_deg" and val == 360) or (key == "field_size_arcmin" and val == 0):
                raise ValueError(f"{key} out of range")
        elif not isinstance(val, str) or not val or len(val) > 180 or _CTRL.search(val):
            raise ValueError(f"{key} must be a nonempty string of at most 180 characters")
        result[key] = val
    return result


def _thread(pix: int) -> list[dict]:
    rows = [_record(r) for r in _conn().execute(
        f"SELECT {COMMENT_FIELDS} FROM comments WHERE pix = ? ORDER BY id", (pix,))]
    top = [r for r in rows if r["parent_id"] is None]
    for t in top:
        t["replies"] = [r for r in rows if r["parent_id"] == t["id"]]
    return top


COVERAGE_TIERS = (
    {"level": "unvisited", "label": "Unvisited", "min_browsers": 0, "max_browsers": 0},
    {"level": "light", "label": "Light attention", "min_browsers": 1, "max_browsers": 2},
    {"level": "moderate", "label": "Some attention", "min_browsers": 3, "max_browsers": 9},
    {"level": "high", "label": "High attention", "min_browsers": 10, "max_browsers": None},
)


def _coverage(browsers: int) -> dict:
    tier = next(t for t in reversed(COVERAGE_TIERS) if browsers >= t["min_browsers"])
    return {"level": tier["level"], "label": tier["label"], "browsers": browsers}


def _browsers(pix: int) -> int:
    return int(_conn().execute("SELECT COUNT(*) FROM seen WHERE pix = ?", (pix,)).fetchone()[0])


def _views(pix: int) -> int:
    r = _conn().execute("SELECT n FROM views WHERE pix = ?", (pix,)).fetchone()
    return int(r["n"]) if r else 0


@router.get("/api/community/tiles/{pix}")
def tile(pix: int):
    if not _valid_pix(pix):
        return _bad(f"tile must be 0..{NPIX - 1} (HEALPix order {ORDER}, nested)")
    with _lock:
        comments, views, coverage = _thread(pix), _views(pix), _coverage(_browsers(pix))
    n = sum(1 + len(c["replies"]) for c in comments)
    return {"status": "ready", "tile": {"order": ORDER, "pix": pix}, "center": tile_center(pix), "views": views,
            "n_comments": n, "comments": comments, "coverage": coverage, "posting_closed": not POSTING_OPEN}


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
        coverage = _coverage(_browsers(pix))
    return {"status": "ready", "views": views, "counted": counted, "coverage": coverage}


@router.post("/api/community/tiles/{pix}/comments")
async def comment(pix: int, request: Request):
    if not POSTING_OPEN:                         # T146
        return _bad("posting is closed for now; the discussion stays readable", 403)
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
    kind = body.get("kind", "discussion")
    if kind not in ("discussion", "second_look"):
        return _bad("kind must be discussion or second_look")
    title = _clean(body.get("title"), 121)
    if len(title) > 120:
        return _bad("a title can have at most 120 characters")
    try:
        evidence = _evidence(body.get("evidence"))
    except ValueError as exc:
        return _bad(str(exc))
    parent = body.get("parent_id")
    if parent is not None and (isinstance(parent, bool) or not isinstance(parent, int) or parent <= 0):
        return _bad("parent_id must be a positive integer")
    if parent is not None and kind != "discussion":
        return _bad("a reply cannot request a separate second look")
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
    if (ra is None) != (dec is None) or (fov is not None and ra is None):
        return _bad("attach both ra_deg and dec_deg, and a position when supplying fov_arcmin")
    if kind == "second_look" and (ra is None or dec is None or fov is None):
        return _bad("a second look needs a position and field of view")
    ip = limits.client_ip(request)
    now = time.time()
    with _lock:
        recent = [t for t in _posts.get(ip, []) if now - t < 600]
        if len(recent) >= POSTS_PER_10MIN:
            return JSONResponse({"status": "error", "message": "too many comments from your address; try again in a few minutes"},
                                status_code=429, headers={"Retry-After": "120"})
        db = _conn()
        if parent is not None:
            r = db.execute("SELECT pix, parent_id FROM comments WHERE id = ?", (parent,)).fetchone()
            if r is None or r["pix"] != pix:
                return _bad("the comment you reply to is not in this tile's thread")
            if r["parent_id"] is not None:
                parent = r["parent_id"]           # one level: a reply to a reply joins the same thread
        cur = db.execute("INSERT INTO comments (pix, parent_id, author, text, ra_deg, dec_deg, fov_arcmin, created_utc, kind, title, evidence) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (pix, parent, author, text, ra, dec, fov, _now(), kind, title,
                          json.dumps(evidence, allow_nan=False) if evidence is not None else None))
        db.commit()
        _posts[ip] = recent + [now]
        new = _record(db.execute(f"SELECT {COMMENT_FIELDS} FROM comments WHERE id = ?", (cur.lastrowid,)).fetchone())
    return JSONResponse({"status": "ready", "comment": new}, status_code=201)


@router.get("/api/community/recent")
def recent(limit: int = 20, unanswered: bool = False):
    limit = max(1, min(int(limit), 100))
    with _lock:
        db = _conn()
        where = ("WHERE kind = 'second_look' AND parent_id IS NULL AND NOT EXISTS "
                 "(SELECT 1 FROM comments AS reply WHERE reply.parent_id = comments.id)") if unanswered else ""
        latest = [_record(r) for r in db.execute(
            f"SELECT pix, {COMMENT_FIELDS} FROM comments {where} ORDER BY id DESC LIMIT ?", (limit,))]
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
        coverage = {p: _coverage(0) for p in ids}
        if ids:
            q = ",".join("?" * len(ids))
            for r in db.execute(f"SELECT pix, COUNT(*) AS n FROM seen WHERE pix IN ({q}) GROUP BY pix", ids):
                coverage[r["pix"]] = _coverage(int(r["n"]))
            for r in db.execute(f"SELECT pix, n FROM views WHERE pix IN ({q})", ids):
                out[r["pix"]]["views"] = int(r["n"])
            for r in db.execute(f"SELECT pix, COUNT(*) AS c FROM comments WHERE pix IN ({q}) GROUP BY pix", ids):
                out[r["pix"]]["comments"] = int(r["c"])
    return {"status": "ready", "tiles": {str(k): v for k, v in out.items()},
            "coverage": {str(k): v for k, v in coverage.items()}}


@router.get("/api/community/coverage")
def coverage_overview(limit: int = 40, sort: str = "least"):
    """Attention from distinct stored browser IDs, never a probability of scientific completeness."""
    if sort not in ("least", "most"):
        return _bad("sort must be least or most")
    limit = max(1, min(limit, 100))
    with _lock:
        db = _conn()
        visitors = {int(r["pix"]): int(r["n"]) for r in db.execute("SELECT pix, COUNT(*) AS n FROM seen GROUP BY pix")}
        visits = {int(r["pix"]): int(r["n"]) for r in db.execute("SELECT pix, n FROM views")}
        comments = {int(r["pix"]): int(r["n"]) for r in db.execute("SELECT pix, COUNT(*) AS n FROM comments GROUP BY pix")}
    summary = {t["level"]: 0 for t in COVERAGE_TIERS}
    summary["unvisited"] = NPIX - len(visitors)
    for n in visitors.values():
        summary[_coverage(n)["level"]] += 1
    # A coprime stride spreads equally unvisited recommendations across the sky instead of clustering at pix 0.
    candidates = list(range(NPIX)) if sort == "least" else list(set(visitors) | set(visits) | set(comments))
    ids = sorted(candidates, key=lambda p: (visitors.get(p, 0) * (1 if sort == "least" else -1), (p * 7919) % NPIX))[:limit]
    tiles = [{"pix": pix, "center": tile_center(pix), "views": visits.get(pix, 0), "n_comments": comments.get(pix, 0),
              "coverage": _coverage(visitors.get(pix, 0))} for pix in ids]
    return {"status": "ready", "order": ORDER, "total_tiles": NPIX, "summary": summary,
            "tiers": list(COVERAGE_TIERS), "basis": "distinct_browser_ids", "tiles": tiles}
