"""Parse user-entered coordinates and derive the cache id (CONTRACTS v0.3 "Target id and cache")."""
from __future__ import annotations

import re

SIZE_MIN, SIZE_MAX, SIZE_DEFAULT = 5, 60, 15

_SEP = re.compile(r"[hdms:°'\"′″\s]+", re.IGNORECASE)


class CoordError(ValueError):
    pass


def _sexagesimal(text: str) -> tuple[float, bool, bool]:
    """Return (absolute value in units of the first field, negative?, was_sexagesimal?)."""
    t = text.strip()
    neg = t.startswith("-")
    if t[:1] in "+-":
        t = t[1:]
    parts = [p for p in _SEP.split(t) if p]
    if not parts or len(parts) > 3:
        raise CoordError(f"cannot parse {text!r}")
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        raise CoordError(f"cannot parse {text!r}") from None
    if any(n < 0 for n in nums) or any(n >= 60 for n in nums[1:]):
        raise CoordError(f"cannot parse {text!r}")
    value = nums[0] + sum(n / 60 ** (i + 1) for i, n in enumerate(nums[1:]))
    is_sexa = len(parts) > 1 or bool(re.search(r"[hdms:°'\"′″]", t, re.IGNORECASE))
    return value, neg, is_sexa


def parse_ra(text: str) -> float:
    """Degrees, or hours if sexagesimal (`08h55m10.8s`, `08:55:10.8`, `8 55 10.8`)."""
    value, neg, sexa = _sexagesimal(text)
    if neg:
        raise CoordError("RA must not be negative")
    deg = value * 15.0 if sexa and not re.search(r"d|°", text, re.IGNORECASE) else value
    if not 0 <= deg < 360:
        raise CoordError("RA must be in [0, 360) deg / [0, 24) h")
    return deg


def parse_dec(text: str) -> float:
    value, neg, _ = _sexagesimal(text)
    deg = -value if neg else value
    if not -90 <= deg <= 90:
        raise CoordError("Dec must be in [-90, 90] deg")
    return deg


def parse_size(text: str | None) -> int:
    if text in (None, ""):
        return SIZE_DEFAULT
    try:
        size = float(text)
    except ValueError:
        raise CoordError(f"size must be a number of arcmin, got {text!r}") from None
    if not SIZE_MIN <= size <= SIZE_MAX:
        raise CoordError(f"size must be {SIZE_MIN}-{SIZE_MAX} arcmin")
    return int(round(size))


def target_id(ra_deg: float, dec_deg: float, size_arcmin: int) -> tuple[str, float, float]:
    """Return (id, rounded ra, rounded dec). Rounds to 1e-4 deg so equal requests share a cache entry."""
    ra_i = int(round(ra_deg * 1e4)) % 3_600_000
    dec_i = int(round(dec_deg * 1e4))
    sign = "m" if dec_i < 0 else "p"
    return f"c{ra_i:07d}-{sign}{abs(dec_i):06d}-s{size_arcmin}", ra_i / 1e4, dec_i / 1e4
