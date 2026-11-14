"""T01: list all SPHEREx exposures covering a sky position, via the IRSA TAP service.

One row per detector image (a SPHEREx exposure has 6 detectors, D1-D6, each its own image and
its own wavelength range). The direct FITS URL comes from joining ObsCore with the CAOM
plane/artifact tables, so no per-image datalink call is needed.

    python -m pipeline.query --ra 150.1 --dec 2.2 [--out data/queries/cosmos.json]
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

TAP_URL = "https://irsa.ipac.caltech.edu/TAP"
IRSA_ROOT = "https://irsa.ipac.caltech.edu/"
# dr1: Apr 2025 - May 2026, qr3: May 2026 onwards. *_deep: extra visits near the ecliptic poles.
DEFAULT_COLLECTIONS = ("spherex_dr1", "spherex_dr1_deep", "spherex_qr3", "spherex_qr3_deep")
EPOCH_GAP_DAYS = 30.0  # visits to one spot cluster within weeks; passes are ~6 months apart

# Step 1: spatial search. IRSA only uses its spatial index on a plain, unjoined s_region,
# so the FITS paths come from a second query (step 2).
QUERY_TEMPLATE = """
SELECT obs_id, obs_collection, energy_bandpassname, t_min, t_max, t_exptime,
       em_min, em_max, obs_publisher_did
FROM spherex.obscore
WHERE obs_collection IN ({collections})
  AND dataproduct_type = 'image'
  AND CONTAINS(POINT('ICRS', {ra}, {dec}), s_region) = 1
"""
# Step 2: direct FITS path per image, from the CAOM tables.
URI_QUERY_TEMPLATE = """
SELECT p.obs_publisher_did, a.uri
FROM spherex.plane AS p JOIN spherex.artifact AS a ON a.planeid = p.planeid
WHERE a.producttype = 'science' AND p.obs_publisher_did IN ({dids})
"""
URI_BATCH = 500


@dataclass
class Exposure:
    obs_id: str          # e.g. "2025W17_4B_0001_1"
    collection: str      # e.g. "spherex_dr1"
    detector: int        # 1-6 (1-3 SWIR, 4-6 MWIR)
    mjd_start: float
    mjd_mid: float
    time_utc: str        # ISO 8601 of mjd_mid
    exptime_s: float
    wave_min_um: float   # wavelength range of the whole detector; varies across the image (LVF)
    wave_max_um: float
    epoch: int           # 1-based cluster of visits, see assign_epochs
    fits_url: str        # full 2040x2040 image; append ?center=ra,dec&size=..deg for a cutout
    publisher_did: str


def build_query(ra_deg: float, dec_deg: float, collections=DEFAULT_COLLECTIONS) -> str:
    cols = ", ".join(f"'{c}'" for c in collections)
    return " ".join(QUERY_TEMPLATE.format(collections=cols, ra=float(ra_deg), dec=float(dec_deg)).split())


def assign_epochs(mjds, gap_days: float = EPOCH_GAP_DAYS) -> np.ndarray:
    """Number visits 1, 2, ... in time order, starting a new epoch after a gap > gap_days."""
    mjds = np.asarray(mjds, dtype=float)
    order = np.argsort(mjds)
    epochs = np.empty(len(mjds), dtype=int)
    current, last = 0, None
    for i in order:
        if last is None or mjds[i] - last > gap_days:
            current += 1
        epochs[i] = current
        last = mjds[i]
    return epochs


def find_exposures(ra_deg: float, dec_deg: float, collections=DEFAULT_COLLECTIONS):
    """Return (exposures sorted by time, provenance dict)."""
    import pyvo
    from astropy.time import Time

    tap = pyvo.dal.TAPService(TAP_URL)
    query = build_query(ra_deg, dec_deg, collections)
    retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    table = tap.run_sync(query, maxrec=100000).to_table()

    dids = [str(d) for d in table["obs_publisher_did"]]
    uris = {}
    for i in range(0, len(dids), URI_BATCH):
        inlist = ", ".join(f"'{d}'" for d in dids[i:i + URI_BATCH])
        for r in tap.run_sync(" ".join(URI_QUERY_TEMPLATE.format(dids=inlist).split()), maxrec=100000):
            uris[str(r["obs_publisher_did"])] = str(r["uri"])
    missing = [d for d in dids if d not in uris]
    if missing:
        raise RuntimeError(f"no FITS path for {len(missing)} images, e.g. {missing[0]}")

    mid = (np.array(table["t_min"], float) + np.array(table["t_max"], float)) / 2
    epochs = assign_epochs(mid)
    times = Time(mid, format="mjd", scale="utc").isot if len(mid) else []
    exposures = [
        Exposure(
            obs_id=str(r["obs_id"]),
            collection=str(r["obs_collection"]),
            detector=int(str(r["energy_bandpassname"]).rsplit("D", 1)[-1]),
            mjd_start=float(r["t_min"]),
            mjd_mid=float(mid[i]),
            time_utc=str(times[i])[:19] + "Z",
            exptime_s=float(r["t_exptime"]),
            wave_min_um=round(float(r["em_min"]) * 1e6, 4),
            wave_max_um=round(float(r["em_max"]) * 1e6, 4),
            epoch=int(epochs[i]),
            fits_url=IRSA_ROOT + uris[str(r["obs_publisher_did"])].lstrip("/"),
            publisher_did=str(r["obs_publisher_did"]),
        )
        for i, r in enumerate(table)
    ]
    exposures.sort(key=lambda e: (e.mjd_mid, e.detector))
    provenance = {"service": "IRSA TAP " + TAP_URL,
                  "query": query + " ; then FITS paths via: " + " ".join(URI_QUERY_TEMPLATE.split()),
                  "retrieved_utc": retrieved}
    return exposures, provenance


def summarize(exposures) -> str:
    lines = [f"{len(exposures)} detector images"]
    for ep in sorted({e.epoch for e in exposures}):
        sel = [e for e in exposures if e.epoch == ep]
        dets = sorted({e.detector for e in sel})
        lines.append(f"  epoch {ep}: {sel[0].time_utc[:10]} .. {sel[-1].time_utc[:10]}, "
                     f"{len(sel)} images, detectors {dets}, "
                     f"{min(e.wave_min_um for e in sel):.2f}-{max(e.wave_max_um for e in sel):.2f} um")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ra", type=float, required=True)
    ap.add_argument("--dec", type=float, required=True)
    ap.add_argument("--out", type=Path, help="write exposures + provenance as JSON")
    args = ap.parse_args(argv)
    exposures, prov = find_exposures(args.ra, args.dec)
    print(summarize(exposures))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({"ra_deg": args.ra, "dec_deg": args.dec, "provenance": prov,
                                        "exposures": [asdict(e) for e in exposures]}, indent=1))
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
