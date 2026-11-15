"""One catalogue lookup/cache shared by chemistry maps and source analysis."""
from __future__ import annotations

import json
import threading
import time
from functools import lru_cache
from pathlib import Path

_retry_at = {}


@lru_cache(maxsize=64)
def _lock_for(path):
    return threading.Lock()


def catalogue(target_dir: Path, target: dict) -> dict:
    from pipeline.chemistry import REDSHIFT_VERSION, galaxy_redshifts
    from pipeline.fieldspectra import _write
    cache = Path(target_dir) / 'chemistry' / 'redshift.json'
    with _lock_for(str(cache)):
        if cache.is_file():
            try:
                hit = json.loads(cache.read_text(encoding='utf-8'))
                if hit.get('version') == REDSHIFT_VERSION:
                    return hit
            except (ValueError, OSError):
                pass
        if target.get('synthetic') or time.monotonic() < _retry_at.get(str(cache), 0):
            return {'galaxies': [], 'provenance': None}
        try:
            out = {**galaxy_redshifts(target, limit=200), 'version': REDSHIFT_VERSION}
        except Exception:  # catalogue availability must not block spectral analysis
            out = {'galaxies': [], 'provenance': None}
        if out.get('provenance') is not None:
            _write(cache, out)
        else:
            _retry_at[str(cache)] = time.monotonic() + 60
        return out
