"""T51: local MPC catalogue (offline; a tiny hand-made catalogue, no MPCORB download)."""
import gzip
import math

import numpy as np
import pytest

from detect import mpcorb
from detect.known_objects import horizons_command


def test_unpack_epoch():
    assert mpcorb._unpack_epoch("K2669") == 2461200.5      # 2026-06-09
    assert mpcorb._unpack_epoch("K25BL") == 2461000.5      # 2025-11-21
    assert mpcorb._unpack_epoch("J9611") == 2450083.5      # 1996-01-01


@pytest.mark.parametrize("readable, name, cmd", [
    ("(433) Eros", "433 Eros", "433;"),
    ("(428715) 2008 RG38", "428715 (2008 RG38)", "428715;"),
    ("2023 UC67", "(2023 UC67)", "DES=2023 UC67;"),
    ("(1) Ceres", "1 Ceres", "1;"),
])
def test_display_name_round_trips_to_horizons(readable, name, cmd):
    assert mpcorb.display_name(readable) == name
    assert horizons_command(name) == cmd


def _catalogue(**over):
    el = {"a": np.array([2.5]), "e": np.array([0.0]), "inc": np.array([0.0]), "node": np.array([0.0]),
          "w": np.array([0.0]), "M": np.array([0.0]), "epoch": np.array([2461200.5]),
          "n": np.array([math.degrees(mpcorb.K_GAUSS / 2.5 ** 1.5)]), "H": np.array([15.0]), "G": np.array([0.15])}
    el.update({k: np.array([v]) for k, v in over.items()})
    el["q"] = el["a"] * (1 - el["e"])
    return el


def test_kepler_circular_orbit_radius_and_speed():
    el = _catalogue()
    r, v = mpcorb.kepler_state(el, np.array([0]), 2461300.5, velocity=True)
    assert np.linalg.norm(r) == pytest.approx(2.5, abs=1e-9)
    assert np.linalg.norm(v) == pytest.approx(mpcorb.K_GAUSS / math.sqrt(2.5), rel=1e-9)


def test_kepler_eccentric_converges():
    el = _catalogue(e=0.95, a=3.0, M=math.degrees(1.0))   # catalogue M is in degrees
    el["n"] = np.array([math.degrees(mpcorb.K_GAUSS / 3.0 ** 1.5)])
    r = mpcorb.kepler_state(el, np.array([0]), 2461200.5)
    # r = a (1 - e cos E); check against a direct solve
    E = 1.0
    for _ in range(100):
        E -= (E - 0.95 * math.sin(E) - 1.0) / (1 - 0.95 * math.cos(E))
    assert np.linalg.norm(r) == pytest.approx(3.0 * (1 - 0.95 * math.cos(E)), rel=1e-9)


def test_integrate_close_to_two_body_over_a_few_days():
    el = _catalogue()
    jd = 2461205.5
    r_nb, _ = mpcorb.integrate(el, np.array([0]), [jd])[jd]
    r_kp = mpcorb.kepler_state(el, np.array([0]), jd)
    assert np.linalg.norm(r_nb - r_kp) < 1e-6        # planets barely matter over 5 days


def test_build_reads_mpcorb_lines(tmp_path):
    header = "MPCORB header\n" + "-" * 160 + "\n"
    line = ("29197   15.20  0.15 K2669  75.28553  183.90432  283.34152    0.06925  0.1783809  0.25591741"
            "   2.4569868  0 E2026-TN5  2429  22 1991-2026 0.78 M-v 3Ek MPCORBFIT  0000  (29197) Gleim"
            "              202605\n")
    src = tmp_path / "MPCORB.DAT.gz"
    with gzip.open(src, "wt") as f:
        f.write(header + line + "\n")
    out = tmp_path / "orbits.npz"
    assert mpcorb.build(src, out) == 1
    with np.load(out) as z:
        assert z["name"][0].decode() == "29197 Gleim"
        assert z["epoch"][0] == 2461200.5 and z["a"][0] == pytest.approx(2.4569868)
        assert z["H"][0] == 15.2 and z["e"][0] == pytest.approx(0.1783809)
