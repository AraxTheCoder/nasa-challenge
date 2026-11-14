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

import io
import math
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


def fetch_cutout(fits_url: str, ra: float, dec: float, size_deg: float, dest: Path) -> Path:
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
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".s3.part")
    out.writeto(tmp, overwrite=True)
    tmp.replace(dest)
    return dest


# -- T42: whole-image access with cached headers and row chunks (for live map tiles) -------------

CHUNK_ROWS = 128
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
                _, s0 = _header_at(self.url, 0, 2)
            except Exception as e:
                if "404" in str(e):
                    raise NotInBucket(self.url) from e
                raise
            himg, simg = _header_at(self.url, s0, 12)
            data0 = s0 + simg
            off_flags = data0 + _data_size(himg)
            hflags, sflags = _header_at(self.url, off_flags, 8)
            meta = {"himg": himg.tostring(), "data0": data0, "off_flags": off_flags,
                    "hflags": hflags.tostring(), "sflags": sflags}
            self.dir.mkdir(parents=True, exist_ok=True)
            tmp = meta_f.with_suffix(".part")
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

    def chunk(self, i: int):
        """(image rows, bad-pixel mask, median, robust sigma) of chunk i (rows i*CHUNK_ROWS...)."""
        f = self.dir / f"c{i:02d}.npz"
        if f.exists():
            z = np.load(f)
            return z["img"], z["bad"], float(z["med"]), float(z["sig"])
        y0, y1 = i * CHUNK_ROWS, min(self.ny, (i + 1) * CHUNK_ROWS)
        bpp = abs(self.himg["BITPIX"]) // 8
        dtype = {-32: ">f4", -64: ">f8", 32: ">i4", 16: ">i2"}[self.himg["BITPIX"]]
        raw = _get(self.url, self.data0 + y0 * self.nx * bpp, self.data0 + y1 * self.nx * bpp)
        img = np.frombuffer(raw, dtype).reshape(y1 - y0, self.nx).astype(np.float32)
        flags = _flags_rows(self.url, self.off_flags, self.hflags, self.sflags, y0, y1, 0, self.nx)
        bad = ((flags & HW_MASK) != 0) | ~np.isfinite(img)
        good = img[~bad]
        med = float(np.median(good)) if good.size else 0.0
        sig = float(1.4826 * np.median(np.abs(good - med))) if good.size else 1.0
        tmp = f.with_suffix(".part.npz")
        np.savez(tmp, img=img, bad=bad, med=med, sig=max(sig, 1e-6))
        tmp.replace(f)
        return img, bad, med, max(sig, 1e-6)


HW_MASK = sum(1 << b for b in (0, 1, 2, 6, 9, 10, 11, 14, 17, 25, 26, 27, 28))   # as pipeline.build
