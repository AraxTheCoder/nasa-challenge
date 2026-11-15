"""T86: sources whose spectrum is out of distribution for their field.

Version 3 fits stars, galaxies/quasars and unclassified sources separately. Sparse groups
are unjudged rather than scored against another population.

Input: a field's spectra (T85, `pipeline.fieldspectra.measure_field`). What "ordinary" means is learned from
the field itself, not from a stellar model (Mati's rules, tasks/T75 notes):

1. Per source and epoch, the clean exposures (no flagged pixel in the aperture, T84) are binned into the 22
   bands of T84 and taken in log flux. Each (source, epoch) gets its own level, so only the *shape* counts:
   SPHEREx's ~10 % calibration, a variable star's brightness or a different distance don't matter.
2. A low-rank model of the field's shapes: one mean shape plus up to N_COMPONENTS principal shapes (in
   practice temperature and reddening), fitted to the field's ordinary sources with missing bands allowed
   (alternating weighted least squares) and refitted without the worst-fitting fifth (robust).
3. Residuals in units of their own error *and* the field's scatter in that band (calibrated per band so
   that the ordinary sources' residuals have unit spread): crowding, calibration and PSF effects that hit
   every star are absorbed, not flagged.
4. Only consistent deviations count: |z| >= Z_BAND in at least MIN_RUN neighbouring bands with the same sign
   (or one band at >= Z_SINGLE), and, where two or more epochs cover those bands, the same sign in at least
   two of them.

Output: a ranked list with a plain-words reason per source ("brighter than its neighbours' kind at 3.2–5.0 µm
(+80 %): warm dust or a cool companion?"), the band residuals for a chart, and caveats (blended with a
brighter neighbour, known variable, uncertain source type).

    from pipeline.spectral_outliers import find_outliers
    find_outliers(field_spectra)                  # dict as returned by measure_field
    python -m pipeline.spectral_outliers data/targets/<id>
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

from .anomaly import BINS, CLEAN_MASKED

VERSION = 4                  # 4: rest-frame galaxy comparison
MIN_CELL_SNR = 5.0           # a band's median flux must be this far above its error to count
MIN_BANDS = 8                # bands (over all epochs) a source needs to be judged
N_COMPONENTS = 2             # principal shapes on top of the mean shape
MIN_REF = 12                 # fewer ordinary sources than this: mean shape only
TRIM = 0.2                   # worst-fitting fraction left out of the reference after the first fit
Z_BAND = 3.0
HUBER_Z = 2.0                # robust per-source fit: residuals beyond this many sigma count less
HUBER_ITERS = 4
MIN_PCT = 10.0               # and at least this far off (smaller is within stars' natural spread and our PSF/aperture)
SYS_FLOOR_DEX = 0.013        # >= 3 % systematic per band: bright stars' tiny errors would make 3 % deviations 400 sigma
Z_SINGLE = 6.0
MIN_RUN = 2
BLEND_ARCSEC = 24.0          # a neighbour this close ...
BLEND_DMAG = 1.5             # ... and at most this much fainter adds >= 25 % of the light
VARIABLE_HINTS = ("V*", "Mi*", "RR*", "Ce*", "Or*", "TT*", "Ae*", "Y*O", "pr*", "EB*", "Ro*", "LP*", "s*r", "C*")
GALAXY_HINTS = ("G", "GiG", "GiC", "AGN", "QSO", "Sy1", "Sy2", "BLL", "LIN", "SBG", "EmG", "rG", "H2G", "bCG")
CENTRES = np.sqrt(BINS[:-1] * BINS[1:])
# Colour–colour diagram (T86 view): mean band shape over these ranges, µm. x = short − mid, y = mid − long, in
# magnitudes (positive = redder). Ordinary stars sit on one sequence; dust, cool dwarfs and galaxies leave it.
COLOUR_BANDS = {"short": (1.0, 1.35), "mid": (1.9, 2.5), "long": (3.4, 4.8)}

# What a deviation over a wavelength range may mean (standard values; the same list as web/spectrum.js T63).
# (lo, hi) µm, sign (+1 brighter, -1 fainter, 0 either), words.
FEATURES = [
    (2.90, 3.15, -1, "water ice absorption (3.0 µm): a star behind or inside a cold cloud"),
    (4.20, 4.35, -1, "CO₂ ice absorption (4.27 µm): cold cloud material"),
    (4.60, 4.75, -1, "CO ice or gas (4.67 µm)"),
    (3.20, 3.45, -1, "methane absorption (3.3 µm): a T/Y brown dwarf?"),
    (3.20, 3.45, +1, "PAH emission (3.3 µm): warm dust lit by a hot star or a star-forming galaxy?"),
    (1.30, 1.50, -1, "water absorption (1.4 µm): a cool M/L dwarf?"),
    (1.80, 2.00, -1, "water absorption (1.9 µm): a cool dwarf?"),
    (1.84, 1.91, +1, "Paschen-α emission (1.875 µm): hot gas, a young or active star?"),
    (2.25, 2.45, -1, "CO bandheads (2.3 µm): a cool giant?"),
    (4.00, 4.10, +1, "Brackett-α emission (4.05 µm): hot gas, a young star?"),
    (4.50, 4.80, -1, "CO absorption (4.6 µm): a brown dwarf or cool giant?"),
]


def _clean(fs: dict, i: int):
    n = len(fs["exposures"])
    fl, er, wl, mf = (fs[k][i] for k in ("flux_ujy", "err_ujy", "wavelength_um", "masked_fraction"))
    keep = [k for k in range(n) if fl[k] is not None and er[k] and er[k] > 0 and wl[k] is not None
            and (mf[k] or 0) <= CLEAN_MASKED and math.isfinite(fl[k])]
    return keep, fl, er, wl


def band_cube(fs: dict):
    """Y, S: (sources, epochs, bands) log10 flux and its error (NaN = no usable measurement); epochs list."""
    epochs = sorted({e["epoch"] for e in fs["exposures"]})
    ep_ix = {ep: j for j, ep in enumerate(epochs)}
    ns, ne, nb = len(fs["sources"]), len(epochs), len(BINS) - 1
    Y = np.full((ns, ne, nb), np.nan)
    S = np.full((ns, ne, nb), np.nan)
    N = np.zeros((ns, ne, nb), int)
    for i in range(ns):
        keep, fl, er, wl = _clean(fs, i)
        if not keep:
            continue
        ej = np.array([ep_ix[fs["exposures"][k]["epoch"]] for k in keep])
        bj = np.digitize([wl[k] for k in keep], BINS) - 1
        f = np.array([fl[k] for k in keep], float)
        e = np.array([er[k] for k in keep], float)
        for j in range(ne):
            for b in range(nb):
                sel = (ej == j) & (bj == b)
                m = int(sel.sum())
                if m == 0:
                    continue
                v = f[sel]
                med = float(np.median(v))
                spread = 1.4826 * float(np.median(np.abs(v - med))) if m >= 3 else 0.0
                err = max(float(np.median(e[sel])), spread) * (1.2533 if m >= 3 else 1.0) / math.sqrt(m)
                if med <= 0 or med < MIN_CELL_SNR * err:
                    continue
                Y[i, j, b] = math.log10(med)
                S[i, j, b] = err / (med * math.log(10))
                N[i, j, b] = m
    return Y, S, N, epochs


def _blends(sources: list[dict]) -> list[dict | None]:
    out = []
    for s in sources:
        best = None
        for o in sources:
            if o is s or s.get("mag") is None or o.get("mag") is None:
                continue
            d = _sep(s, o)
            if d < BLEND_ARCSEC and o["mag"] <= s["mag"] + BLEND_DMAG and (best is None or o["mag"] < best[1]["mag"]):
                best = (d, o)
        out.append(None if best is None else {"name": best[1]["name"], "sep_arcsec": round(best[0], 1),
                                              "dmag": round(best[1]["mag"] - s["mag"], 2)})
    return out


def _sep(a, b):
    dra = (a["ra_deg"] - b["ra_deg"] + 180) % 360 - 180
    return 3600 * math.hypot(dra * math.cos(math.radians(a["dec_deg"])), a["dec_deg"] - b["dec_deg"])


def _is(otype, hints):
    o = (otype or "").strip()
    return any(o == h or (h.endswith("*") and o.startswith(h)) for h in hints)


def _fit(Y, S, scatter, ref, K, iters=25):
    """Alternating weighted least squares: Y[i,e,b] ~ C[i,e] + M[b] + A[i] . V[:,b]. Returns C, M, A, V.
    Start: level = each (source, epoch)'s mean, M = the reference's median shape, V = the leading
    singular vectors of the reference's mean residuals (zero coefficients would never move off zero)."""
    import warnings
    ns, ne, nb = Y.shape
    ok = np.isfinite(Y)
    W = np.where(ok, 1.0 / (np.nan_to_num(S) ** 2 + scatter[None, None, :] ** 2), 0.0)
    Y0 = np.nan_to_num(Y)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        C = np.nan_to_num(np.nanmean(np.where(ok, Y, np.nan), axis=2))
        R0 = np.where(ok, Y - C[:, :, None], np.nan)
        M = np.nan_to_num(np.nanmedian(R0[ref].reshape(-1, nb), axis=0))
        res = np.nan_to_num(np.nanmean(R0 - M[None, None, :], axis=1))           # (ns, nb)
    A = np.zeros((ns, K))
    V = np.zeros((K, nb))
    if K:
        _, sv, vt = np.linalg.svd(res[ref], full_matrices=False)
        V = vt[:K].copy()

    def source_step(Wu):
        for i in range(ns):
            cells = np.argwhere(ok[i])
            if len(cells) < ne + K + 1:
                continue
            eps = sorted(set(cells[:, 0]))
            col = {e: k for k, e in enumerate(eps)}
            X = np.zeros((len(cells), len(eps) + K))
            for r, (e, b) in enumerate(cells):
                X[r, col[e]] = 1.0
                X[r, len(eps):] = V[:, b]
            y = np.array([Y[i, e, b] - M[b] for e, b in cells])
            sw = np.sqrt(np.array([Wu[i, e, b] for e, b in cells]))
            sol = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)[0]
            for e, k in col.items():
                C[i, e] = sol[k]
            A[i] = sol[len(eps):]

    def band_step():
        R = (Y0 - C[:, :, None])[ref]                       # (nr, ne, nb)
        Wr = W[ref]
        X = np.concatenate([np.ones((int(ref.sum()), 1)), A[ref]], axis=1)    # (nr, 1+K)
        Xe = np.repeat(X[:, None, :], ne, axis=1).reshape(-1, K + 1)
        for b in range(nb):
            wv = Wr[:, :, b].reshape(-1)
            sel = wv > 0
            if sel.sum() < K + 3:
                continue
            sw = np.sqrt(wv[sel])
            sol = np.linalg.lstsq(Xe[sel] * sw[:, None], R[:, :, b].reshape(-1)[sel] * sw, rcond=None)[0]
            M[b], V[:, b] = sol[0], sol[1:]

    for _ in range(iters):
        source_step(W)
        band_step()
    # Final per-source fit, robust (Huber weights): a deviation over part of the range (an IR excess) stays
    # in the residuals instead of being half-absorbed by tilting the source's temperature shape.
    Wu = W
    for _ in range(HUBER_ITERS):
        source_step(Wu)
        model = C[:, :, None] + M[None, None, :] + np.einsum("ik,kb->ib", A, V)[:, None, :]
        z = np.abs(np.nan_to_num(Y - model)) * np.sqrt(W)
        Wu = W * np.minimum(1.0, HUBER_Z / np.maximum(z, 1e-9))
    source_step(Wu)
    return C, M, A, V


def _calibrate(Rres, S, ref):
    """Per-band extra scatter so the reference's residuals have unit robust spread."""
    nb = Rres.shape[2]
    scatter = np.zeros(nb)
    for b in range(nb):
        r = Rres[ref, :, b].ravel()
        s = S[ref, :, b].ravel()
        m = np.isfinite(r) & np.isfinite(s)
        if m.sum() < 5:
            scatter[b] = 0.05
            continue
        r, s = r[m], s[m]
        lo, hi = 0.0, 1.0
        for _ in range(40):
            mid = (lo + hi) / 2
            spread = 1.4826 * np.median(np.abs(r / np.sqrt(s ** 2 + mid ** 2)))
            lo, hi = (mid, hi) if spread > 1 else (lo, mid)
        scatter[b] = hi
    return np.maximum(scatter, SYS_FLOOR_DEX)


def _runs(z, sig):
    """Maximal runs of neighbouring bands with |z| >= Z_BAND and one sign; z: (nb,) with NaN gaps."""
    out, b, nb = [], 0, len(z)
    while b < nb:
        if not np.isfinite(z[b]) or abs(z[b]) < Z_BAND:
            b += 1
            continue
        sgn, e = np.sign(z[b]), b
        while e + 1 < nb and np.isfinite(z[e + 1]) and abs(z[e + 1]) >= Z_BAND and np.sign(z[e + 1]) == sgn:
            e += 1
        out.append((b, e, int(sgn)))
        b = e + 1
    return [(b, e, s) for b, e, s in out if e - b + 1 >= MIN_RUN or np.nanmax(np.abs(z[b:e + 1])) >= Z_SINGLE]


def _words(lo_um, hi_um, sign, pct):
    hits = [w for (a, b, s, w) in FEATURES if (s == 0 or s == sign) and lo_um <= (a + b) / 2 <= hi_um
            and hi_um - lo_um <= max(0.45, 2.5 * (b - a))]          # a narrow run on the feature, not a broad slope
    if hits:
        return hits[0]
    if sign > 0 and lo_um >= 1.5 and hi_um >= 4.0:
        return "extra light at long wavelengths: warm dust (a disk?) or a cool companion / brown dwarf?"
    if sign < 0 and lo_um >= 1.5 and hi_um >= 4.0:
        return "less light at long wavelengths than its kind: a hotter star, or the field model misfits it"
    if sign > 0 and hi_um <= 1.6:
        return "extra light at short wavelengths: a hot companion, or a blend with a bluer neighbour?"
    if sign < 0 and hi_um <= 1.6:
        return "less light at short wavelengths: reddened by dust in front of it?"
    if hi_um - lo_um > 0.45:
        return "a different overall slope: hotter / cooler or more reddened than anything ordinary here, or a blend"
    return "a bump or dip that ordinary sources in this field don't have"


def _jagged(z) -> bool:
    """Significant residuals that flip sign from band to band: not a spectral feature (those span bands)."""
    pairs = [(a, b) for a, b in zip(z[:-1], z[1:]) if np.isfinite(a) and np.isfinite(b) and abs(a) > 2 and abs(b) > 2]
    return len(pairs) >= 3 and sum(1 for a, b in pairs if np.sign(a) != np.sign(b)) > len(pairs) / 2


def _part(d):
    agree = ", all epochs agree" if d["epochs_seen"] >= 2 and d["epochs_agree"] == d["epochs_seen"] else ""
    return f"{_fmt(d['um_min'])}–{_fmt(d['um_max'])} µm ({d['pct']:+.0f} %, {d['z']:.0f}σ{agree})"


def _reason(devs) -> str:
    d0 = devs[0]
    other = next((d for d in devs[1:] if d["sign"] != d0["sign"] and d["z"] >= d0["z"] / 3), None)
    if other:     # both ends off: the whole slope differs, say it as one thing
        lo, hi = sorted([d0, other], key=lambda d: d["um_min"])
        if lo["sign"] < 0 < hi["sign"]:
            why = ("dust: reddened by a cloud in front, or a warm disk around it?" if hi["um_max"] >= 2.5 else
                   "reddened by dust in front of it, or cooler than its kind?")
            return f"Redder than ordinary sources here: fainter at {_part(lo)}, brighter at {_part(hi)}: {why}"
        return (f"Bluer than ordinary sources here: brighter at {_part(lo)}, fainter at {_part(hi)}: "
                "hotter than its kind, or a hot companion?")
    return f"{'Brighter' if d0['sign'] > 0 else 'Fainter'} than ordinary sources here at {_part(d0)}: {d0['meaning']}"


def _fmt(um):
    return f"{um:.2f}".rstrip("0").rstrip(".")


def _find_group(fs: dict, blends) -> dict:
    sources = fs["sources"]
    Y, S, N, epochs = band_cube(fs)
    ns, ne, nb = Y.shape
    n_bands = np.isfinite(Y).any(1).sum(1)
    judged = n_bands >= MIN_BANDS
    variable = np.array([_is(s.get("otype"), VARIABLE_HINTS) or s.get("source") == "vsx" for s in sources], bool)
    base = judged & np.array([b is None for b in blends], bool) & ~variable
    if base.sum() < 3:
        base = judged & np.array([b is None for b in blends], bool)
    if ns == 0 or base.sum() < 3:
        return {"version": VERSION, "items": [], "scores": {}, "n_sources": ns, "n_judged": int(judged.sum()),
                "summary": f"Can't judge: {int(base.sum())} unblended sources with enough clean bands (need 3).",
                "method": _method(0, 0)}
    K = min(N_COMPONENTS, max(0, (int(base.sum()) - MIN_REF) // 10 + 1)) if base.sum() >= MIN_REF else 0
    scatter = np.full(nb, 0.03)
    ref = base.copy()
    # One principal shape first, then more: learned all at once, a later shape takes on whatever single odd
    # source is in the reference (an IR excess is the only common pattern left after temperature).
    ks = list(range(min(1, K), K + 1)) + [K]
    for rnd, k in enumerate(ks):
        C, M, A, V = _fit(Y, S, scatter, ref, k)
        model = C[:, :, None] + M[None, None, :] + np.einsum("ik,kb->ib", A, V)[:, None, :]
        R = Y - model
        scatter = _calibrate(R, S, ref)
        Z = R / np.sqrt(S ** 2 + scatter[None, None, :] ** 2)
        chi = np.array([np.nanmean(Z[i] ** 2) if np.isfinite(Z[i]).any() else np.nan for i in range(ns)])
        if rnd < len(ks) - 1:     # robust: the worst-fitting fifth of the reference doesn't define "ordinary"
            cut = np.nanquantile(chi[base], 1 - TRIM)
            ref = base & (chi <= cut)
    # combine epochs per band: weighted mean residual and its z
    w = np.where(np.isfinite(Z), 1.0 / (S ** 2 + scatter[None, None, :] ** 2), 0.0)
    Rn = np.nan_to_num(R)
    wsum = w.sum(1)
    Rc = np.where(wsum > 0, (w * Rn).sum(1) / np.where(wsum > 0, wsum, 1), np.nan)
    Zc = Rc * np.sqrt(wsum)
    Zc[wsum == 0] = np.nan

    items, scores = [], {}
    for i in np.flatnonzero(judged):
        devs, score = [], 0.0
        for b0, b1, sgn in _runs(Zc[i], Z):
            zz = Zc[i, b0:b1 + 1]
            per_ep = [np.nansum(Z[i, j, b0:b1 + 1]) for j in range(ne) if np.isfinite(Z[i, j, b0:b1 + 1]).any()]
            agree = sum(1 for v in per_ep if np.sign(v) == sgn and abs(v) >= 2)
            if len(per_ep) >= 2 and agree < 2:
                continue                                  # one epoch only: not consistent
            lo, hi = float(BINS[b0]), float(BINS[b1 + 1])
            pct = float(10 ** np.nanmean(Rc[i, b0:b1 + 1]) - 1) * 100
            if abs(pct) < MIN_PCT:
                continue
            sig = float(np.sqrt(np.nansum(zz ** 2)))
            score += sig
            devs.append({"um_min": round(lo, 3), "um_max": round(hi, 3), "sign": sgn, "pct": round(pct, 1),
                         "z": round(sig, 1), "n_bands": int(b1 - b0 + 1), "epochs_agree": int(agree),
                         "epochs_seen": len(per_ep), "meaning": _words(lo, hi, sgn, pct)})
        s = sources[i]
        caveats = []
        if blends[i]:
            caveats.append(f"blended: {blends[i]['name']} is {blends[i]['sep_arcsec']}″ away"
                           f" ({abs(blends[i]['dmag'])} mag {'brighter' if blends[i]['dmag'] < 0 else 'fainter'})")
        if variable[i]:
            caveats.append("known variable star: its own brightness changes are taken out per epoch, colour changes are not")
        jag = _jagged(Zc[i])
        if jag:
            caveats.append("jagged: neighbouring bands disagree, so the position may be off or it changed within an epoch")
        rank = score * (0.5 if blends[i] else 1.0) * (0.3 if jag else 1.0)
        scores[s["id"]] = round(rank, 1)
        if not devs:
            continue
        devs.sort(key=lambda d: -d["z"])
        reason = _reason(devs)
        items.append({"id": s["id"], "name": s["name"], "source": s.get("source"), "otype": s.get("otype"),
                      "mag": s.get("mag"), "ra_deg": s["ra_deg"], "dec_deg": s["dec_deg"], "index": int(i),
                      "score": round(rank, 1), "chi2": round(float(chi[i]), 2), "deviations": devs,
                      "reason": reason, "caveats": caveats,
                      "bands_um": [round(float(c), 3) for c in CENTRES],
                      "residual_pct": [None if not np.isfinite(v) else round(float(10 ** v - 1) * 100, 1) for v in Rc[i]],
                      "z": [None if not np.isfinite(v) else round(float(v), 1) for v in Zc[i]]})
    items.sort(key=lambda it: -it["score"])
    clean = [it for it in items if not it["caveats"]]
    n_j = int(judged.sum())
    if not items:
        summary = f"Nothing out of the ordinary: {n_j} sources judged against {int(ref.sum())} ordinary ones."
    else:
        summary = (f"{len(items)} of {n_j} sources stand out ({len(clean)} without caveats), "
                   f"judged against {int(ref.sum())} ordinary ones.")
    views = _views(Y, S, C, M, A, V, scatter, sources, judged, ref, {it["id"] for it in items}, scores)
    return {"version": VERSION, "items": items, "scores": scores, "n_sources": ns, "n_judged": n_j,
            "n_reference": int(ref.sum()), "components": K, "epochs": epochs, "summary": summary, **views,
            "scatter_pct": [round(float(10 ** s - 1) * 100, 1) for s in scatter],
            "not_judged": _not_judged(fs, sources, judged, n_bands),
            "method": _method(int(ref.sum()), K)}


def peer_group(source: dict) -> str:
    from .chemistry import GALAXY_OTYPES
    otype = (source.get("otype") or "").strip()
    kind = (source.get("kind") or "").lower()
    if source.get("spectral_population") == "galaxies" or otype in GALAXY_OTYPES or any(k in kind for k in ("galaxy", "quasar")):
        return "galaxies"
    if "*" in otype or otype in {"BD?", "Y*O", "Y*?"} or any(k in kind for k in ("star", "dwarf")) or source.get("source") in {"gaia_dr3", "vsx"}:
        return "stars"
    return "unclassified"


def find_outliers(fs: dict, blends=None) -> dict:
    """Learn and score each catalogue population independently; never borrow another population's model."""
    if blends is None:
        blends = _blends(fs["sources"])
    from .redshift import valid_z
    groups = {}
    items, points, not_judged, scores = [], [], [], {}
    n_judged = n_reference = 0
    for group in dict.fromkeys(peer_group(s) for s in fs["sources"]):
        indices = [i for i, s in enumerate(fs["sources"]) if peer_group(s) == group]
        group_count = len(indices)
        sub = {k: ([v[i] for i in indices] if k in {
            "sources", "flux_ujy", "err_ujy", "wavelength_um", "bandwidth_um", "masked_fraction"} else v)
               for k, v in fs.items()}
        if group == "galaxies":
            known = [j for j, source in enumerate(sub["sources"]) if valid_z(source.get("redshift", source.get("z"))) is not None]
            unknown = [j for j in range(len(indices)) if j not in known]
            not_judged.extend({"id": sub["sources"][j]["id"], "name": sub["sources"][j]["name"],
                               "why": "no reliable redshift for rest-frame peers"} for j in unknown)
            indices = [indices[j] for j in known]
            sub = {k: ([v[j] for j in known] if k in {"sources", "flux_ujy", "err_ujy", "wavelength_um", "bandwidth_um", "masked_fraction"} else v)
                   for k, v in sub.items()}
            sub["wavelength_um"] = [[None if w is None else w / (1 + valid_z(source.get("redshift", source.get("z")))) for w in row]
                                    for source, row in zip(sub["sources"], sub["wavelength_um"])]
        result = _find_group(sub, [blends[i] for i in indices])
        groups[group] = {k: result[k] for k in ("summary", "method", "envelope", "n_reference", "components") if k in result}
        groups[group]["n_sources"] = group_count
        groups[group]["wavelength_frame"] = "rest" if group == "galaxies" else "observed"
        if "points" not in result:
            not_judged.extend({"id": s["id"], "name": s["name"], "why": f"too few clean, unblended {group} peers (need 3)"} for s in sub["sources"])
            continue
        n_judged += result["n_judged"]
        n_reference += result["n_reference"]
        for it in result["items"]:
            it["index"] = indices[it["index"]]
            it["peer_group"] = group
            it["wavelength_frame"] = "rest" if group == "galaxies" else "observed"
            it["reason"] = it["reason"].replace("ordinary sources here", f"ordinary {group} here")
            if group == "galaxies":
                it["reason"] += " (Rest-frame wavelengths.)"
            items.append(it)
        points.extend({**p, "peer_group": group, "wavelength_frame": "rest" if group == "galaxies" else "observed"} for p in result["points"])
        not_judged.extend(result["not_judged"])
        scores.update(result["scores"])
    items.sort(key=lambda it: -it["score"])
    return {"version": VERSION, "items": items, "points": points, "scores": scores,
            "n_sources": len(fs["sources"]), "n_judged": n_judged, "n_reference": n_reference,
            "not_judged": not_judged, "groups": groups,
            "bands_um": [round(float(c), 3) for c in CENTRES],
            "colours": {k: list(v) for k, v in COLOUR_BANDS.items()},
            "summary": (f"{len(items)} of {n_judged} sources stand out within their peer group." if items else
                        f"Nothing out of the ordinary: {n_judged} sources judged within their peer groups." if n_judged else
                        "Not enough clean peers to judge spectra in this field."),
            "method": "Stars, galaxies/quasars and unclassified sources use separate models and scatter. Galaxies use rest-frame wavelengths; unknown shifts are unjudged. "
                      "Groups with fewer than 3 clean, unblended peers are not scored. "
                      "Shape only, with per-source and epoch brightness removed; deviations require ≥10% and ≥3σ "
                      "in neighbouring bands (or one at ≥6σ), with epoch agreement."}


def _band_mean(row, lo, hi):
    sel = (CENTRES >= lo) & (CENTRES <= hi) & np.isfinite(row)
    return float(row[sel].mean()) if sel.any() else math.nan


def _r(v, nd=3):
    return None if v is None or not np.isfinite(v) else round(float(v), nd)


def _views(Y, S, C, M, A, V, scatter, sources, judged, ref, outlier_ids, scores) -> dict:
    """For the charts: each judged source's band shape (level taken out, epochs combined, dex), the shape an
    ordinary source of its kind would have (the model), the field's spread, and two colours per source."""
    w = np.where(np.isfinite(Y), 1.0 / (S ** 2 + scatter[None, None, :] ** 2), 0.0)
    wsum = w.sum(1)
    shape = np.where(wsum > 0, (w * np.nan_to_num(Y - C[:, :, None])).sum(1) / np.where(wsum > 0, wsum, 1), np.nan)
    model = M[None, :] + A @ V if A.size else np.repeat(M[None, :], len(sources), 0)
    with np.errstate(all="ignore"), __import__("warnings").catch_warnings():
        __import__("warnings").simplefilter("ignore", RuntimeWarning)
        env = np.nanpercentile(shape[ref], [16, 50, 84], axis=0) if ref.any() else np.full((3, len(CENTRES)), np.nan)
    points = []
    for i in np.flatnonzero(judged):
        s = shape[i]
        a, b, c = (_band_mean(s, *COLOUR_BANDS[k]) for k in ("short", "mid", "long"))
        points.append({"id": sources[i]["id"], "name": sources[i]["name"], "otype": sources[i].get("otype"),
                       "ra_deg": sources[i]["ra_deg"], "dec_deg": sources[i]["dec_deg"],
                       "x": _r(-2.5 * (a - b), 2), "y": _r(-2.5 * (b - c), 2),   # magnitudes: + = redder
                       "outlier": sources[i]["id"] in outlier_ids, "reference": bool(ref[i]),
                       "score": scores.get(sources[i]["id"], 0.0),
                       "shape": [_r(v) for v in s], "model": [_r(v) for v in model[i]]})
    return {"bands_um": [round(float(c), 3) for c in CENTRES], "points": points,
            "envelope": {k: [_r(v) for v in env[j]] for j, k in enumerate(("p16", "p50", "p84"))},
            "colours": {k: [lo, hi] for k, (lo, hi) in COLOUR_BANDS.items()}}


def _not_judged(fs, sources, judged, n_bands):
    """Why a source has too few clean bands: mostly saturated (flagged core) or too faint."""
    out = []
    for i in np.flatnonzero(~judged):
        mf = [m for m in fs["masked_fraction"][i] if m is not None]
        flagged = sum(1 for m in mf if m > CLEAN_MASKED)
        why = "saturated / flagged in most exposures" if mf and flagged > len(mf) / 2 else "too faint for enough bands"
        out.append({"id": sources[i]["id"], "name": sources[i]["name"], "why": why, "bands": int(n_bands[i])})
    return out


def _method(n_ref, K):
    return (f"Shape only (each source and epoch scaled to its own level), {len(BINS) - 1} bands 0.74–5.05 µm, "
            f"clean exposures only. Ordinary = a mean shape + {K} principal shapes fitted to {n_ref} ordinary "
            f"sources of this field; residuals against their error and the field's scatter per band. A deviation "
            f"needs ≥ {MIN_PCT:g} % and |z| ≥ {Z_BAND:g} (field scatter ≥ 3 %) in ≥ {MIN_RUN} neighbouring bands (or one at ≥ {Z_SINGLE:g}) and the same sign "
            f"in ≥ 2 epochs where more than one covers it.")


def main(argv=None) -> int:
    from . import fieldspectra
    ap = argparse.ArgumentParser(prog="python -m pipeline.spectral_outliers", description=__doc__.split("\n\n")[0])
    ap.add_argument("target_dir", type=Path)
    ap.add_argument("-n", type=int, default=10)
    args = ap.parse_args(argv)
    t = json.loads((args.target_dir / "target.json").read_text(encoding="utf-8"))
    out = find_outliers(fieldspectra.measure_field(t))
    print(out["summary"])
    for name, group in out["groups"].items():
        print(f"{name}: {group['summary']}")
    for it in out["items"][:args.n]:
        print(f"  {it['score']:6.1f}  {it['name']:<28} {it.get('otype') or '':<6} mag {it.get('mag')}  {it['reason']}"
              + (f"  [{'; '.join(it['caveats'])}]" if it["caveats"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
