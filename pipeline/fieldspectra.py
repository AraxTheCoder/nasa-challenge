"""T85: spectra for every catalogue source of a field at once.

T66/T83 measure one sky point on every exposure that covers it (~6 s, all of it reading ~300 small cutouts).
A field's sources share those exposures, so here each exposure is read once, as one cutout the size of the
field, and every source is measured in it: the cost is the exposures, not the number of stars.

Sources are the field's catalogue labels (stars, variable stars, brown dwarfs; T19/T72), each moved along
its own track (its label positions, by MJD) so fast stars stay in the aperture. Solar-system objects are left
out: they cross the field within hours and get their own spectra from a click.

    python -m pipeline.fieldspectra data/targets/<id>

Result, cached as data/field_spectra/<target id>.json:
    {"target_id", "center", "size_deg", "sources": [{id, name, source, otype, mag, ra_deg, dec_deg, ...}],
     "exposures": [{frame_id, mjd, epoch, detector, time_utc}],
     "flux_ujy" / "err_ujy" / "wavelength_um" / "masked_fraction": [source][exposure] (null = not measured),
     "missing": [frame ids], "seconds", "note"}
`source_spectrum(fs, i)` turns one source back into the T66 spectrum shape (photometry.measure_all).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from . import build, photometry

ROOT = Path("data/field_spectra")
MARGIN_DEG = 0.03          # the annulus (8 px = 49") around sources at the field's edge
SKIP_KINDS = {"asteroid", "comet", "planet", "moon", "minor planet", "solar system"}
DUP_ARCSEC = 3.0           # labels this close are one source (SIMBAD + Gaia twin)
# SIMBAD types whose positions come from X-ray / radio / far-IR catalogues (ROSAT 1RXS: 10-20" errors): an
# aperture there sits beside the star, and the PSF growing with wavelength fakes spectral structure (T86).
LOOSE_OTYPES = {"X", "gam", "UV", "Rad", "mR", "cm", "mm", "smm", "HI", "rB", "IR", "FIR", "MIR", "gB", "XB", "ULX"}
VERSION = 2                # 2: no X-ray / radio positions
_lock = threading.Lock()


def cache_path(target_id: str) -> Path:
    return ROOT / f"{target_id}.json"


def sources_of(target: dict) -> list[dict]:
    """Catalogue sources of a field with a linear track (RA/Dec at MJD0 + rate per day)."""
    mjd = {f["id"]: f["mjd"] for f in target.get("frames", [])}
    out = []
    for lab in target.get("labels", []):
        if (lab.get("kind") or "").lower() in SKIP_KINDS or lab.get("synthetic") or \
                (lab.get("otype") or "").strip() in LOOSE_OTYPES:
            continue
        pos = [p for p in lab.get("positions", []) if p.get("frame_id") in mjd]
        if not pos:
            continue
        t = np.array([mjd[p["frame_id"]] for p in pos])
        ra = np.unwrap(np.radians([p["ra_deg"] for p in pos]))
        dec = np.array([p["dec_deg"] for p in pos])
        t0 = float(t.mean())
        if np.ptp(t) > 1:
            dra, ra0 = np.polyfit(t - t0, ra, 1)
            ddec, dec0 = np.polyfit(t - t0, dec, 1)
        else:
            dra, ra0, ddec, dec0 = 0.0, float(ra.mean()), 0.0, float(dec.mean())
        out.append({"id": lab.get("id"), "name": lab.get("name"), "source": lab.get("source"),
                    "kind": lab.get("kind"), "otype": lab.get("otype"), "mag": lab.get("mag"),
                    "mag_band": lab.get("mag_band"), "named": bool(lab.get("named")),
                    **({"redshift": lab.get("redshift", lab.get("z"))} if "redshift" in lab or "z" in lab else {}),
                    "ra_deg": round(float(np.degrees(ra0)) % 360, 7), "dec_deg": round(float(dec0), 7),
                    "mjd0": round(t0, 5), "dra_deg_day": float(np.degrees(dra)), "ddec_deg_day": float(ddec)})
    return _dedupe(out)


def _dedupe(src: list[dict]) -> list[dict]:
    """One source per spot: keep the named / brighter label, the other's name goes to aliases."""
    rank = sorted(range(len(src)), key=lambda i: (not src[i]["named"], src[i]["mag"] if src[i]["mag"] is not None else 99))
    kept: list[dict] = []
    for i in rank:
        s = src[i]
        twin = next((k for k in kept if _sep_arcsec(k, s) < DUP_ARCSEC), None)
        if twin is None:
            kept.append({**s, "aliases": []})
        else:
            twin["aliases"].append(s["name"])
    kept.sort(key=lambda s: (s["mag"] if s["mag"] is not None else 99))
    return kept


def _sep_arcsec(a: dict, b: dict) -> float:
    dra = (a["ra_deg"] - b["ra_deg"] + 180) % 360 - 180
    return 3600 * float(np.hypot(dra * np.cos(np.radians(a["dec_deg"])), a["dec_deg"] - b["dec_deg"]))


def positions_at(sources: list[dict], mjd: float) -> list[tuple[float, float]]:
    return [((s["ra_deg"] + s["dra_deg_day"] * (mjd - s["mjd0"])) % 360, s["dec_deg"] + s["ddec_deg_day"] * (mjd - s["mjd0"]))
            for s in sources]


def _field_point(e, ra: float, dec: float, size_deg: float, sources: list[dict]):
    """('row', (exposure dict, [measurement | None per source])) | ('missing', frame id) | ('lost', e)."""
    fid = f"{e.obs_id}-D{e.detector}"
    try:
        path = photometry._spectrum_cutout(e.fits_url, ra, dec, size_deg)
        ms = photometry.measure_cutout_many(path, positions_at(sources, e.mjd_mid))
    except LookupError:
        return "missing", fid
    except Exception:  # noqa: BLE001 - moved (reprocessed) or a hiccup: looked up afterwards
        return "lost", e
    if all(m is None for m in ms):
        return "missing", fid
    return "row", ({"frame_id": fid, "epoch": e.epoch, "mjd": round(e.mjd_mid, 6), "time_utc": e.time_utc,
                    "detector": e.detector}, ms)


def _field_batch(exposures, ra, dec, size_deg, sources):
    with ThreadPoolExecutor(len(exposures)) as pool:
        return list(pool.map(lambda e: _field_point(e, ra, dec, size_deg, sources), exposures))


def _key(sources: list[dict]) -> str:
    return hashlib.sha1(json.dumps([(s["id"], s["ra_deg"], s["dec_deg"]) for s in sources]).encode()).hexdigest()[:12]


def measure_field(target: dict, progress=None, processes: int | None = None, refresh: bool = False) -> dict:
    """Spectra of all catalogue sources of `target` (a parsed target.json) from every exposure there."""
    sources = sources_of(target)
    key = _key(sources)
    path = cache_path(target["id"])
    if not refresh and path.is_file():
        out = json.loads(path.read_text(encoding="utf-8"))
        if out.get("version") == VERSION and out.get("sources_key") == key:
            return out
    t0 = time.time()
    c = target["center"]
    ra, dec = round(c["ra_deg"] % 360, 4), round(c["dec_deg"], 4)
    size_deg = round(target.get("size_arcmin", 15) / 60 + 2 * MARGIN_DEG, 4)
    exposures, _ = build.cached_exposures(ra, dec)
    total, done = len(exposures), 0
    rows, missing, lost = [], [], []

    def take(results):
        nonlocal done
        for kind, v in results:
            {"row": rows, "missing": missing, "lost": lost}[kind].append(v)
        done += len(results)
        if progress:
            progress(done, total)

    procs = photometry.SPECTRUM_PROCESSES if processes is None else processes
    if procs and sources:
        batch = photometry.SPECTRUM_BATCH
        try:
            futs = [photometry._pool().submit(_field_batch, exposures[i:i + batch], ra, dec, size_deg, sources)
                    for i in range(0, total, batch)]
            for f in as_completed(futs):
                take(f.result())
        except Exception as ex:  # noqa: BLE001 - BrokenProcessPool etc.: start over with threads
            print(f"field spectra: worker processes failed ({type(ex).__name__}), using threads", file=sys.stderr)
            with photometry._proc_lock:
                photometry._proc_pool = None
            done, rows[:], missing[:], lost[:] = 0, [], [], []
            procs = 0
    if not procs and sources:
        with ThreadPoolExecutor(photometry.SPECTRUM_THREADS) as pool:
            for f in as_completed([pool.submit(_field_point, e, ra, dec, size_deg, sources) for e in exposures]):
                take([f.result()])
    for e in lost:     # second try for moved images (bucket listing inside _spectrum_cutout already ran)
        kind, v = _field_point(e, ra, dec, size_deg, sources)
        (rows.append(v) if kind == "row" else missing.append(f"{e.obs_id}-D{e.detector}"))
    rows.sort(key=lambda r: (r[0]["mjd"], r[0]["detector"]))

    def col(field):
        return [[(ms[i] or {}).get(field) for _, ms in rows] for i in range(len(sources))]

    out = {"version": VERSION, "target_id": target["id"], "center": {"ra_deg": ra, "dec_deg": dec},
           "size_deg": size_deg, "sources_key": key, "sources": sources, "exposures": [r[0] for r in rows],
           "flux_ujy": col("flux_ujy"), "err_ujy": col("err_ujy"), "wavelength_um": col("wavelength_um"),
           "bandwidth_um": col("bandwidth_um"), "masked_fraction": col("masked_fraction"),
           "missing": missing, "n_exposures": total, "seconds": round(time.time() - t0, 1),
           "unit": "uJy", "aperture_px": photometry.APERTURE_PX, "annulus_px": list(photometry.ANNULUS_PX),
           "note": photometry.NOTE}
    _write(path, out)
    return out


def _write(path: Path, out: dict) -> None:
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{threading.get_ident()}.part")
        tmp.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
        tmp.replace(path)


def source_spectrum(fs: dict, i: int) -> dict:
    """Source i of a field-spectra result in the T66 spectrum shape (frames list)."""
    s = fs["sources"][i]
    frames = []
    for k, e in enumerate(fs["exposures"]):
        f = fs["flux_ujy"][i][k]
        wl = fs["wavelength_um"][i][k]
        if wl is None:
            continue
        mf = fs["masked_fraction"][i][k]
        frames.append({**e, "flux_ujy": f, "err_ujy": fs["err_ujy"][i][k], "wavelength_um": wl,
                       "bandwidth_um": fs["bandwidth_um"][i][k], "masked_fraction": mf,
                       "masked": f is None or (mf or 0) > photometry.MAX_MASKED})
    return {"ra_deg": s["ra_deg"], "dec_deg": s["dec_deg"], "name": s["name"], "unit": "uJy",
            "aperture_px": fs["aperture_px"], "annulus_px": fs["annulus_px"], "frames": frames,
            "all_exposures": True, "n_exposures": fs["n_exposures"], "note": fs["note"]}


def seed_spectra(fs: dict) -> int:
    """Put every source's spectrum into the per-position spectrum cache (T66), so a click on a source of a
    measured field (`/api/photometry?ra=&dec=` at its position) answers at once. Existing entries stay."""
    n = 0
    for i, s in enumerate(fs["sources"]):
        sp = source_spectrum(fs, i)
        ra, dec = round(s["ra_deg"] % 360, 4), round(s["dec_deg"], 4)
        path = photometry.spectrum_cache(ra, dec)
        if path.is_file() or not sp["frames"]:
            continue
        photometry._write_spectrum(path, {**sp, "ra_deg": ra, "dec_deg": dec, "missing": fs["missing"],
                                          "seconds": None, "from_field": fs["target_id"]})
        n += 1           # anomalies (T84) are added by measure_all the first time it is read
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m pipeline.fieldspectra", description=__doc__.split("\n\n")[0])
    ap.add_argument("target_dir", type=Path)
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args(argv)
    t = json.loads((args.target_dir / "target.json").read_text(encoding="utf-8"))
    fs = measure_field(t, progress=lambda d, n: print(f"\r{d}/{n} exposures", end="", flush=True), refresh=args.refresh)
    print()
    seeded = seed_spectra(fs)
    n = len(fs["exposures"])
    good = [sum(1 for k in range(n) if fs["flux_ujy"][i][k] is not None and (fs["masked_fraction"][i][k] or 0) == 0)
            for i in range(len(fs["sources"]))]
    print(f"{len(fs['sources'])} sources x {n} exposures ({len(fs['missing'])} missing) in {fs['seconds']} s; "
          f"clean measurements per source: median {int(np.median(good)) if good else 0}; {seeded} spectra cached for clicks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
