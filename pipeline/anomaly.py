"""T84: what changes in a spectrum in a non-continuous way, from all exposures at one position (T66).

Three kinds, each with a plain-words reason and how significant it is:

- **spike / dip**: one exposure far above (below) its epoch's smooth spectrum at that wavelength
  (the median of its wavelength neighbours of the same epoch), beyond its own error and the local
  scatter. Typical causes: something passed through the aperture (an asteroid: checked against the
  known ones at that moment with the local MPC catalogue, T51), a cosmic ray or artefact, a flare.
  A second detector looking at the same spot at the same moment that is also high makes a real
  source more likely than a detector artefact.
- **level**: the same wavelengths are brighter or fainter in another epoch (the whole spectrum moved).
- **shape**: the ratio between two epochs varies with wavelength beyond the noise: the spectrum changed
  shape, e.g. molecular bands deepening in a cool variable star, dust appearing around a young star,
  gas switching on in a comet. Reported with the wavelength where it differs most.

    from pipeline.anomaly import find_anomalies
    find_anomalies(spectrum)          # spectrum = pipeline.photometry.measure_all(...) answer

Pure numpy apart from the known-object check; the same call runs per position on the HPC (T75).
"""
from __future__ import annotations

import math

import numpy as np

SPIKE_SIGMA = 5.0            # one exposure vs. its neighbours
NEIGHBOUR_DEX = 0.04         # wavelength window for "neighbours": +-10% (SPHEREx channels: ~2.5%)
MIN_NEIGHBOURS = 4
WIDE_DEX = 0.15              # too few in the window: the nearest MIN_NEIGHBOURS + 1 within +-40% instead
LEVEL_SIGMA = 5.0
LEVEL_MIN = 0.10             # at least 10% brighter/fainter
SHAPE_CHI2 = 4.0             # reduced chi^2 of the epoch ratio around a constant
SHAPE_MIN = 0.15             # and the most deviating band differs by at least 15% from the rest
BINS = np.geomspace(0.74, 5.05, 23)   # common wavelength bins for epoch comparisons
MIN_BIN_SNR = 5.0
SAME_MOMENT_DAYS = 2 / 1440  # the other detector of the same exposure (they are taken together)
SAME_BURST_DAYS = 30 / 1440  # a burst (~4 exposures over ~6 min) is not its own reference: an asteroid passing
                             # lifts all of them at the same wavelengths (244 Sita: 8 high, only 1 found before)
APERTURE_ARCSEC = 18.0
MIN_CLEAN = 10               # fewer unflagged exposures than this: say so instead of "nothing unusual"
# Exposures with more of the aperture flagged than this are left out of every check: flagged pixels are filled
# in, and for bright stars they are the saturated core, so the flux is too low (RW Aur at 1.55 um: 14-19 %
# flagged read 35-39 mJy next to 122 mJy at 7 %, which looked like a "shape change", T84 findings).
# Even one flagged pixel matters: SPHEREx's 6" pixels put about half a star's light into its core pixel, so
# filling a flagged core loses ~60% (27 of the first 36 "dips" had a flagged pixel in the aperture).
CLEAN_MASKED = 0.0


def _good(frames):
    return [f for f in frames if not f.get("masked") and f.get("flux_ujy") is not None
            and f.get("err_ujy") and np.isfinite(f["flux_ujy"]) and f["err_ujy"] > 0
            and (f.get("masked_fraction") or 0) <= CLEAN_MASKED]


def spikes(frames: list[dict]) -> list[dict]:
    """Exposures far off their epoch's smooth spectrum."""
    out = []
    good = _good(frames)
    for ep in sorted({f["epoch"] for f in good}):
        pts = [f for f in good if f["epoch"] == ep]
        lw = np.log10([f["wavelength_um"] for f in pts])
        fl = np.array([f["flux_ujy"] for f in pts], float)
        er = np.array([f["err_ujy"] for f in pts], float)
        t = np.array([f["mjd"] for f in pts], float)
        for i, f in enumerate(pts):
            other = np.abs(t - t[i]) > SAME_BURST_DAYS
            dl = np.abs(lw - lw[i])
            nb = (dl <= NEIGHBOUR_DEX) & other
            wide = nb.sum() < MIN_NEIGHBOURS
            if wide:                                        # sparse: nearest ones within WIDE_DEX
                cand = np.flatnonzero(other & (dl <= WIDE_DEX))
                nb = np.zeros(len(pts), bool)
                nb[cand[np.argsort(dl[cand])][:MIN_NEIGHBOURS + 1]] = True
            if nb.sum() < MIN_NEIGHBOURS:
                continue
            m = float(np.median(fl[nb]))
            scatter = 1.4826 * float(np.median(np.abs(fl[nb] - m)))
            z = (fl[i] - m) / math.sqrt(er[i] ** 2 + scatter ** 2)
            if wide and z < 0:
                continue          # over +-40% the spectrum's slope alone makes points look low: spikes only
            if abs(z) >= SPIKE_SIGMA and abs(fl[i] - m) >= 3 * er[i]:
                out.append({"type": "spike" if z > 0 else "dip", "epoch": ep, "frame_id": f["frame_id"],
                            "mjd": f["mjd"], "time_utc": f.get("time_utc"), "detector": f.get("detector"),
                            "wavelength_um": f["wavelength_um"], "sigma": round(float(abs(z)), 1),
                            "flux_ujy": f["flux_ujy"], "expected_ujy": round(m, 3),
                            "change_pct": round(100 * (fl[i] - m) / abs(m), 1) if abs(m) > 5 * max(scatter, er[i]) else None})
    # the other detector of the same exposure sees the same spot at the same moment
    for s in out:
        twins = [g for g in good if g["frame_id"] != s["frame_id"] and abs(g["mjd"] - s["mjd"]) <= SAME_MOMENT_DAYS]
        partners = [o for o in out if o is not s and abs(o["mjd"] - s["mjd"]) <= SAME_MOMENT_DAYS]
        s["same_moment"] = {"exposures": len(twins), "also_off": len(partners)}
    return out


def _binned(pts):
    """Median flux and its error per common wavelength bin: {bin: (flux, err, n)}."""
    w = np.array([f["wavelength_um"] for f in pts]); fl = np.array([f["flux_ujy"] for f in pts], float)
    er = np.array([f["err_ujy"] for f in pts], float)
    idx = np.digitize(w, BINS) - 1
    out = {}
    for k in np.unique(idx):
        sel = idx == k
        if sel.sum() < 2 or not 0 <= k < len(BINS) - 1:
            continue
        v = fl[sel]
        med = float(np.median(v))
        spread = 1.4826 * float(np.median(np.abs(v - med)))
        e = max(float(np.median(er[sel])), spread) * 1.2533 / math.sqrt(sel.sum())   # error of a median
        out[int(k)] = (med, e, int(sel.sum()))
    return out


def epoch_changes(frames: list[dict]) -> list[dict]:
    """Level and shape changes between consecutive epochs, at the same wavelengths."""
    good = [f for f in _good(frames)]
    eps = sorted({f["epoch"] for f in good})
    by = {ep: _binned([f for f in good if f["epoch"] == ep]) for ep in eps}
    out = []
    for a, b in zip(eps, eps[1:]):
        ks = [k for k in by[a] if k in by[b] and by[a][k][0] > MIN_BIN_SNR * by[a][k][1]
              and by[b][k][0] > MIN_BIN_SNR * by[b][k][1]]
        if len(ks) < 3:
            continue
        r = np.array([by[b][k][0] / by[a][k][0] for k in ks])
        re = r * np.hypot([by[a][k][1] / by[a][k][0] for k in ks], [by[b][k][1] / by[b][k][0] for k in ks])
        wgt = 1 / re ** 2
        mean = float(np.sum(wgt * r) / np.sum(wgt))
        mean_err = float(1 / math.sqrt(np.sum(wgt)))
        wl = [float(math.sqrt(BINS[k] * BINS[k + 1])) for k in ks]
        if abs(mean - 1) >= LEVEL_MIN and abs(mean - 1) / mean_err >= LEVEL_SIGMA:
            out.append({"type": "level", "epochs": [a, b], "ratio": round(mean, 3),
                        "change_pct": round(100 * (mean - 1), 1), "sigma": round(abs(mean - 1) / mean_err, 1),
                        "bands": len(ks)})
        chi2 = float(np.sum(((r - mean) / re) ** 2) / (len(ks) - 1))
        j = int(np.argmax(np.abs(r - mean) / re))
        dev = (r[j] - mean) / mean
        if chi2 >= SHAPE_CHI2 and abs(dev) >= SHAPE_MIN:
            out.append({"type": "shape", "epochs": [a, b], "wavelength_um": round(wl[j], 2),
                        "change_pct": round(100 * dev, 1), "ratio_here": round(float(r[j]), 3), "ratio_rest": round(mean, 3), "reduced_chi2": round(chi2, 1),
                        "sigma": round(float(abs(r[j] - mean) / re[j]), 1), "bands": len(ks)})
    return out


def group_bursts(sp: list[dict]) -> list[dict]:
    """Spikes/dips of the same kind in one burst (< SAME_BURST_DAYS apart) are one event."""
    out = []
    for s in sorted(sp, key=lambda s: (s["type"], s["mjd"])):
        g = out[-1] if out else None
        if g and g["type"] == s["type"] and s["mjd"] - g["mjd_last"] <= SAME_BURST_DAYS:
            g["frames"].append(s["frame_id"]); g["mjd_last"] = s["mjd"]
            g["wavelengths_um"].append(s["wavelength_um"]); g["detectors"].add(s["detector"])
            g["sigma"] = max(g["sigma"], s["sigma"])
            g["known"] = g.get("known") or s.get("known")
            g["same_moment"]["also_off"] += 1
            continue
        out.append({**s, "frames": [s["frame_id"]], "mjd_last": s["mjd"], "wavelengths_um": [s["wavelength_um"]],
                    "detectors": {s["detector"]}, "same_moment": dict(s.get("same_moment") or {})})
    for g in out:
        g["detectors"] = sorted(d for d in g["detectors"] if d is not None)
        g["n_exposures"] = len(g["frames"])
    return out


def known_passers(ra: float, dec: float, spike_list: list[dict], vmag_lim: float = 21.0) -> None:
    """Fill spike['known'] with asteroids/comets within the aperture at that moment (local MPC catalogue)."""
    if not spike_list:
        return
    try:
        from detect import mpcorb
        if not mpcorb.available():
            return
        scale = 6.15
        npx = int(2 * 60 / scale)                       # +-1' around the position
        target = {"center": {"ra_deg": ra, "dec_deg": dec},
                  "image": {"width": npx, "height": npx, "pixel_scale_arcsec": scale},
                  "frames": [{"id": s["frame_id"], "mjd": s["mjd"], "epoch": s["epoch"]} for s in spike_list]}
        found = mpcorb.find(target, vmag_lim)
    except Exception as e:  # noqa: BLE001 - the anomalies stand without it
        print(f"anomaly: known-object check failed: {e}")
        return
    for s in spike_list:
        near = []
        for o in found:
            for p in o["positions"]:
                if p["frame_id"] == s["frame_id"]:
                    d = math.degrees(math.acos(min(1.0, math.sin(math.radians(dec)) * math.sin(math.radians(p["dec_deg"]))
                        + math.cos(math.radians(dec)) * math.cos(math.radians(p["dec_deg"]))
                        * math.cos(math.radians(p["ra_deg"] - ra))))) * 3600
                    if d <= 2 * APERTURE_ARCSEC:
                        near.append({"name": o["name"], "distance_arcsec": round(d, 1)})
        s["known"] = sorted(near, key=lambda n: n["distance_arcsec"])


def _ujy(v: float) -> str:
    return f"{v / 1000:.2f} mJy" if abs(v) >= 1000 else f"{v:.0f} µJy"


def explain(a: dict) -> str:
    t = a["type"]
    if t in ("spike", "dip"):
        word = "brighter" if t == "spike" else "fainter"
        how = (f"{abs(a['change_pct']):.0f}% {word} than its neighbours" if a.get("change_pct") is not None else
               f"{word} than its neighbours ({_ujy(a['flux_ujy'])} instead of about {_ujy(a['expected_ujy'])})")
        n = a.get("n_exposures", 1)
        if n > 1:
            lo, hi = min(a["wavelengths_um"]), max(a["wavelengths_um"])
            txt = (f"{n} exposures of one burst (epoch {a['epoch']}, {a.get('time_utc') or ''}"[:-1 if not a.get('time_utc') else None]
                   + f"; {lo:.2f}–{hi:.2f} µm, detector{'s' if len(a['detectors']) > 1 else ''} "
                   + ", ".join(f"D{d}" for d in a["detectors"]) + f") are {word} than their neighbours"
                   + (f", e.g. {abs(a['change_pct']):.0f}%" if a.get("change_pct") is not None else
                      f", e.g. {_ujy(a['flux_ujy'])} instead of about {_ujy(a['expected_ujy'])}") + f" (up to {a['sigma']:.0f}σ).")
        else:
            txt = f"One exposure ({a['frame_id']}, epoch {a['epoch']}, {a['wavelength_um']:.2f} µm) is {how} ({a['sigma']:.0f}σ)."
        if a.get("known"):
            k = a["known"][0]
            return txt + f" Known object {k['name']} was {k['distance_arcsec']:.0f}″ away at that moment: it passed through."
        sm = a.get("same_moment") or {}
        if t == "spike" and (sm.get("also_off") or len(a.get("detectors") or []) > 1):
            return txt + " The other detector saw the same spot higher at the same moment: likely something real " \
                         "passing or flaring there (no known asteroid or comet nearby)."
        if t == "spike" and sm.get("exposures"):
            return txt + " The other detector at the same moment saw nothing unusual: more likely a cosmic ray " \
                         "or an artefact in this one image."
        return txt + (" Possible causes: something passing, a flare, a cosmic ray or an artefact."
                      if t == "spike" else " Possible causes: a bad pixel or flagged edge, or an eclipse.")
    if t == "level":
        a_, b_ = a["epochs"]
        return (f"Epoch {b_} is {abs(a['change_pct']):.0f}% {'brighter' if a['change_pct'] > 0 else 'fainter'} than "
                f"epoch {a_} at the same wavelengths ({a['bands']} bands, {a['sigma']:.0f}σ): the source varies.")
    a_, b_ = a["epochs"]
    return (f"The spectrum's shape changed from epoch {a_} to {b_}: around {a['wavelength_um']:.2f} µm the brightness "
            f"changed ×{a['ratio_here']:.2f}, elsewhere ×{a['ratio_rest']:.2f} ({a['sigma']:.0f}σ). Bands that come and "
            f"go point to molecules, dust or gas changing (cool variable stars, young stars, comets).")


def find_anomalies(spectrum: dict, check_known: bool = True) -> dict:
    """{'items': [...], 'summary': str} for a measure_all() answer; items most significant first."""
    frames = spectrum.get("frames", [])
    sp = spikes(frames)
    if check_known:
        known_passers(spectrum["ra_deg"], spectrum["dec_deg"], sp)
    items = sorted(group_bursts(sp) + epoch_changes(frames), key=lambda a: -a["sigma"])
    for a in items:
        a["reason"] = explain(a)
    kinds = {k: sum(1 for a in items if a["type"] == k) for k in ("spike", "dip", "level", "shape")}
    clean = _good(frames)
    if len(clean) < MIN_CLEAN:
        summary = (f"Can't judge: only {len(clean)} of {len(frames)} exposures are (nearly) free of flagged pixels "
                   f"in the aperture: the source is saturated (too bright for SPHEREx) or sits on bad pixels.")
        items = []
    elif not items:
        summary = "Nothing unusual: every exposure fits its epoch's spectrum, and the epochs agree."
    else:
        parts = [f"{n} {k}{'s' if n > 1 else ''}" for k, n in kinds.items() if n]
        summary = "Unusual: " + ", ".join(parts) + "."
    return {"items": items, "summary": summary, "counts": kinds,
            "method": f"spikes: {SPIKE_SIGMA:g}σ vs. ±{NEIGHBOUR_DEX:g} dex neighbours of the same epoch; "
                      f"epochs: {len(BINS) - 1} common bands, level ≥{100 * LEVEL_MIN:.0f}% at ≥{LEVEL_SIGMA:g}σ, "
                      f"shape reduced χ² ≥{SHAPE_CHI2:g} and ≥{100 * SHAPE_MIN:.0f}% in one band"}
