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


def test_build_comets_reads_mpc_lines(tmp_path):
    lines = [
        "    CK23A030  2024 09 27.8438  0.391287  1.000183  308.5898   21.6839  139.0978  20261113   6.5  3.2  C/2023 A3 (Tsuchinshan-ATLAS)                            MPEC 2026-O98",
        "0029P         2026 02 13.5110  5.795420  0.043393   49.8000  312.4000    9.3700  20261113   5.5  4.0  29P/Schwassmann-Wachmann                                 MPEC",
    ]
    src = tmp_path / "CometEls.txt"
    src.write_text("\n".join(lines) + "\n")
    assert mpcorb.build_comets(src, tmp_path / "comets.npz") == 2
    with np.load(tmp_path / "comets.npz") as z:
        assert [n.decode() for n in z["name"]] == ["C/2023 A3 (Tsuchinshan-ATLAS)", "29P/Schwassmann-Wachmann"]
        assert z["tp"][0] == pytest.approx(2460581.3438, abs=1e-4)      # 2024-09-27.8438
        assert z["epoch"][0] == 2461357.5 and z["e"][0] == pytest.approx(1.000183)
    assert horizons_command("C/2023 A3 (Tsuchinshan-ATLAS)") == "DES=C/2023 A3;CAP;"
    assert horizons_command("29P/Schwassmann-Wachmann") == "DES=29P;CAP;NOFRAG;"


def _comet(q, e):
    c = {"q": np.array([q]), "e": np.array([e]), "tp": np.array([2461000.5]), "w": np.array([0.0]),
         "node": np.array([0.0]), "inc": np.array([0.0])}
    c["P"], c["Q"] = mpcorb._rotation(c["w"], c["node"], c["inc"])
    return c


@pytest.mark.parametrize("e", [0.5, 0.999, 1.0, 1.2])
def test_comet_state_at_perihelion_and_energy(e):
    c = _comet(1.5, e)
    r, v = mpcorb.comet_state(c, np.array([0]), 2461000.5, velocity=True)
    assert np.linalg.norm(r) == pytest.approx(1.5, rel=1e-9)            # at perihelion: r = q
    r, v = mpcorb.comet_state(c, np.array([0]), 2461060.5, velocity=True)
    # vis-viva: v^2 = GM (2/r - 1/a), 1/a = (1 - e) / q
    assert float(np.sum(v * v)) == pytest.approx(mpcorb.GM_SUN * (2 / np.linalg.norm(r) - (1 - e) / 1.5), rel=1e-6)


def test_integrate_handles_objects_with_different_epochs():
    el = _catalogue()
    for k in ("a", "e", "inc", "node", "w", "M", "n", "H", "G", "q"):
        el[k] = np.repeat(el[k], 2)
    el["epoch"] = np.array([2461200.5, 2461100.5])
    jd = 2461205.5
    r, _ = mpcorb.integrate(el, np.array([0, 1]), [jd])[jd]
    for i in (0, 1):
        r_kp = mpcorb.kepler_state(el, np.array([i]), jd)
        assert np.linalg.norm(r[:, i:i + 1] - r_kp) < 1e-4    # each from its own epoch (105 days for the second)
