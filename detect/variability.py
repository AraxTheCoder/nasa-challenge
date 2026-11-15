"""T61: sources of a field that change brightness between exposures (variable stars, flares, fading).

Input: a field's spectra (T85, `pipeline.fieldspectra.measure_field`): every catalogue source measured in every
SPHEREx exposure, with the wavelength it was seen at. T86 (`pipeline.spectral_outliers`) looks at the *shape* of
the spectra and removes each source's level per epoch; this looks at the level.

SPHEREx sees a source at a different wavelength in every exposure, and stars are brighter at some wavelengths
than others, so only exposures at the same wavelength are compared:

1. Pairs. Per source, every two clean exposures (no flagged pixel in the aperture, S/N >= MIN_SNR) of the same
   detector, at least MIN_DT_DAYS apart, whose wavelengths differ by at most half a bandwidth (CONTRACTS Pair,
   here per source position: the wavelength changes across a field). Change = -2.5 log10(flux later / earlier).
2. Calibration. Each pair of exposures is offset by the median change of all the field's sources seen in it
   (exposure-to-exposure calibration and zodiacal light residuals hit every star the same way).
3. Amplitude = 90th percentile of |change| over the source's pairs. The field's median amplitude is what
   noise, aperture and pointing do to a constant star; a source is variable when its amplitude is at least
   MIN_AMP_MAG and FIELD_X times the field's median, it has MIN_PAIRS pairs, and its own errors are small
   enough (amplitude >= MIN_Z times the typical pair error).
4. Not judged (listed under `blended`): a neighbour within BLEND_ARCSEC with at least BLEND_FRAC of its flux
   (the aperture catches a changing part of it) and extended sources (galaxies, nebulae).

On two 86' fields in Ophiuchus (2026-11-15) 34 sources were flagged, 24 of them catalogued variables (Miras,
eclipsing binaries, RR Lyrae, long-period variables) against 28 % of all sources: the rest are candidates.

    from detect.variability import find_variables
    find_variables(field_spectra)                       # dict as returned by measure_field
    python -m detect.variability data/targets/<id>
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import warnings
from pathlib import Path

import numpy as np

VERSION = 1
MIN_SNR = 5.0           # each exposure's flux / error
MIN_DT_DAYS = 0.5       # pairs closer in time say nothing about change (and share the same pointing)
MIN_PAIRS = 6
CAL_SIG = 0.05          # pairs with an error below this (mag) set the field's offset of an exposure pair ...
CAL_MIN = 5             # ... if there are at least this many
MIN_AMP_MAG = 0.2
FIELD_X = 3.0
MIN_Z = 5.0
BLEND_ARCSEC = 24.0
BLEND_FRAC = 0.25
VARIABLE_HINTS = ("V*", "Mi*", "RR*", "Ce*", "Or*", "TT*", "Ae*", "Y*O", "pr*", "EB*", "Ro*", "LP*", "s*r", "C*",
                  "BY*", "RS*", "Pu*", "dS*", "El*", "Pe*", "Em*", "SB*", "CV*", "No*", "Ir*", "Er*", "a2*", "gD*",
                  "WR*", "Be*", "bC*", "sv*", "cC*", "RI*", "Fl*", "LM*")
EXTENDED = {"G", "GiG", "GiC", "GiP", "AGN", "QSO", "Sy1", "Sy2", "BLL", "LIN", "SBG", "EmG", "rG", "H2G", "bCG",
            "LSB", "ClG", "GrG", "sh", "HII", "RNe", "ISM", "Cld", "MoC", "PN", "SNR", "GNe", "DNe", "bub", "DNe"}
WORDS = {"Mi*": "a Mira variable", "LP*": "a long-period variable", "EB*": "an eclipsing binary",
         "RR*": "an RR Lyrae star", "TT*": "a T Tauri star", "Or*": "a young (Orion) variable",
         "Ce*": "a Cepheid", "BY*": "a spotted (BY Dra) star", "RS*": "an RS CVn binary", "Pu*": "a pulsating star",
         "dS*": "a delta Scuti star", "El*": "an ellipsoidal variable", "Ro*": "a rotating variable",
         "Pe*": "a peculiar star", "Em*": "an emission-line star", "SB*": "a spectroscopic binary",
         "C*": "a carbon star", "Y*O": "a young star"}


def _is_variable(otype: str | None) -> bool:
    o = (otype or "").strip()
    return any(o == h or (h.endswith("*") and o.startswith(h)) for h in VARIABLE_HINTS)


def _arr(fs: dict, key: str) -> np.ndarray:
    return np.array([[np.nan if v is None else v for v in row] for row in fs[key]], float).reshape(len(fs["sources"]), -1)


def _pairs(F, E, L, B, ok, mjd, det):
    """[(source, k_early, k_late, change mag, error mag)] for every wavelength-matched pair."""
    out = []
    for i in range(F.shape[0]):
        ks = np.nonzero(ok[i])[0]
        for d in np.unique(det[ks]):
            kd = ks[det[ks] == d]
            if len(kd) < 2:
                continue
            a, b = np.triu_indices(len(kd), 1)
            k1, k2 = kd[a], kd[b]
            swap = mjd[k1] > mjd[k2]
            k1, k2 = np.where(swap, k2, k1), np.where(swap, k1, k2)
            sel = (np.abs(mjd[k2] - mjd[k1]) >= MIN_DT_DAYS) & \
                  (np.abs(L[i, k1] - L[i, k2]) <= 0.5 * np.minimum(B[i, k1], B[i, k2]))
            k1, k2 = k1[sel], k2[sel]
            dm = -2.5 * np.log10(F[i, k2] / F[i, k1])
            sig = 1.0857 * np.hypot(E[i, k1] / F[i, k1], E[i, k2] / F[i, k2])
            out.extend(zip([i] * len(k1), k1.tolist(), k2.tolist(), dm.tolist(), sig.tolist()))
    return out


def _sep_arcsec(ra, dec, i):
    dra = (ra - ra[i] + 180) % 360 - 180
    return 3600 * np.hypot(dra * np.cos(np.radians(dec[i])), dec - dec[i])


def find_variables(fs: dict) -> dict:
    sources, exps = fs["sources"], fs["exposures"]
    n = len(sources)
    if not n or not exps:
        return {"version": VERSION, "variables": [], "blended": [], "n_judged": 0, "method": _method(0.0)}
    F, E, L, B, M = (_arr(fs, k) for k in ("flux_ujy", "err_ujy", "wavelength_um", "bandwidth_um", "masked_fraction"))
    mjd = np.array([e["mjd"] for e in exps], float)
    det = np.array([e.get("detector") or 0 for e in exps])
    epoch = {k: e.get("epoch") for k, e in enumerate(exps)}
    with np.errstate(invalid="ignore", divide="ignore"):
        ok = np.isfinite(F) & np.isfinite(E) & (E > 0) & np.isfinite(L) & np.isfinite(B) & \
             (np.nan_to_num(M, nan=1.0) <= 0.0) & (F >= MIN_SNR * E)
    pairs = _pairs(F, E, L, B, ok, mjd, det)

    # 2. per exposure pair: the field's median change
    cal: dict[tuple[int, int], list[float]] = {}
    for i, k1, k2, dm, sig in pairs:
        if sig < CAL_SIG:
            cal.setdefault((k1, k2), []).append(dm)
    offset = {p: float(np.median(v)) for p, v in cal.items() if len(v) >= CAL_MIN}
    per: dict[int, list[tuple[float, float, int, int]]] = {}
    for i, k1, k2, dm, sig in pairs:
        o = offset.get((k1, k2))
        if o is not None:
            per.setdefault(i, []).append((dm - o, sig, k1, k2))

    # 3. amplitude per source, against the field
    stats = {}
    for i, v in per.items():
        if len(v) < MIN_PAIRS:
            continue
        d = np.array([x[0] for x in v])
        stats[i] = {"amp": float(np.percentile(np.abs(d), 90)), "sig": float(np.median([x[1] for x in v])),
                    "n": len(v), "d": d, "v": v}
    field_amp = float(np.median([s["amp"] for s in stats.values()])) if stats else 0.0
    ra = np.array([s["ra_deg"] for s in sources], float)
    dec = np.array([s["dec_deg"] for s in sources], float)
    with warnings.catch_warnings():                       # sources without one clean exposure: NaN, fine
        warnings.simplefilter("ignore", RuntimeWarning)
        level = np.nanmedian(np.where(ok, F, np.nan), axis=1)

    variables, blended = [], []
    for i, s in stats.items():
        if not (s["amp"] >= max(MIN_AMP_MAG, FIELD_X * field_amp) and s["amp"] >= MIN_Z * s["sig"]):
            continue
        src = sources[i]
        row = {"id": src.get("id"), "name": src.get("name"), "otype": src.get("otype"),
               "ra_deg": src["ra_deg"], "dec_deg": src["dec_deg"], "amplitude_mag": round(s["amp"], 2),
               "n_pairs": s["n"], "catalogued_variable": _is_variable(src.get("otype")),
               "epochs": _epoch_changes(s["v"], epoch)}
        d = _sep_arcsec(ra, dec, i)
        d[i] = np.inf
        near = np.nonzero((d < BLEND_ARCSEC) & (np.nan_to_num(level, nan=0.0) >= BLEND_FRAC * level[i]))[0]
        if (src.get("otype") or "").strip() in EXTENDED:
            blended.append({**row, "why": "extended source: the aperture catches a different part of it each time"})
        elif len(near):
            j = int(near[np.argmin(d[near])])
            blended.append({**row, "why": f"{sources[j].get('name')} is {d[j]:.0f}\" away and at least "
                                          f"{BLEND_FRAC:.0%} as bright: the change may be the neighbour's"})
        else:
            row["reason"] = _reason(row, src)
            variables.append(row)
    variables.sort(key=lambda r: (r["catalogued_variable"], -r["amplitude_mag"]))   # new ones first
    blended.sort(key=lambda r: -r["amplitude_mag"])
    return {"version": VERSION, "variables": variables, "blended": blended, "n_judged": len(stats),
            "field_amplitude_mag": round(field_amp, 3), "method": _method(field_amp)}


def _epoch_changes(v, epoch) -> list[dict]:
    """Median change between survey passes (later minus earlier; negative = brighter later), where >= 3 pairs."""
    by: dict[tuple, list[float]] = {}
    for dm, _sig, k1, k2 in v:
        e1, e2 = epoch.get(k1), epoch.get(k2)
        if e1 is not None and e2 is not None and e1 != e2:
            by.setdefault((e1, e2), []).append(dm)
    return [{"from_epoch": a, "to_epoch": b, "change_mag": round(float(np.median(d)), 2), "n_pairs": len(d)}
            for (a, b), d in sorted(by.items()) if len(d) >= 3]


def _reason(row: dict, src: dict) -> str:
    amp = row["amplitude_mag"]
    times = 10 ** (0.4 * amp)
    txt = (f"changes brightness by up to {amp:.2f} mag (×{times:.1f}) between exposures at the same wavelength "
           f"({row['n_pairs']} pairs)")
    trend = max(row["epochs"], key=lambda e: abs(e["change_mag"]), default=None)
    if trend and abs(trend["change_mag"]) >= MIN_AMP_MAG:
        txt += (f"; {'fainter' if trend['change_mag'] > 0 else 'brighter'} by {abs(trend['change_mag']):.2f} mag in "
                f"survey pass {trend['to_epoch']} than in pass {trend['from_epoch']}")
    o = (src.get("otype") or "").strip()
    if row["catalogued_variable"]:
        txt += f"; catalogued as {WORDS.get(o, 'a variable star')} ({o})"
    else:
        txt += f"; not catalogued as variable ({o or 'no type'}): a new variable? Check its light curve"
    return txt


def _method(field_amp: float) -> str:
    return (f"v{VERSION}: same detector, wavelengths within half a bandwidth, >= {MIN_DT_DAYS} d apart, S/N >= "
            f"{MIN_SNR:g}, no flagged pixel; offset per exposure pair = field median; variable = 90th percentile "
            f"|change| >= max({MIN_AMP_MAG} mag, {FIELD_X:g} x field's {field_amp:.3f} mag) and >= {MIN_Z:g} x pair "
            f"error, >= {MIN_PAIRS} pairs; neighbours within {BLEND_ARCSEC:g}\" with >= {BLEND_FRAC:.0%} of the flux "
            "and extended sources are listed as `blended`, not judged")


def main(argv=None) -> int:
    from pipeline import fieldspectra

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("target", type=Path, help="data/targets/<id> (its field spectra must be measured: T85)")
    a = ap.parse_args(argv)
    t = json.loads((a.target / "target.json").read_text(encoding="utf-8"))
    p = fieldspectra.cache_path(t["id"])
    if not p.is_file():
        print(f"no field spectra at {p}: run python -m pipeline.fieldspectra {a.target}", file=sys.stderr)
        return 1
    out = find_variables(json.loads(p.read_text(encoding="utf-8")))
    print(out["method"])
    for r in out["variables"]:
        print(f"  {r['name']}: {r['reason']}")
    print(f"{len(out['blended'])} more not judged (blended / extended); {out['n_judged']} sources judged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
