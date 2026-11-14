"""T64: pipeline.releases (offline: the bucket listing is faked)."""
import json
import os

from pipeline import releases
from pipeline.query import Exposure


def _e(obs, coll, det=1, mjd=61000.0):
    return Exposure(obs_id=obs, collection=coll, detector=det, mjd_start=mjd, mjd_mid=mjd, time_utc="t", exptime_s=1,
                    wave_min_um=1, wave_max_um=2, epoch=1, fits_url="u", publisher_did="d")


def test_collections_add_only_new_release_folders():
    assert releases.collections(["dr1", "qr", "qr2", "qr3"]) == releases.IN_USE
    assert releases.collections(["dr1", "qr2", "qr3", "qr4", "dr2"])[4:] == (
        "spherex_qr4", "spherex_qr4_deep", "spherex_dr2", "spherex_dr2_deep")


def test_rank_and_dedupe():
    assert releases.rank("spherex_dr2") > releases.rank("spherex_dr1_deep") > releases.rank("spherex_qr4") > releases.rank("spherex_qr3")
    a, b, c, d = _e("x", "spherex_qr3"), _e("x", "spherex_dr2"), _e("x", "spherex_qr3", det=2), _e("y", "spherex_qr3")
    assert releases.dedupe([a, b, c, d]) == [b, c, d]


def test_bucket_releases_cache_and_offline(tmp_path, monkeypatch):
    cache = tmp_path / "releases.json"
    calls = []
    monkeypatch.setattr(releases, "_list_bucket", lambda: calls.append(1) or ["dr1", "qr2", "qr3"])
    assert releases.bucket_releases(cache)["releases"] == ["dr1", "qr2", "qr3"]
    assert releases.bucket_releases(cache)["releases"] == ["dr1", "qr2", "qr3"] and len(calls) == 1   # cached
    os.utime(cache, (0, 0))                                                                          # a day old
    def down():
        raise OSError("no network")
    monkeypatch.setattr(releases, "_list_bucket", down)
    assert releases.bucket_releases(cache)["releases"] == ["dr1", "qr2", "qr3"]                      # old answer kept
    cache.unlink()
    off = releases.bucket_releases(cache)
    assert off["retrieved_utc"] is None and set(off["releases"]) == releases.KNOWN
    assert json.loads(json.dumps(off))
