"""T60: SPHEREx quality flags in plain words.

Every level-2 image has a FLAGS plane: one bit per reason a pixel may be unreliable. Names and bits are the
mask planes of the FLAGS header (MSKNnnnn / MSKMnnnn, read from a DR1 image on 2026-11-15); the words are ours.
`kind`: "bad" = the value can't be trusted (these are the bits of build.HW_MASK), "warn" = look twice,
"info" = says something about the pixel, not a defect.
"""
from __future__ import annotations

import numpy as np

# bit: (name, kind, plain words)
FLAG_BITS: dict[int, tuple[str, str, str]] = {
    0: ("TRANSIENT", "bad", "a sudden jump during the exposure: a cosmic ray, or something passing"),
    1: ("OVERFLOW", "bad", "saturated: too bright for the detector"),
    2: ("SUR_ERROR", "bad", "error in the onboard processing"),
    6: ("NONFUNC", "bad", "dead pixel"),
    7: ("DICHROIC", "warn", "low sensitivity at the edge of the beam splitter"),
    9: ("MISSING_DATA", "bad", "data lost onboard"),
    10: ("HOT", "bad", "hot pixel"),
    11: ("COLD", "bad", "pixel with anomalously low signal"),
    12: ("FULLSAMPLE", "info", "full readout history available"),
    14: ("PHANMISS", "bad", "a readout artefact (phantom) could not be corrected"),
    15: ("NONLINEAR", "warn", "so bright that the value is only approximate"),
    17: ("PERSIST", "bad", "afterglow of a bright source seen just before"),
    19: ("OUTLIER", "warn", "differs from the other exposures of this spot: an artefact, or something that moved or changed"),
    20: ("CROSSTALK", "warn", "electronic echo of a bright source elsewhere on the detector"),
    21: ("SOURCE", "info", "a catalogued source is here"),
    22: ("GHOST", "warn", "ghost image of a bright source in the field"),
    23: ("GHOST_FPA", "warn", "ghost image of a bright source on another detector"),
    24: ("GHOST_EXT", "warn", "stray light from a bright source outside the field"),
    25: ("STREAK", "bad", "a streak: a satellite or a fast-moving object"),
    26: ("BLOOM", "bad", "charge spilling from a saturated star"),
    27: ("SNOWBALL", "bad", "a large cosmic-ray hit"),
    28: ("HALO", "bad", "halo around a transient hit"),
}
NAMES = {name: (bit, kind, words) for bit, (name, kind, words) in FLAG_BITS.items()}


def names(value: int) -> list[str]:
    """Flag names set in a FLAGS value (or the OR of several pixels), lowest bit first."""
    v = int(value)
    return [FLAG_BITS[b][0] if b in FLAG_BITS else f"BIT{b}" for b in range(32) if v >> b & 1]


def in_pixels(flag_values) -> list[str]:
    """Names of every flag set in any of the given pixels."""
    a = np.asarray(flag_values, dtype=np.int64)
    return names(int(np.bitwise_or.reduce(a.ravel()))) if a.size else []


def legend() -> list[dict]:
    return [{"name": n, "bit": b, "kind": k, "meaning": w} for b, (n, k, w) in sorted(FLAG_BITS.items())]


def meanings(rows: list[dict]) -> dict:
    """{name: {kind, meaning}} for every flag that occurs in the measurements `rows` (their "flags" lists)."""
    seen = sorted({n for r in rows for n in r.get("flags") or []}, key=lambda n: NAMES.get(n, (99,))[0])
    return {n: {"kind": NAMES[n][1], "meaning": NAMES[n][2]} if n in NAMES else {"kind": "warn", "meaning": "unnamed flag"}
            for n in seen}
