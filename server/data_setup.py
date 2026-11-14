"""T71: the Live API fetches and builds its local data itself, in a background thread at start.

- MPC orbit catalogue (`detect.mpcorb`, ~95 MB download, ~10 s build): when missing or older than
  ORBITS_MAX_AGE_DAYS (MPC updates it daily; a week-old copy is still sub-arcsecond for this).
- SPHEREx image index (`pipeline.mirror`, harvest + build, a few minutes): when missing.

Until each is ready the server uses the fallbacks (SkyBoT for known objects, IRSA TAP for image
searches), so nothing waits for this. Started from `python -m server`, not from `create_app`, so the
tests never download anything. `python -m server --no-data-setup` turns it off.
"""
from __future__ import annotations

import threading
import time
import traceback
from pathlib import Path

ORBITS_MAX_AGE_DAYS = 7.0


def _log(msg: str) -> None:
    print(f"[data setup] {msg}", flush=True)


def ensure_orbits(root: Path) -> None:
    from detect import mpcorb
    age = mpcorb.age_days(root)
    if age is not None and age <= ORBITS_MAX_AGE_DAYS:
        _log(f"orbit catalogue ok ({age:.1f} days old)")
        return
    _log("orbit catalogue " + ("missing" if age is None else f"{age:.0f} days old") + ": downloading from the MPC")
    t0 = time.time()
    mpcorb.fetch(root)
    n = mpcorb.build(root / "MPCORB.DAT.gz", root / "orbits.npz")
    c = mpcorb.build_comets(root / "CometEls.txt", root / "comets.npz")
    _log(f"orbit catalogue ready: {n} asteroids, {c} comets in {time.time() - t0:.0f} s")


def ensure_image_index(root: Path) -> None:
    from pipeline import mirror
    if mirror.available(root):
        _log("SPHEREx image index ok")
        return
    _log("SPHEREx image index missing: harvesting from IRSA (a few minutes; searches use IRSA TAP until then)")
    t0 = time.time()
    mirror.harvest(root)
    mirror.build(root)
    _log(f"SPHEREx image index ready in {time.time() - t0:.0f} s")


def start(data_root: Path) -> threading.Thread:
    """Run both checks in one background thread (one after the other: both are network-heavy)."""
    def run():
        for name, fn, sub in (("orbit catalogue", ensure_orbits, "mpcorb"),
                              ("image index", ensure_image_index, "mirror")):
            try:
                fn(data_root / sub)
            except Exception as e:  # noqa: BLE001 - the server keeps working with the fallbacks
                _log(f"{name} failed ({type(e).__name__}: {e}); using the fallback, retried on the next start")
                traceback.print_exc()

    th = threading.Thread(target=run, daemon=True, name="data-setup")
    th.start()
    return th
