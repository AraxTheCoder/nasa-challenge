"""T33: read only what we need of a SPHEREx image from the AWS Open Data bucket, via HTTP Range.

The bucket `nasa-irsa-spherex` (https://registry.opendata.aws/spherex-qr/, also has dr1/) mirrors
IRSA's paths: ibe/data/spherex/<rest> -> https://nasa-irsa-spherex.s3.amazonaws.com/<rest>.
A level-2 file is ~61 MB (IMAGE, FLAGS, VARIANCE, ZODI, EPSF, WCS-WAVE). For one field we read:
  - the primary + IMAGE headers (WCS, ~26 kB),
  - the rows of IMAGE around the field (float32, uncompressed),
  - the same rows of FLAGS (RICE-compressed, one tile per row: we fetch only those tiles),
  - WCS-WAVE from the end of the file (a few kB).
VARIANCE, ZODI and EPSF (~80% of the bytes) are skipped. The result is written as a small FITS file
with IMAGE, FLAGS and WCS-WAVE, laid out like an IRSA cutout, so pipeline.build reads it unchanged.
Measured 2026-11-14 from Europe: 5-7 MB/s with 8-32 parallel requests and no errors (IRSA cutouts:
0.31 MB/s with >50% "503 Server busy").
"""
from __future__ import annotations

import gzip
import io
import math
import os
import threading
import time
from pathlib import Path

import numpy as np

S3_ROOT = "https://nasa-irsa-spherex.s3.amazonaws.com/"
IBE_PREFIX = "https://irsa.ipac.caltech.edu/ibe/data/spherex/"
BLOCK = 2880
TIMEOUT_S = 120
_SESSION = None


def s3_url(fits_url: str) -> str | None:
    return S3_ROOT + fits_url[len(IBE_PREFIX):] if fits_url.startswith(IBE_PREFIX) else None


def _session():
    global _SESSION
    if _SESSION is None:
        import requests
        from requests.adapters import HTTPAdapter

        _SESSION = requests.Session()
        _SESSION.mount("https://", HTTPAdapter(pool_connections=4, pool_maxsize=64, max_retries=3))
    return _SESSION


def _get(url: str, start: int, end: int | None = None) -> bytes:
    """Bytes [start, end) ; start < 0 means the last -start bytes."""
    rng = f"bytes={start}" if start < 0 else f"bytes={start}-{end - 1}"
    r = _session().get(url, headers={"Range": rng}, timeout=TIMEOUT_S)
    r.raise_for_status()
    if r.status_code != 206:
        raise RuntimeError(f"no range support: HTTP {r.status_code}")
    return r.content


def _header_at(url: str, offset: int, guess_blocks: int = 12):
    """Parse the FITS header starting at offset. Returns (header, header size in bytes)."""
    from astropy.io import fits

    buf = b""
    n = guess_blocks
    while True:
        buf = _get(url, offset, offset + n * BLOCK)
        for k in range(0, len(buf), 80):
            if buf[k:k + 80] == b"END" + b" " * 77:
                size = math.ceil((k + 80) / BLOCK) * BLOCK
                return fits.Header.fromstring(buf[:k + 80].decode("ascii")), size
        if len(buf) < n * BLOCK:
            raise RuntimeError("FITS header without END")
        n *= 2


def _two_headers(head: bytes, url: str):
    """Parse the primary header and the IMAGE header that follows it from the first bytes of a file.
    Returns (IMAGE header, its size, offset of the IMAGE HDU). Falls back to a second request."""
    from astropy.io import fits

    def end_of(buf, start):
        for k in range(start, len(buf), 80):
            if buf[k:k + 80] == b"END" + b" " * 77:
                return math.ceil((k + 80) / BLOCK) * BLOCK
        return None

    s0 = end_of(head, 0)
    e1 = end_of(head, s0) if s0 else None
    if s0 and e1:
        return fits.Header.fromstring(head[s0:e1].decode("ascii")), e1 - s0, s0
    if not s0:
        _, s0 = _header_at(url, 0, 2)
    himg, simg = _header_at(url, s0, 12)
    return himg, simg, s0


def _data_size(h) -> int:
    nax = [h.get(f"NAXIS{i}", 0) for i in range(1, h.get("NAXIS", 0) + 1)]
    n = abs(h["BITPIX"]) // 8 * (math.prod(nax) if nax else 0) * h.get("GCOUNT", 1) + h.get("PCOUNT", 0)
    return math.ceil(n / BLOCK) * BLOCK


def _flags_rows(url: str, offset: int, hdr, hsize: int, y0: int, y1: int, x0: int, x1: int) -> np.ndarray:
    """Decompress rows y0..y1-1 of a RICE tile-compressed FLAGS HDU (one tile per row)."""
    from astropy.io import fits

    if not (hdr.get("ZIMAGE") and hdr.get("ZTILE2", 0) == 1 and hdr.get("ZTILE1") == hdr.get("ZNAXIS1")):
        raise RuntimeError("unexpected FLAGS layout")
    data0 = offset + hsize
    rowlen = hdr["NAXIS1"]                       # 8: one 1PB descriptor (count, offset) per tile
    heap0 = data0 + hdr.get("THEAP", rowlen * hdr["NAXIS2"])
    desc = np.frombuffer(_get(url, data0 + y0 * rowlen, data0 + y1 * rowlen), ">i4").reshape(-1, 2)
    lo, hi = int(desc[:, 1].min()), int((desc[:, 1] + desc[:, 0]).max())
    heap = _get(url, heap0 + lo, heap0 + hi)
    # Re-pack the tiles we got into a small compressed HDU and let astropy decompress it.
    new_desc = desc.copy()
    new_desc[:, 1] -= lo
    h = hdr.copy()
    for k in ("CHECKSUM", "DATASUM", "ZDATASUM", "ZHECKSUM", "THEAP"):
        h.remove(k, ignore_missing=True)
    h["NAXIS2"] = y1 - y0
    h["ZNAXIS2"] = y1 - y0
    h["PCOUNT"] = len(heap)
    table = new_desc.astype(">i4").tobytes() + heap
    blob = (fits.PrimaryHDU().header.tostring().encode() + h.tostring().encode()
            + table + b"\0" * (-len(table) % BLOCK))
    with fits.open(io.BytesIO(blob)) as hd:
        return np.asarray(hd[1].data)[:, x0:x1].astype(np.int32)


def fetch_cutout(fits_url: str, ra: float, dec: float, size_deg: float, dest: Path,
                 via: str | None = None) -> Path:
    """Write a small cutout FITS (IMAGE, FLAGS, WCS-WAVE) of size_deg around (ra, dec) to dest."""
    from astropy.io import fits
    from astropy.wcs import WCS

    url = s3_url(fits_url)
    if url is None:
        raise ValueError(f"not an IRSA SPHEREx path: {fits_url}")

    h0, s0 = _header_at(url, 0, 2)
    off_img = s0
    himg, simg = _header_at(url, off_img, 12)
    nx, ny = himg["NAXIS1"], himg["NAXIS2"]
    wcs = WCS(himg)

    # Rows/cols of the detector that cover the field (corners + centre, small margin).
    h = size_deg / 2
    c = math.cos(math.radians(dec)) or 1e-6
    pts = [(ra + dx / c, dec + dy) for dx in (-h, 0, h) for dy in (-h, 0, h)]
    px, py = wcs.all_world2pix([p[0] for p in pts], [p[1] for p in pts], 0)
    x0, x1 = max(0, int(np.floor(px.min())) - 2), min(nx, int(np.ceil(px.max())) + 3)
    y0, y1 = max(0, int(np.floor(py.min())) - 2), min(ny, int(np.ceil(py.max())) + 3)
    if x1 - x0 < 4 or y1 - y0 < 4:
        raise LookupError("field is not on this image")

    bpp = abs(himg["BITPIX"]) // 8
    dtype = {-32: ">f4", -64: ">f8", 32: ">i4", 16: ">i2"}[himg["BITPIX"]]
    data0 = off_img + simg
    raw = _get(url, data0 + y0 * nx * bpp, data0 + y1 * nx * bpp)
    img = np.frombuffer(raw, dtype).reshape(y1 - y0, nx)[:, x0:x1].astype(np.float32)
    if "BZERO" in himg or "BSCALE" in himg:
        img = img * himg.get("BSCALE", 1.0) + himg.get("BZERO", 0.0)

    off_flags = data0 + _data_size(himg)
    hflags, sflags = _header_at(url, off_flags, 8)
    flags = _flags_rows(url, off_flags, hflags, sflags, y0, y1, x0, x1)

    # WCS-WAVE is the last HDU and small: read the tail of the file and find its header.
    tail = _get(url, -6 * BLOCK)            # files are whole FITS blocks, so the tail is aligned
    starts = [k for k in range(0, len(tail), BLOCK) if tail.startswith(b"XTENSION= 'BINTABLE'", k)
              and b"'WCS-WAVE'" in tail[k:k + 2 * BLOCK]]
    if not starts:
        raise RuntimeError("WCS-WAVE not found at the end of the file")
    with fits.open(io.BytesIO(fits.PrimaryHDU().header.tostring().encode() + tail[starts[-1]:])) as hd:
        wave = fits.BinTableHDU(data=hd["WCS-WAVE"].data.copy(), header=hd["WCS-WAVE"].header.copy())

    # Shift every pixel-based WCS (sky, 0-based active pixels "A", wavelength table "W").
    hcut = himg.copy()
    for suffix in ("", "A", "W"):
        if f"CRPIX1{suffix}" in hcut:
            hcut[f"CRPIX1{suffix}"] -= x0
            hcut[f"CRPIX2{suffix}"] -= y0
    for key in ("CHECKSUM", "DATASUM"):
        hcut.remove(key, ignore_missing=True)
    out = fits.HDUList([
        fits.PrimaryHDU(header=h0),
        fits.ImageHDU(img, header=hcut, name="IMAGE"),
        fits.ImageHDU(flags, name="FLAGS"),
        wave,
    ])
    out[0].header["S3SRC"] = (url[:68], "read via HTTP Range")
    out[0].header["S3CUT"] = (f"x {x0}:{x1} y {y0}:{y1}", "detector pixels kept (0-based)")
    if via:
        out[0].header["VIA"] = (via[:68], "cut by this host next to the bucket (T57)")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(f".{threading.get_ident()}.s3.part")
    out.writeto(tmp, overwrite=True)
    tmp.replace(dest)
    return dest


# -- T57: the same cutout, cut by the team VM next to the bucket -----------------------------------
# From Europe the bucket gives ~3 MB/s in total and each read takes whole detector rows (~2-3 MB per
# image for a 478 kB cutout). The VM in us-east4 reads at 38-95 MB/s and sends back only the finished
# cutout, gzipped (~200 kB). Same file as fetch_cutout writes, so everything downstream is unchanged.
REMOTE: str | None = os.environ.get("SPHEREX_CUTOUTS_REMOTE") or None   # set by `python -m server`
REMOTE_RETRY_S = 60          # after a VM failure, go straight to the bucket for this long
_remote_down_until = 0.0
OFF_IMAGE = "off-image"      # X-Cutout header value: the field is not on this image (-> LookupError)
MISSING = "missing"          # X-Cutout: the path is not in the bucket (-> NotInBucket)
S3_ERROR = "s3-error"        # X-Cutout: the VM is fine, this one read failed (no pause)
# NotInBucket (defined with S3Image below) is raised for MISSING; find_in_bucket finds the real path.


def is_not_found(e: Exception) -> bool:
    return getattr(getattr(e, "response", None), "status_code", None) == 404


def week_version(rel: str, week: str) -> str | None:
    """The processing version folder of a week (e.g. dr1, 2025W47_2A -> l2b-v27-2026-208), by listing
    the bucket (one request, ~0.6 s from Europe; TAP took 20-145 s on 2026-11-14). Reprocessed
    `l2b_retry-...` folders hold only a few images, so the plain one wins."""
    import re
    prefix = f"{rel}/level2/{week}/"
    r = _session().get(S3_ROOT, params={"list-type": "2", "prefix": prefix, "delimiter": "/"}, timeout=(5, 30))
    r.raise_for_status()
    versions = re.findall(r"<Prefix>" + re.escape(prefix) + r"([^/<]+)/</Prefix>", r.text)
    plain = sorted(v for v in versions if "retry" not in v)
    return (plain or sorted(versions) or [None])[-1]


def find_in_bucket(fits_url: str) -> str | None:
    """The real IRSA-style URL of an image whose derived path is wrong (other processing version,
    e.g. l2b_retry-...), by listing the bucket: one request for the week's versions, one per version.
    ~0.6 s per request from Europe instead of 20-40 s for a TAP lookup."""
    import re
    url = s3_url(fits_url)
    m = re.match(r"(.*/level2/[^/]+/)([^/]+)/(\d+)/(level2_.+?D\d+)_spx_", url or "")
    if not m:
        return None
    week, old_ver, det, stem = m.groups()
    rel_week = week[len(S3_ROOT):]

    def listing(prefix: str, delimiter: str | None = None) -> str:
        params = {"list-type": "2", "prefix": prefix}
        if delimiter:
            params["delimiter"] = delimiter
        r = _session().get(S3_ROOT, params=params, timeout=(5, 30))
        r.raise_for_status()
        return r.text

    versions = re.findall(r"<Prefix>" + re.escape(rel_week) + r"([^/<]+)/</Prefix>", listing(rel_week, "/"))
    for ver in sorted(versions, key=lambda v: (v == old_ver, "retry" not in v)):   # retries first
        keys = re.findall(r"<Key>([^<]+\.fits)</Key>", listing(f"{rel_week}{ver}/{det}/{stem}_spx_"))
        if keys:
            return IBE_PREFIX + keys[0]
    return None


def remote_available() -> bool:
    return bool(REMOTE) and time.time() >= _remote_down_until


def fetch_cutout_remote(fits_url: str, ra: float, dec: float, size_deg: float, dest: Path,
                        base: str | None = None) -> Path:
    """fetch_cutout, done by the tilegen service at `base` (default REMOTE). Raises LookupError if the
    field is not on the image, RuntimeError (and pauses remote use) if the VM can't help."""
    global _remote_down_until
    base = (base or REMOTE or "").rstrip("/")
    try:
        r = _session().get(f"{base}/cutout", params={"url": fits_url, "ra": f"{ra:.7f}",
                                                     "dec": f"{dec:.7f}", "size": f"{size_deg:.4f}"},
                           timeout=(5, TIMEOUT_S))
    except Exception as e:  # noqa: BLE001 - connection refused, timeout, DNS
        _remote_down_until = time.time() + REMOTE_RETRY_S
        raise RuntimeError(f"cutout VM unreachable: {e}") from e
    kind = r.headers.get("X-Cutout")
    if r.status_code == 404 and kind == OFF_IMAGE:
        raise LookupError("field is not on this image")
    if r.status_code == 404 and kind == MISSING:
        raise NotInBucket(f"not in the bucket: {fits_url.rsplit('/', 1)[-1]}")
    if r.status_code != 200:
        if kind is None:          # no answer from tilegen itself: VM/proxy down, or an old VM without /cutout
            _remote_down_until = time.time() + REMOTE_RETRY_S
        raise RuntimeError(f"cutout VM: HTTP {r.status_code} {r.text[:120]}")
    data = gzip.decompress(r.content)
    if not data.startswith(b"SIMPLE"):
        raise RuntimeError("cutout VM: answer is not a FITS file")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(f".{threading.get_ident()}.vm.part")
    tmp.write_bytes(data)
    tmp.replace(dest)
    return dest


# -- T42: whole-image access with cached headers and row chunks (for live map tiles) -------------

from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

# 64 rows: less over-read (and RICE decoding of FLAGS) at the edges of a map tile than 128.
CHUNK_ROWS = 64
# Decoded chunks kept in memory (~0.6 MB each); disk copies are written in the background.
CHUNK_MEM = int(os.environ.get("S3_CHUNK_MEM", "1500"))
_mem_chunks: "OrderedDict[str, tuple]" = OrderedDict()
_mem_lock = threading.Lock()
_disk_writer = ThreadPoolExecutor(1, thread_name_prefix="chunk-writer")
_fetchers = ThreadPoolExecutor(16, thread_name_prefix="chunk-image-rows")
CHUNK_ROOT = Path("data/raw/s3chunks")


class NotInBucket(FileNotFoundError):
    """The path is not in the bucket (e.g. a reprocessed l2b_retry file): resolve the real path."""


class S3Image:
    """One level-2 image in the bucket: WCS from its header, IMAGE/FLAGS rows in cached chunks.

    Headers (~26 kB) are cached as JSON, rows in chunks of CHUNK_ROWS full-width rows (~1 MB of
    IMAGE + its FLAGS tiles) under data/raw/s3chunks/<hash>/, so map tiles next to each other reuse
    what their neighbours already read."""

    _mem: dict[str, "S3Image"] = {}

    def __init__(self, fits_url: str, root: Path = CHUNK_ROOT):
        import hashlib
        import json

        from astropy.io import fits
        from astropy.wcs import WCS

        self.url = s3_url(fits_url)
        if self.url is None:
            raise ValueError(f"not an IRSA SPHEREx path: {fits_url}")
        self.dir = root / hashlib.sha1(self.url.encode()).hexdigest()[:20]
        meta_f = self.dir / "meta.json"
        if meta_f.exists():
            meta = json.loads(meta_f.read_text(encoding="utf-8"))
        else:
            try:
                head = _get(self.url, 0, 16 * BLOCK)          # primary + IMAGE header in one go
            except Exception as e:
                if "404" in str(e):
                    raise NotInBucket(self.url) from e
                raise
            himg, simg, s0 = _two_headers(head, self.url)
            data0 = s0 + simg
            off_flags = data0 + _data_size(himg)
            hflags, sflags = _header_at(self.url, off_flags, 8)
            meta = {"himg": himg.tostring(), "data0": data0, "off_flags": off_flags,
                    "hflags": hflags.tostring(), "sflags": sflags}
            self.dir.mkdir(parents=True, exist_ok=True)
            tmp = meta_f.with_name(f"meta.{threading.get_ident()}.part")
            tmp.write_text(json.dumps(meta), encoding="utf-8")
            tmp.replace(meta_f)
        self.himg = fits.Header.fromstring(meta["himg"])
        self.hflags = fits.Header.fromstring(meta["hflags"])
        self.data0, self.off_flags, self.sflags = meta["data0"], meta["off_flags"], meta["sflags"]
        self.nx, self.ny = self.himg["NAXIS1"], self.himg["NAXIS2"]
        self.wcs = WCS(self.himg)

    @classmethod
    def get(cls, fits_url: str) -> "S3Image":
        im = cls._mem.get(fits_url)
        if im is None:
            im = cls._mem[fits_url] = cls(fits_url)
        return im

    _locks: dict = {}
    _locks_guard = threading.Lock()

    def chunk(self, i: int):
        """(image rows, bad-pixel mask, median, robust sigma) of chunk i (rows i*CHUNK_ROWS...).

        Single-flight: tiles asking for the same chunk at once wait for one download."""
        key = f"{self.dir}/{i}"
        with S3Image._locks_guard:
            lk = S3Image._locks.setdefault(key, threading.Lock())
        with lk:
            return self._chunk(i)

    def _chunk(self, i: int):
        key = f"{self.dir}/{CHUNK_ROWS}/{i}"
        with _mem_lock:
            hit = _mem_chunks.get(key)
            if hit is not None:
                _mem_chunks.move_to_end(key)
                return hit
        f = self.dir / f"r{CHUNK_ROWS}_{i:03d}.npz"
        if f.exists():
            z = np.load(f)
            out = (z["img"], z["bad"], float(z["med"]), float(z["sig"]))
            self._remember(key, out)
            return out
        y0, y1 = i * CHUNK_ROWS, min(self.ny, (i + 1) * CHUNK_ROWS)
        bpp = abs(self.himg["BITPIX"]) // 8
        dtype = {-32: ">f4", -64: ">f8", 32: ">i4", 16: ">i2"}[self.himg["BITPIX"]]
        # image rows and the FLAGS tiles (descriptors -> heap) are independent: fetch in parallel
        raw_f = _fetchers.submit(_get, self.url, self.data0 + y0 * self.nx * bpp, self.data0 + y1 * self.nx * bpp)
        flags = _flags_rows(self.url, self.off_flags, self.hflags, self.sflags, y0, y1, 0, self.nx)
        img = np.frombuffer(raw_f.result(), dtype).reshape(y1 - y0, self.nx).astype(np.float32)
        bad = ((flags & HW_MASK) != 0) | ~np.isfinite(img)
        good = img[~bad]
        med = float(np.median(good)) if good.size else 0.0
        sig = float(1.4826 * np.median(np.abs(good - med))) if good.size else 1.0
        out = (img, bad, med, max(sig, 1e-6))
        self._remember(key, out)
        _disk_writer.submit(self._write, f, out)       # off the critical path (slow VM disk)
        return out

    @staticmethod
    def _remember(key: str, value: tuple) -> None:
        with _mem_lock:
            _mem_chunks[key] = value
            _mem_chunks.move_to_end(key)
            while len(_mem_chunks) > CHUNK_MEM:
                _mem_chunks.popitem(last=False)

    @staticmethod
    def _write(f: Path, value: tuple) -> None:
        try:
            img, bad, med, sig = value
            tmp = f.with_name(f"{f.stem}.{threading.get_ident()}.part.npz")
            np.savez(tmp, img=img, bad=bad, med=med, sig=sig)
            tmp.replace(f)
        except OSError:
            pass


HW_MASK = sum(1 << b for b in (0, 1, 2, 6, 9, 10, 11, 14, 17, 25, 26, 27, 28))   # as pipeline.build
