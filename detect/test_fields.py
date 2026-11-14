"""T10: SPHEREx multi-epoch coverage of the official test fields (docs/CHALLENGE.md, Objectives).

Resolves each target in SIMBAD (position, proper motion, parallax), moves it to each epoch,
lists the SPHEREx images that cover it (pipeline.query) and reports per epoch: dates, images,
detectors, wavelength range, and how far the target moves between epochs.

    python -m detect.test_fields [--out data/t10/test_fields.json]
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from pipeline.labels import SIMBAD_TAP, _tap
from pipeline.query import find_exposures

PIXEL_ARCSEC = 6.15
J2000_MJD = 51544.5

# Names as SIMBAD knows them. WISE 0855 also has the coordinates given in the challenge text.
TARGETS = [
    {"key": "barnard", "label": "Barnard's Star", "simbad": "Barnard's star", "why": "fastest proper motion (10.4\"/yr)"},
    {"key": "eps-indi-b", "label": "Epsilon Indi B", "simbad": "eps Ind B", "why": "brown dwarf pair orbiting a star"},
    {"key": "wise-0855", "label": "WISE 0855", "simbad": "WISE J085510.83-071442.5", "why": "fast-moving coldest brown dwarf"},
    {"key": "rw-aur", "label": "RW Aurigae", "simbad": "RW Aur", "why": "variable star"},
    {"key": "r-dra", "label": "R Draconis", "simbad": "R Dra", "why": "Mira variable"},
]

ADQL = """SELECT TOP 1 b.main_id, b.ra, b.dec, b.pmra, b.pmdec, b.plx_value, b.otype
FROM basic AS b JOIN ident AS i ON i.oidref = b.oid WHERE i.id = '{name}'"""


def simbad(name: str) -> tuple[dict, dict]:
    adql = " ".join(ADQL.format(name=name.replace("'", "''")).split())
    last = None
    for url in SIMBAD_TAP:
        try:
            rows = _tap(url, adql)
        except Exception as e:  # noqa: BLE001 - try the next mirror
            last = e
            continue
        if not rows:
            raise LookupError(f"SIMBAD has no object {name!r}")
        prov = {"service": f"SIMBAD TAP {url}", "query": adql,
                "retrieved_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        return rows[0], prov
    raise RuntimeError(f"all SIMBAD mirrors failed: {last}")


def propagate(ra, dec, pmra, pmdec, mjd) -> tuple[float, float]:
    """Linear proper motion from J2000 (SIMBAD epoch) to mjd. pm in mas/yr, pmra includes cos(dec)."""
    yrs = (mjd - J2000_MJD) / 365.25
    dec2 = dec + (pmdec or 0) * yrs / 3.6e6
    ra2 = ra + (pmra or 0) * yrs / 3.6e6 / math.cos(math.radians(dec))
    return ra2 % 360, dec2


def survey(t: dict) -> dict:
    obj, prov_s = simbad(t["simbad"])
    pmra, pmdec = obj.get("pmra") or 0.0, obj.get("pmdec") or 0.0
    pm_total = math.hypot(pmra, pmdec) / 1000  # arcsec/yr
    # Query at the position for mid-2025.9 (middle of the data so far); the search uses the image
    # footprint (~3.5 deg), so a few arcmin offset doesn't change which images we get.
    ra_q, dec_q = propagate(obj["ra"], obj["dec"], pmra, pmdec, 61000.0)
    exposures, prov_q = find_exposures(ra_q, dec_q)

    epochs = []
    for ep in sorted({e.epoch for e in exposures}):
        sel = [e for e in exposures if e.epoch == ep]
        mid = sum(e.mjd_mid for e in sel) / len(sel)
        epochs.append({
            "epoch": ep, "start": sel[0].time_utc[:10], "end": sel[-1].time_utc[:10],
            "mjd_mean": round(mid, 2), "n_images": len(sel),
            "per_detector": {d: sum(1 for e in sel if e.detector == d) for d in range(1, 7)},
            "wave_um": [round(min(e.wave_min_um for e in sel), 3), round(max(e.wave_max_um for e in sel), 3)],
            "position": dict(zip(("ra_deg", "dec_deg"), (round(v, 6) for v in
                             propagate(obj["ra"], obj["dec"], pmra, pmdec, mid)))),
        })
    span_days = epochs[-1]["mjd_mean"] - epochs[0]["mjd_mean"] if len(epochs) > 1 else 0.0
    shift = pm_total * span_days / 365.25
    return {
        **t, "simbad_main_id": obj["main_id"], "otype": obj.get("otype"),
        "ra_deg_j2000": obj["ra"], "dec_deg_j2000": obj["dec"],
        "pmra_mas_yr": pmra, "pmdec_mas_yr": pmdec, "parallax_mas": obj.get("plx_value"),
        "pm_arcsec_yr": round(pm_total, 3),
        "n_images": len(exposures), "n_epochs": len(epochs), "epochs": epochs,
        "span_days": round(span_days, 1),
        "pm_shift_over_span_arcsec": round(shift, 2),
        "pm_shift_over_span_px": round(shift / PIXEL_ARCSEC, 2),
        "provenance": [prov_s, prov_q],
    }


def table(results: list[dict]) -> str:
    out = ["| Target | SIMBAD | PM \"/yr | Epochs | Images | Span d | PM shift \" (px) | Images per detector D1..D6 |",
           "|---|---|---|---|---|---|---|---|"]
    for r in results:
        if "error" in r:
            out.append(f"| {r['label']} | error: {r['error']} | | | | | | |")
            continue
        per = [sum(ep["per_detector"][d] for ep in r["epochs"]) for d in range(1, 7)]
        out.append(f"| {r['label']} | {r['simbad_main_id']} ({r['otype']}) | {r['pm_arcsec_yr']} | "
                   f"{r['n_epochs']} | {r['n_images']} | {r['span_days']} | "
                   f"{r['pm_shift_over_span_arcsec']} ({r['pm_shift_over_span_px']}) | {'/'.join(map(str, per))} |")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=Path("data/t10/test_fields.json"))
    args = ap.parse_args(argv)
    results = []
    for t in TARGETS:
        try:
            r = survey(t)
        except Exception as e:  # noqa: BLE001 - report and carry on with the other targets
            r = {**t, "error": f"{type(e).__name__}: {e}"}
        results.append(r)
        print(f"{t['label']}: " + (r.get("error") or f"{r['n_epochs']} epochs, {r['n_images']} images"),
              flush=True)
    print(table(results))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=1, default=str), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
