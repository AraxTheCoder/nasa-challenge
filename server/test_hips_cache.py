"""pytest server/test_hips_cache.py (T143): the map server's images / tiles kept in memory by size, 8-bit images."""
import json

import numpy as np
from PIL import Image

from server import hips


def test_budget_drops_least_recently_used_by_size():
    calls = []
    cache = hips._BudgetCache(1)                              # 1 MB

    @cache
    def img(k):
        calls.append(k)
        return np.zeros(600 * 1024, np.uint8), np.zeros(1, bool)  # ~0.6 MB each

    img(1); img(1)
    assert calls == [1] and img.cache_info().hits == 1
    img(2)                                                    # 1.2 MB > 1 MB: the older one goes
    img(2)
    img(1)
    assert calls == [1, 2, 1]
    assert cache.used <= cache.budget and img.cache_info().currsize == 1
    img.cache_clear()
    assert cache.used == 0 and img.cache_info().currsize == 0


def _field(tmp_path, frames):
    d = tmp_path / "t"
    d.mkdir()
    for f, value in frames:
        Image.fromarray(np.dstack([np.full((8, 8), value, np.uint8), np.full((8, 8), 255, np.uint8)]), "LA") \
            .save(d / f["image"])
    t = {"center": {"ra_deg": 10.0, "dec_deg": 0.0}, "size_arcmin": 1, "frames": [f for f, _ in frames],
         "image": {"width": 8, "height": 8, "pixel_scale_arcsec": 6.15}}
    (d / "target.json").write_text(json.dumps(t), encoding="utf-8")
    return str(d), (d / "target.json").stat().st_mtime


def test_images_are_8_bit_and_colour_does_not_overflow(tmp_path):
    hips._images.clear()
    f = lambda i, det: {"id": f"f00{i}", "epoch": 1, "detector": det, "image": f"f{i}.png", "mjd": 1.0 + i,  # noqa: E731
                        "time_utc": "2025-06-01T00:00:00"}
    d, m = _field(tmp_path, [(f(0, 5), 200), (f(1, 6), 220), (f(2, 3), 90)])
    grey, cov = hips.frame_image(d, m, "f000")
    assert grey.dtype == np.uint8 and grey[0, 0] == 200 and cov.all()
    mean, _ = hips.epoch_image(d, m, 1, None)
    assert mean.dtype == np.uint8 and mean[0, 0] == round((200 + 220 + 90) / 3)
    rgb, _ = hips.colour_image(d, m, 1)
    assert rgb.dtype == np.uint8 and rgb[0, 0, 0] == 210      # R = mean of D5 (200) and D6 (220), not wrapped at 256
    diff, both = hips.diff_image(d, m, "f000", "f001")
    assert diff.dtype == np.uint8 and both.all()
