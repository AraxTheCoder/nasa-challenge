"""Stopgap until pipeline.build (T02-T04) exists: bake one REAL target folder into the Live API cache.

    python pipeline/reference/bake_target.py --ra 269.4463 --dec 4.7682 --size 15 \
        --name "Barnard's Star" --detectors 1 6 [--cache data/targets]

Uses the reference scripts in this folder (fetch_cutouts.py, align_render.py), then
pipeline.labels.add_labels. The id is the Live API's own (server.coords.target_id), so the viewer's
request for that field is a cache hit. Output follows docs/CONTRACTS.md (target.json v0.2 + labels).
Provenance says it was baked with reference code, so nobody mistakes it for pipeline.build output.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
HERE = Path(__file__).resolve().parent
PX_ARCSEC = 6.15


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> None:
    from pipeline.labels import add_labels
    from pipeline.query import find_exposures
    from server.coords import target_id

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ra", type=float, required=True)
    ap.add_argument("--dec", type=float, required=True)
    ap.add_argument("--size", type=int, default=15, help="field side in arcmin")
    ap.add_argument("--name", required=True)
    ap.add_argument("--detectors", type=int, nargs="+", default=[1])
    ap.add_argument("--cache", type=Path, default=REPO / "data" / "targets")
    a = ap.parse_args()

    tid, ra, dec = target_id(a.ra, a.dec, a.size)
    work = REPO / "data" / "bake" / tid
    work.mkdir(parents=True, exist_ok=True)
    n_px = round(a.size * 60 / PX_ARCSEC)
    cut_deg = a.size / 60 * 1.45  # bigger than the field so rotated frames still fill its corners

    print(f"[{tid}] querying IRSA ...", flush=True)
    exposures, prov_q = find_exposures(ra, dec)
    if not exposures:
        sys.exit(f"no SPHEREx images cover RA {ra} Dec {dec}")
    qjson = work / "query.json"
    from dataclasses import asdict
    qjson.write_text(json.dumps({"ra_deg": ra, "dec_deg": dec, "provenance": prov_q,
                                 "exposures": [asdict(e) for e in exposures]}))

    frames, pairs, images = [], [], {}
    for det in a.detectors:
        n = sum(e.detector == det for e in exposures)
        print(f"[{tid}] detector {det}: {n} images, fetching cutouts ...", flush=True)
        raw = REPO / "data" / "raw" / "bake" / tid / f"d{det}"
        subprocess.run([sys.executable, str(HERE / "fetch_cutouts.py"), str(qjson), str(det), f"{cut_deg:.4f}", str(raw)],
                       check=True)
        out = work / f"d{det}"
        print(f"[{tid}] detector {det}: aligning + rendering ...", flush=True)
        subprocess.run([sys.executable, str(HERE / "align_render.py"), str(qjson), str(raw), str(out), str(n_px)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        summ = json.loads((out / "summary.json").read_text())
        meta = {e.obs_id: e for e in exposures if e.detector == det}
        for f in summ["frames"]:
            fid = f"d{det}-{f['id']}"
            e = meta[f["obs_id"]]
            frames.append({"id": fid, "time_utc": f["time_utc"], "mjd": f["mjd"], "epoch": f["epoch"],
                           "detector": det, "wavelength_um": f["wavelength_um"], "bandwidth_um": f["bandwidth_um"],
                           "image": f"frames/{fid}.png", "obs_id": f["obs_id"],
                           "source_url": f"{e.fits_url}?center={ra},{dec}&size={cut_deg:.4f}deg"})
            images[fid] = out / "frames" / f"{f['id']}.png"
        for p in summ["pairs"]:
            pairs.append({"a": f"d{det}-{p['a']}", "b": f"d{det}-{p['b']}", "detector": det,
                          "dwave_um": p["dwave_um"], "dt_days": p["dt_days"]})

    frames.sort(key=lambda f: (f["mjd"], f["detector"]))
    target = {
        "schema_version": "0.2", "id": tid, "name": a.name, "synthetic": False,
        "center": {"ra_deg": ra, "dec_deg": dec}, "size_arcmin": a.size,
        "image": {"width": n_px, "height": n_px, "pixel_scale_arcsec": PX_ARCSEC},
        "provenance": [prov_q, {
            "service": "IRSA IBE cutouts + pipeline/reference (stopgap bake, not pipeline.build)",
            "query": f"bake_target.py --ra {ra} --dec {dec} --size {a.size} --detectors {' '.join(map(str, a.detectors))}; "
                     f"cutouts {cut_deg:.4f} deg, zodi subtracted, flags masked, reprojected TAN 6.15\"/px",
            "retrieved_utc": now()}],
        "frames": frames, "known_objects": [], "detections": [], "pairs": pairs,
    }
    add_labels(target)

    tmp = a.cache / (tid + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    (tmp / "frames").mkdir(parents=True)
    for fid, src in images.items():
        shutil.copy(src, tmp / "frames" / f"{fid}.png")
    (tmp / "target.json").write_text(json.dumps(target, indent=1))
    try:
        import jsonschema
        jsonschema.validate(target, json.loads((REPO / "docs" / "target.schema.json").read_text()))
        print(f"[{tid}] target.json valid against docs/target.schema.json")
    except ImportError:
        print(f"[{tid}] jsonschema not installed, skipped validation")
    dest = a.cache / tid
    shutil.rmtree(dest, ignore_errors=True)
    tmp.rename(dest)
    named = [l["name"] for l in target["labels"] if l["named"]]
    print(f"[{tid}] done: {len(frames)} frames, {len(pairs)} pairs, {len(target['labels'])} labels "
          f"(named: {', '.join(named) or 'none'}) -> {dest}", flush=True)


if __name__ == "__main__":
    main()
