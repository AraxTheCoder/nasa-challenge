"""Candidate chemistry-profile matches from shared aperture spectra, without reading images.

These are feature-pattern matches, not fitted physical templates or object classifications.
Both continuum sides and repeated-epoch agreement are required. Missing features are
reported, never interpreted as non-detections. No network redshift lookups are made.
"""
from __future__ import annotations

import math

import numpy as np

from .chemistry import FEATURES, PRESETS, _other_features
from .spectral_outliers import _blends, _clean, peer_group

VERSION = 2
# Signs follow the map presets: absorption negative, emission positive.
SIGNS = {"h2o_14": -1, "h2o_19": -1, "co_23": -1, "h2o_ice": -1,
         "ch4": -1, "ch3oh_ice": -1, "co2_ice": -1, "co_ice": -1}


def _median(values, errors):
    med = float(np.median(values))
    spread = 1.4826 * float(np.median(np.abs(values - med))) if len(values) >= 3 else 0
    err = max(float(np.median(errors)), spread) * 1.2533 / math.sqrt(len(values))
    return med, err


def feature_evidence(fs, i, feature, z=0):
    """Local on-minus-interpolated-continuum contrast, independently in each epoch."""
    _, lam, half, _, _ = FEATURES[feature]
    lam, half = lam * (1 + z), half * (1 + z)
    keep, fl, er, wl = _clean(fs, i)
    rows = []
    for ep in sorted({fs["exposures"][k]["epoch"] for k in keep}):
        ks = [k for k in keep if fs["exposures"][k]["epoch"] == ep]
        w, f, e = (np.array([v[k] for k in ks], float) for v in (wl, fl, er))
        bw = np.array([fs["bandwidth_um"][i][k] or w[j] / 40 for j, k in enumerate(ks)])
        width = np.maximum(half, bw / 2)
        d = w - lam
        on = np.abs(d) <= width
        cont = (np.abs(d) >= width + bw / 2) & (np.abs(d) <= width + 3 * bw)
        for other, hw in _other_features(lam, z):
            cont &= np.abs(w - other) > np.maximum(hw, bw / 2) + bw / 2
        blue, red = cont & (d < 0), cont & (d > 0)
        if not all(sel.any() for sel in (on, blue, red)):
            continue
        a, ae = _median(f[on], e[on])
        b, be = _median(f[blue], e[blue])
        r, re = _median(f[red], e[red])
        t = float((np.median(w[on]) - np.median(w[blue])) / (np.median(w[red]) - np.median(w[blue])))
        c = b * (1 - t) + r * t
        ce = math.hypot(be * (1 - t), re * t)
        if c <= 0 or c < 5 * ce:
            continue
        sigma = math.sqrt(ae ** 2 + ce ** 2 + (0.03 * c) ** 2)
        rows.append({"epoch": ep, "pct": 100 * (a - c) / c, "sigma": 100 * sigma / c})
    if not rows:
        return {"feature": feature, "name": FEATURES[feature][0], "status": "insufficient_coverage"}
    weights = np.array([1 / r["sigma"] ** 2 for r in rows])
    pct = float(np.average([r["pct"] for r in rows], weights=weights))
    significance = pct * math.sqrt(float(weights.sum()))
    sign = SIGNS.get(feature, 1)
    agree = sum(r["pct"] * sign >= 10 and r["pct"] * sign / r["sigma"] >= 2 for r in rows)
    detected = pct * sign >= 10 and significance * sign >= 3 and agree >= min(2, len(rows))
    return {"feature": feature, "name": FEATURES[feature][0], "status": "detected" if detected else "not_detected",
            "pct": round(pct, 1), "significance": round(significance, 2),
            "epochs_seen": len(rows), "epochs_agree": agree}


def find_matches(fs, blends=None):
    from .redshift import valid_z
    matches, skipped = [], []
    if blends is None:
        blends = _blends(fs["sources"])
    for i, source in enumerate(fs["sources"]):
        evidence = {}
        for profile in PRESETS:
            if profile.get("needs_z") and peer_group(source) == "stars":
                continue
            z = valid_z(source.get("redshift", source.get("z"))) if profile.get("needs_z") else 0
            if profile.get("needs_z") and z is None:
                skipped.append({"id": source["id"], "profile": profile["id"], "why": "reliable catalogue or spectral redshift required"})
                continue
            # Extragalactic sources must not be assigned a rest-frame stellar profile.
            if peer_group(source) == "galaxies" and profile["group"] == "object" and not profile.get("needs_z"):
                continue
            z = float(z)
            features = []
            for fid in profile["features"]:
                key = (fid, z)
                if key not in evidence:
                    evidence[key] = feature_evidence(fs, i, fid, z)
                features.append(evidence[key])
            detected = [f for f in features if f["status"] == "detected"]
            # Require a distinctive molecule as well as a second feature for cool atmospheres.
            required = {"brown_dwarfs": "ch4", "cool_giants": "co_23"}.get(profile["id"])
            if len(detected) < 2 or (required and required not in {f["feature"] for f in detected}):
                continue
            matches.append({"id": source["id"], "name": source["name"], "ra_deg": source["ra_deg"],
                            "dec_deg": source["dec_deg"], "profile": profile["id"], "profile_name": profile["name"],
                            "z": z, "redshift_origin": source.get("redshift_origin", "label") if profile.get("needs_z") else "rest", "features": features, "score": round(sum(abs(f["significance"]) for f in detected), 1),
                            "caveats": ([f"Blended with {blends[i]['name']}; the features may belong to either source."] if blends[i] else []) +
                                       [profile["caveats"], "Feature-pattern candidate; not an object classification."]})
    matches.sort(key=lambda m: -m["score"])
    return {"version": VERSION, "matches": matches, "skipped": skipped,
            "method": "Shared source spectra; at least two features with ≥10% contrast and ≥3σ, continuum on both sides, "
                      "and agreement in two epochs when available. Brown-dwarf candidates require methane; cool giants require CO. "
                      "Single-epoch evidence and blends need follow-up. Redshift profiles use catalogue values or unambiguous experimental spectral estimates."}
