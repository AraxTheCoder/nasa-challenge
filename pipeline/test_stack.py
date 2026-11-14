"""pytest pipeline/test_stack.py (T23 shift-and-stack) on the synthetic fixture, no network."""
from pathlib import Path

import numpy as np

from pipeline.stack import shift_and_stack

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "targets" / "demo-synthetic"


def test_mover_sharp_only_in_shifted_stack():
    plain, shifted, info = shift_and_stack(FIXTURE)
    assert info["object"] == "Fake asteroid" and info["synthetic"]
    x, y = (int(round(v)) for v in info["ref_xy"])
    # the plain median removes the mover; the shifted stack keeps it bright at its reference spot
    assert shifted[y, x] > np.nanpercentile(shifted, 99)
    assert plain[y, x] < np.nanpercentile(plain, 90)
