"""T94: keep disk caches under a size cap, so the disk never fills up.

The row-chunk cache (data/raw/s3chunks), the rendered tiles and the VM's cutouts are caches: everything in
them can be fetched or rendered again. Without a cap they grew to 24 GB on the 30 GB tile VM on 2026-11-14,
the disk filled up and every tile that needed new rows failed (HTTP 500), so the map had holes.

    start([(Path("data/raw/s3chunks"), 8e9), (Path("data/tilegen_cache"), 4e9)], keep_free=3e9)

Every `interval` seconds each folder is trimmed to its cap, least recently used files first; when the disk
has less than `keep_free` bytes free, more is deleted (least recently used first, across the folders).
"Used" = the file's mtime: written, or read from the cache (the readers call `used(path)`; the file system's
own access time is unreliable: Linux relatime updates it once a day at most, Windows often not at all).
"""
from __future__ import annotations

import os
import shutil
import threading
import time
from pathlib import Path


USED_EVERY_S = 600   # a cache hit refreshes a file's mtime at most this often (one utime per file per 10 min)


def used(path) -> None:
    """Mark a cache file as just used, so the janitor keeps it (least recently used goes first)."""
    try:
        if time.time() - os.stat(path).st_mtime > USED_EVERY_S:
            os.utime(path, None)
    except OSError:
        pass


def _files(root: Path) -> list[tuple[float, int, Path]]:
    out = []
    if not root.exists():
        return out
    for dirpath, _dirs, names in os.walk(root):
        for n in names:
            p = Path(dirpath) / n
            try:
                st = p.stat()
            except OSError:
                continue
            out.append((st.st_mtime, st.st_size, p))
    return out


def trim(folders: list[tuple[Path, float]], keep_free: float = 0.0) -> int:
    """Delete the least recently used files (oldest mtime, see `used`) until every folder is under its cap
    and the disk has keep_free bytes free.
    Returns the number of bytes deleted."""
    deleted = 0
    pools = []
    for root, cap in folders:
        files = sorted(_files(Path(root)))
        total = sum(s for _, s, _ in files)
        i = 0
        while total > cap and i < len(files):
            _, size, p = files[i]
            i += 1
            try:
                p.unlink()
                total -= size
                deleted += size
            except OSError:
                pass
        pools.extend(files[i:])
    if keep_free and folders:
        where = next((Path(r) for r, _ in folders if Path(r).exists()), Path("."))
        try:
            free = shutil.disk_usage(where).free
        except OSError:
            free = keep_free
        for _, size, p in sorted(pools):
            if free >= keep_free:
                break
            try:
                p.unlink()
                free += size
                deleted += size
            except OSError:
                pass
    return deleted


def start(folders: list[tuple[Path, float]], keep_free: float = 3e9, interval: float = 300.0) -> threading.Thread:
    """Trim now (in the background) and then every `interval` seconds."""
    def run():
        while True:
            try:
                n = trim(folders, keep_free)
                if n:
                    print(f"[janitor] freed {n / 1e9:.2f} GB of cache", flush=True)
            except Exception as e:  # noqa: BLE001 - never take the service down
                print(f"[janitor] {e}", flush=True)
            time.sleep(interval)
    t = threading.Thread(target=run, daemon=True, name="cache-janitor")
    t.start()
    return t
