"""pytest pipeline/test_labels_tracks.py (T38): vectorised tracks match the per-object maths, no network."""
import math

import numpy as np

from pipeline.labels import J2000_MJD, Grid, _tracks

TARGET = {"center": {"ra_deg": 269.4463, "dec_deg": 4.7682},
          "image": {"width": 146, "height": 146, "pixel_scale_arcsec": 6.15}}
FRAMES = [{"id": "a", "mjd": 60900.0}, {"id": "b", "mjd": 61265.25}]


def test_barnard_moves_north_10_arcsec_per_year():
    g = Grid(TARGET)
    # Barnard's Star, J2000 + proper motion (mas/yr)
    R, D, X, Y, inside = _tracks(g, FRAMES, [269.4520769586187], [4.693364966576667], [-801.551], [10362.394], J2000_MJD)
    assert inside[0]
    dy_arcsec = (D[0, 1] - D[0, 0]) * 3600
    assert abs(dy_arcsec - 10.362) < 0.01            # one year apart
    assert Y[0, 1] < Y[0, 0]                         # north = up = smaller y
    assert abs((Y[0, 0] - Y[0, 1]) * 6.15 - dy_arcsec) < 0.1


def test_many_objects_one_call_and_outside_is_dropped():
    g = Grid(TARGET)
    n = 5000
    ra = np.full(n, 269.4463); dec = np.linspace(4.7682 - 1, 4.7682 + 1, n)  # 2 deg strip, field is 15'
    R, D, X, Y, inside = _tracks(g, FRAMES, ra, dec, np.zeros(n), np.zeros(n), J2000_MJD)
    assert R.shape == (n, 2)
    frac = inside.mean()
    assert 0.10 < frac < 0.16                        # ~15'/120' of the strip (plus margins)
    assert math.isclose(X[n // 2, 0], (146 - 1) / 2, abs_tol=1)
