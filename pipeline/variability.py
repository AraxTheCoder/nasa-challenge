"""T75: sources that got brighter or fainter between epochs, compared at the same wavelengths.

T86 (`pipeline.spectral_outliers`) judges the *shape* of a spectrum and leaves overall brightness changes out on
purpose. This is the other half: per source and per pair of epochs, the change in each wavelength band
(T86's band cube: 22 bands of ~9 %, saturated / flagged measurements already left out), so a star is always
compared with itself at the same wavelength (SPHEREx's filters put every exposure at a different wavelength).

Rules (the same two as T86, Mati's T75 notes):
1. Normal comes from the field. Per band and epoch pair, the median change of the field's ordinary sources
   (not known variables, galaxies or blends) is taken out: that removes calibration and aperture drifts
   between epochs. What is left is compared with the field's own robust scatter (>= 3 %) and the errors.
Within an epoch (pulsating stars, eclipsing binaries vary in hours, so epoch averages wash it out): the robust
scatter of a source's measurements in one band and epoch, against the ordinary sources' scatter in that band.

2. Only consistent changes count: the same sign in several bands (>= MIN_BANDS at >= Z_BAND sigma, at least
   half of the bands the source has in both epochs), and at least MIN_PCT on average.
"""
from __future__ import annotations

import math

import numpy as np

from .spectral_outliers import BINS, CENTRES, GALAXY_HINTS, VARIABLE_HINTS, _blends, _clean, _is, band_cube

Z_BAND = 3.0
MIN_BANDS = 3              # bands with a significant change of the same sign
MIN_FRACTION = 0.5         # ... out of the bands the source has in both epochs
MIN_SHARED = 4             # bands needed in both epochs to judge a pair at all
MIN_PCT = 10.0             # average change at least this large
SYS_FLOOR_DEX = 0.013      # >= 3 % per band, as T86
MIN_REF = 8                # ordinary sources needed to calibrate an epoch pair
# Within an epoch (pulsating stars, eclipsing binaries: hours): the scatter of a source's measurements in one
# wavelength band of one epoch, against the same scatter of the field's ordinary sources in that band.
ACTIVE_HINTS = ("AGN", "QSO", "Sy1", "Sy2", "BLL", "LIN")   # galaxies that can vary within days
MIN_CELL = 4               # measurements in an (epoch, band) cell to measure its scatter
WITHIN_RATIO = 3.0         # scatter at least this many times the ordinary sources' ...
WITHIN_MIN_PCT = 8.0       # ... and at least this large (± %, robust)


def _epoch_dates(fs: dict, epochs: list[int]) -> dict[int, str]:
    out = {}
    for ep in epochs:
        ts = sorted(e.get("time_utc") or "" for e in fs["exposures"] if e["epoch"] == ep)
        ts = [t for t in ts if t]
        out[ep] = (ts[0][:7] if ts else f"epoch {ep}")      # "2025-09"
    return out


def _within(fs: dict, ordinary: np.ndarray):
    """Per source and band: the median over epochs of the robust fractional scatter (%) within an epoch."""
    ns, nb = len(fs["sources"]), len(BINS) - 1
    Q = np.full((ns, nb), np.nan)
    M = np.zeros((ns, nb), int)
    for i in range(ns):
        keep, fl, er, wl = _clean(fs, i)
        cells: dict[tuple[int, int], list[tuple[float, float]]] = {}
        for k in keep:
            b = int(np.digitize(wl[k], BINS)) - 1
            if 0 <= b < nb:
                cells.setdefault((fs["exposures"][k]["epoch"], b), []).append((fl[k], er[k]))
        per_band: dict[int, list[float]] = {}
        for (_, b), v in cells.items():
            if len(v) < MIN_CELL:
                continue
            f = np.array([x[0] for x in v])
            med = float(np.median(f))
            if med <= 0 or med < 5 * float(np.median([x[1] for x in v])):
                continue
            per_band.setdefault(b, []).append(100 * 1.4826 * float(np.median(np.abs(f - med))) / med)
        for b, q in per_band.items():
            Q[i, b] = float(np.median(q))
            M[i, b] = len(q)
    ref = np.nanmedian(np.where(ordinary[:, None], Q, np.nan), axis=0) if ordinary.any() else np.full(nb, np.nan)
    return Q, ref


def find_variables(fs: dict) -> dict:
    """{"items": [...] best first, "pairs": n epoch pairs, "n_judged": n, "method": str}."""
    Y, S, N, epochs = band_cube(fs)
    sources = fs["sources"]
    ns, ne, nb = Y.shape
    blends = _blends(sources)
    ordinary = np.array([not _is(s.get("otype"), VARIABLE_HINTS) and not _is(s.get("otype"), GALAXY_HINTS)
                         and blends[i] is None for i, s in enumerate(sources)], bool)
    dates = _epoch_dates(fs, epochs)
    best: dict[int, dict] = {}
    judged = set()
    pairs = 0
    for j1 in range(ne):
        for j2 in range(j1 + 1, ne):
            D = Y[:, j2, :] - Y[:, j1, :]
            E = np.sqrt(S[:, j1, :] ** 2 + S[:, j2, :] ** 2)
            ref = ordinary[:, None] & np.isfinite(D)
            if (ref.sum(axis=0) >= MIN_REF).sum() < MIN_SHARED:
                continue
            pairs += 1
            off = np.full(nb, np.nan)
            sc = np.full(nb, np.nan)
            for b in range(nb):
                d = D[ref[:, b], b]
                if len(d) < MIN_REF:
                    continue
                off[b] = np.median(d)
                sc[b] = max(1.4826 * np.median(np.abs(d - off[b])), SYS_FLOOR_DEX)
            R = D - off[None, :]
            Z = R / np.sqrt(E ** 2 + sc[None, :] ** 2)
            for i in range(ns):
                ok = np.isfinite(Z[i])
                n = int(ok.sum())
                if n < MIN_SHARED:
                    continue
                judged.add(i)
                for sign in (+1, -1):
                    hit = ok & (sign * Z[i] >= Z_BAND)
                    k = int(hit.sum())
                    if k < MIN_BANDS or k < MIN_FRACTION * n:
                        continue
                    pct = (10 ** float(np.median(R[i][hit])) - 1) * 100
                    if abs(pct) < MIN_PCT:
                        continue
                    score = float(np.sum(np.abs(Z[i][hit]))) / math.sqrt(n)
                    if i in best and best[i]["score"] >= score:
                        continue
                    um = CENTRES[hit]
                    best[i] = {"index": i, "kind": "between", "score": round(score, 2), "pct": round(pct, 1), "sign": sign,
                               "epochs": [epochs[j1], epochs[j2]], "dates": [dates[epochs[j1]], dates[epochs[j2]]],
                               "bands": k, "bands_shared": n, "um_min": round(float(um.min()), 2),
                               "um_max": round(float(um.max()), 2),
                               "field_scatter_pct": round((10 ** float(np.nanmedian(sc)) - 1) * 100, 1)}
    Q, ref = _within(fs, ordinary)
    for i in range(ns):
        o = sources[i].get("otype")
        if (_is(o, GALAXY_HINTS) and not _is(o, ACTIVE_HINTS)) or blends[i]:
            continue          # extended / a neighbour in the 18" aperture: its share of the light changes from
                              # exposure to exposure and fakes scatter (Barnard field, 2026-11-14: 9 of 11 were blends)
        ok = np.isfinite(Q[i]) & np.isfinite(ref)
        n = int(ok.sum())
        if n < MIN_SHARED:
            continue
        hit = ok & (Q[i] >= WITHIN_RATIO * ref) & (Q[i] >= WITHIN_MIN_PCT)
        k = int(hit.sum())
        if k < MIN_BANDS or k < MIN_FRACTION * n:
            continue
        score = float(np.sum(Q[i][hit] / ref[hit])) / math.sqrt(n)
        if i in best and best[i]["score"] >= score:
            continue
        um = CENTRES[hit]
        best[i] = {"index": i, "kind": "within", "score": round(score, 2), "pct": round(float(np.median(Q[i][hit])), 1),
                   "sign": 0, "epochs": epochs, "dates": [dates[e] for e in epochs], "bands": k, "bands_shared": n,
                   "um_min": round(float(um.min()), 2), "um_max": round(float(um.max()), 2),
                   "field_scatter_pct": round(float(np.median(ref[hit])), 1)}
    items = []
    for i, v in sorted(best.items(), key=lambda kv: -kv[1]["score"]):
        s = sources[i]
        caveats = []
        if blends[i]:
            caveats.append(f"blended: {blends[i]['name']} is {blends[i]['sep_arcsec']}″ away")
        if _is(s.get("otype"), GALAXY_HINTS):
            caveats.append("a galaxy (an active nucleus can vary)")
        known_var = _is(s.get("otype"), VARIABLE_HINTS)
        if v.get("kind") == "within":
            reason = (f"Varies within days: its measurements at the same wavelength, hours to days apart in one epoch, "
                      f"scatter by ±{v['pct']:.0f} % in {v['bands']} of {v['bands_shared']} wavelength bands "
                      f"({v['um_min']:.2f}–{v['um_max']:.2f} µm), where ordinary stars here scatter by "
                      f"±{v['field_scatter_pct']:.0f} %: a pulsating star, an eclipsing binary or flares?")
        else:
            word = "Brighter" if v["sign"] > 0 else "Fainter"
            reason = (f"{word} by {abs(v['pct']):.0f} % in {v['dates'][1]} than in {v['dates'][0]} (epochs "
                      f"{v['epochs'][0]} → {v['epochs'][1]}), in {v['bands']} of {v['bands_shared']} wavelength bands "
                      f"({v['um_min']:.2f}–{v['um_max']:.2f} µm), each compared at the same wavelength; ordinary stars "
                      f"here changed by about {v['field_scatter_pct']:.0f} %.")
        if known_var:
            reason += " Catalogued as variable: a check that the search sees known variables."
        items.append({"id": s.get("id"), "name": s.get("name"), "otype": s.get("otype"), "mag": s.get("mag"),
                      "ra_deg": s.get("ra_deg"), "dec_deg": s.get("dec_deg"), "known_variable": known_var,
                      "reason": reason, "caveats": caveats, **{k: v[k] for k in v if k != "index"}})
    return {"items": items, "pairs": pairs, "n_judged": len(judged), "method": (
        f"per source and epoch pair: change per wavelength band minus the field's ordinary sources' median change; "
        f"significant at >= {Z_BAND} sigma against errors + the field's scatter (>= 3 %); >= {MIN_BANDS} bands and "
        f">= {int(MIN_FRACTION * 100)} % of shared bands with the same sign, >= {MIN_PCT:.0f} % on average; within an epoch: "
        f"robust scatter per band >= {WITHIN_RATIO:.0f}x the ordinary sources' and >= {WITHIN_MIN_PCT:.0f} % in as many bands")}
