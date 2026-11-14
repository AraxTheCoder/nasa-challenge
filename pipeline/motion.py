"""T23: motion summary + plain-words motion class for anything with one position per frame.

Works for catalogue labels (T19), known objects (T07) and detections (T06/T08) alike: it only needs
the per-frame positions (`frame_id`, `ra_deg`, `dec_deg`, `x`, `y`) and the target's frames.

    from pipeline.motion import summarize
    label["motion"] = summarize(label["positions"], target["frames"], pixel_scale_arcsec=6.15)

Classes (rough, from the scales in TEAM.md Ideas, 2026-11-14):
    still              moves < STILL_PX over the whole series
    fast mover         > FAST_ARCSEC_PER_HR within one epoch: asteroid / comet-like, crosses a 15'
                       field in hours, so it is only seen in one burst of exposures
    distant body?      clear jump between epochs (> JUMP_ARCSEC) but slow within an epoch: what a body
                       hundreds of AU away looks like from Earth's orbit (question mark: unconfirmed)
    proper motion      steady, slow, straight: a nearby star or brown dwarf (Barnard's Star 10.4"/yr)
"""
from __future__ import annotations

import math

STILL_PX = 0.3
FAST_ARCSEC_PER_HR = 1.0
JUMP_ARCSEC = 60.0
MIN_PAIR_HR = 0.01      # 36 s: pairs inside one ~2 min visit count
NOISE_ARCSEC = 3.0      # half a pixel: smaller shifts between two frames are noise, not motion


def _sep_arcsec(ra1, dec1, ra2, dec2) -> float:
    d = math.radians
    a = math.sin(d(dec2 - dec1) / 2) ** 2 + math.cos(d(dec1)) * math.cos(d(dec2)) * math.sin(d(ra2 - ra1) / 2) ** 2
    return math.degrees(2 * math.asin(min(1.0, math.sqrt(a)))) * 3600


def _pa_deg(ra1, dec1, ra2, dec2) -> float:
    """Position angle of the motion, degrees east of north."""
    d = math.radians
    y = math.sin(d(ra2 - ra1)) * math.cos(d(dec2))
    x = math.cos(d(dec1)) * math.sin(d(dec2)) - math.sin(d(dec1)) * math.cos(d(dec2)) * math.cos(d(ra2 - ra1))
    return (math.degrees(math.atan2(y, x)) + 360) % 360


COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def summarize(positions: list[dict], frames: list[dict], pixel_scale_arcsec: float) -> dict | None:
    """Motion over the series: shift, rate, direction, class. None if fewer than 2 positions."""
    mjd = {f["id"]: f["mjd"] for f in frames}
    epoch = {f["id"]: f.get("epoch") for f in frames}
    pts = sorted((p for p in positions if p.get("frame_id") in mjd), key=lambda p: mjd[p["frame_id"]])
    if len(pts) < 2:
        return None
    a, b = pts[0], pts[-1]
    shift = _sep_arcsec(a["ra_deg"], a["dec_deg"], b["ra_deg"], b["dec_deg"])
    days = mjd[b["frame_id"]] - mjd[a["frame_id"]]
    shift_px = shift / pixel_scale_arcsec
    # how far it ever gets from where it started (a looping body can end near its start)
    reach = max(_sep_arcsec(a["ra_deg"], a["dec_deg"], p["ra_deg"], p["dec_deg"]) for p in pts)

    # fastest motion within one epoch (consecutive frames of the same epoch)
    # fastest motion within one epoch. SPHEREx exposures in a visit are ~2 min apart, so short pairs
    # count (>= MIN_PAIR_HR), but only if the shift beats position noise (>= NOISE_ARCSEC); also
    # first-to-last per epoch (T42, from Mati's T08 finding).
    within = 0.0
    def rate(p, q):
        hrs = (mjd[q["frame_id"]] - mjd[p["frame_id"]]) * 24
        sep = _sep_arcsec(p["ra_deg"], p["dec_deg"], q["ra_deg"], q["dec_deg"])
        return sep / hrs if hrs >= MIN_PAIR_HR and sep >= NOISE_ARCSEC else 0.0
    for p, q in zip(pts, pts[1:]):
        if epoch[p["frame_id"]] == epoch[q["frame_id"]]:
            within = max(within, rate(p, q))
    for ep in {epoch[p["frame_id"]] for p in pts}:
        e = [p for p in pts if epoch[p["frame_id"]] == ep]
        if len(e) > 1:
            within = max(within, rate(e[0], e[-1]))
    # biggest jump between the mean positions of two consecutive epochs
    by_ep: dict = {}
    for p in pts:
        by_ep.setdefault(epoch[p["frame_id"]], []).append(p)
    means = [(sum(p["ra_deg"] for p in v) / len(v), sum(p["dec_deg"] for p in v) / len(v)) for _, v in sorted(by_ep.items(), key=lambda kv: (kv[0] is None, kv[0]))]
    jump = max((_sep_arcsec(*m, *n) for m, n in zip(means, means[1:])), default=0.0)

    if reach / pixel_scale_arcsec < STILL_PX and within < FAST_ARCSEC_PER_HR:
        cls, note = "still", "doesn't move visibly in this series"
    elif within >= FAST_ARCSEC_PER_HR:
        cls, note = "fast mover", f"{within:.1f}\"/h within an epoch: asteroid- or comet-like"
    elif jump >= JUMP_ARCSEC:
        cls, note = "distant body?", f"jumps {jump:.0f}\" between epochs but drifts slowly within one"
    else:
        cls, note = "proper motion", "steady slow motion: a nearby star or brown dwarf"
    pa = _pa_deg(a["ra_deg"], a["dec_deg"], b["ra_deg"], b["dec_deg"]) if shift > 0 else None
    return {
        "shift_arcsec": round(shift, 2), "shift_px": round(shift_px, 2), "reach_arcsec": round(reach, 2),
        "days": round(days, 2),
        "rate_arcsec_per_yr": round(shift / days * 365.25, 2) if days > 0 else None,
        "max_rate_within_epoch_arcsec_per_hr": round(within, 3),
        "pa_deg": None if pa is None else round(pa, 1),
        "direction": None if pa is None else COMPASS[round(pa / 45) % 8],
        "class": cls, "note": note,
    }
