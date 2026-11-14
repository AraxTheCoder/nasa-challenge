"""T73–T75: the discovery survey, pilot. Suggests interesting sources automatically, field by field.

    python -m pipeline.survey manifest                 # pass 0: pilot fields + their SPHEREx coverage
    python -m pipeline.survey run [--limit N]          # pass 1 + 2 for every manifest field, then the index
    python -m pipeline.survey index                    # only rebuild data/survey/discoveries.json

Options: --api (Live API, default http://127.0.0.1:8000), --data (the API's data folder, default data).

- Pass 0 (T73): the pilot = the five official test fields (built-in validation) + the quick picks of
  web/discover.json (fast stars, brown dwarfs), each with its HEALPix tile and SPHEREx coverage from the local
  image index. → data/survey/manifest.json
- Pass 1 (T74): per field, through the Live API: build the field, ask for its catalogue sources (SIMBAD, Gaia,
  ... = labels), measure every source in every exposure there (T85 field spectra, one read per exposure).
  Runs wherever a Live API runs (here, the VM next to the bucket, an HPC node), the API does the reading.
- Pass 2 (T75): per field, T86 spectral outliers (shape out of the field's ordinary range) and
  `pipeline.variability` (brighter / fainter between epochs at the same wavelength). → data/survey/fields/<id>.json,
  then all fields → data/survey/discoveries.json (CONTRACTS "Discoveries", the viewer's Candidates panel).

Blind mover search is not part of it on purpose (TEAM.md Questions, T06): stars move <= ~2 px within SPHEREx's
data and every asteroid a single exposure sees is long known; the spectra are what is new.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
API = "http://127.0.0.1:8000"
ORDER = 6                    # HEALPix order of the survey tiles (T73), nested
FIELD_ARCMIN = 15            # pilot fields: the quick picks' size, at least this
OPEN_ARCMIN = 10             # a candidate opens a field this size around it
POLL_S = 3


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def tile(ra: float, dec: float, order: int = ORDER) -> int:
    import astropy.units as u
    from astropy_healpix import HEALPix
    return int(HEALPix(nside=2 ** order, order="nested").lonlat_to_healpix(ra * u.deg, dec * u.deg))


# -- pass 0 ---------------------------------------------------------------------------------------------------

def pilot_fields() -> list[dict]:
    out = []
    for f, why in (("presets.json", "official test field"), ("discover.json", None)):
        for x in json.loads((REPO / "web" / f).read_text(encoding="utf-8"))["fields"]:
            out.append({"name": x["name"], "ra_deg": x["ra_deg"], "dec_deg": x["dec_deg"],
                        "size_arcmin": max(FIELD_ARCMIN, x.get("size_arcmin", FIELD_ARCMIN)),
                        "group": why or x.get("group", "quick pick")})
    return out


def manifest(data: Path) -> dict:
    from . import mirror
    fields = pilot_fields()
    local = mirror.available()
    for f in fields:
        f["tile"] = {"order": ORDER, "ipix": tile(f["ra_deg"], f["dec_deg"])}
        if local:
            exps = mirror.find_exposures_local(f["ra_deg"], f["dec_deg"])[0]
            f["coverage"] = {"images": len(exps), "epochs": len({e.epoch for e in exps}),
                             "first": min((e.time_utc for e in exps), default=None),
                             "last": max((e.time_utc for e in exps), default=None)}
    m = {"created_utc": _now(), "pilot": "5 official test fields + web/discover.json quick picks",
         "tile_order": ORDER, "fields": fields}
    out = data / "survey" / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding="utf-8")
    return m


# -- pass 1: through the Live API ------------------------------------------------------------------------------

def _poll(get, url: str, done, timeout_s: float, what: str, **params):
    t0 = time.time()
    while True:
        r = get(url, params=params, timeout=120)
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if done(r, body):
            return body
        if r.status_code >= 400 and r.status_code != 404:
            raise RuntimeError(f"{what}: HTTP {r.status_code} {body.get('message', '')}")
        if time.time() - t0 > timeout_s:
            raise TimeoutError(f"{what}: not ready after {timeout_s:.0f} s")
        time.sleep(POLL_S)
        params = {k: v for k, v in params.items() if k != "start"}     # start once, then poll


def run_field(api: str, f: dict, get=None, log=print) -> dict:
    """Build the field, its labels and T85/T86 on the Live API. Returns {"target_id", "outliers"}."""
    import requests
    get = get or requests.get
    body = _poll(get, f"{api}/api/target", lambda r, b: b.get("status") == "ready", 1800, "build",
                 ra=f["ra_deg"], dec=f["dec_deg"], size=f["size_arcmin"])
    tid = body["id"]
    log(f"  built {tid}")
    _poll(get, f"{api}/api/targets/{tid}/labels", lambda r, b: b.get("status") == "ready", 900, "labels")
    log("  labels ready")
    out = _poll(get, f"{api}/api/targets/{tid}/spectral-outliers",
                lambda r, b: b.get("status") in ("ready", "no_data"), 3600, "field spectra", start=1)
    log(f"  field spectra + outliers: {out.get('summary', out.get('status'))}")
    return {"target_id": tid, "outliers": out}


# -- pass 2 -----------------------------------------------------------------------------------------------------

def _score01(raw: float, scale: float) -> float:
    return 1 - math.exp(-max(raw, 0) / scale)


def _known(item: dict) -> str | None:
    """A source SIMBAD already classes as something special (variable, young star, galaxy, ...) is a known
    object: listing it checks the search. Plain stars and Gaia-only sources are not."""
    o = (item.get("otype") or "").strip()
    return item.get("name") if o and o not in ("*", "**") else None


def candidates(field: dict, target_id: str, outliers: dict, variables: dict) -> list[dict]:
    out = []
    for it in outliers.get("items", []):
        devs = it.get("deviations") or []
        strongest = max(devs, key=lambda d: abs(d.get("z") or 0), default=None)
        cls = "brown_dwarf" if any("brown dwarf" in (d.get("meaning") or "") for d in devs) else "spectral"
        known = _known(it)
        score = _score01(it.get("score", 0), 15) * (0.6 if known else 1) * (0.5 if it.get("caveats") else 1)
        reason = it.get("reason", "")
        if it.get("caveats"):
            reason += " Caveats: " + "; ".join(it["caveats"]) + "."
        c = {"id": f"{target_id}-s-{it['id']}", "name": it.get("name"), "ra_deg": round(it["ra_deg"], 6),
             "dec_deg": round(it["dec_deg"], 6), "size_arcmin": OPEN_ARCMIN, "class": cls, "score": round(score, 3),
             "reason": f"Odd spectrum for this field: {reason}", "known": known,
             "tile": {"order": ORDER, "ipix": tile(it["ra_deg"], it["dec_deg"])},
             "evidence": {"field": field["name"], "target_id": target_id, "t86_score": it.get("score"),
                          "chi2": it.get("chi2"), "deviations": devs}}
        if strongest and strongest.get("um_min"):
            c["lam_um"] = round((strongest["um_min"] + strongest["um_max"]) / 2, 3)
        out.append(c)
    for v in variables.get("items", []):
        known = v["name"] if v.get("known_variable") else _known(v)
        score = _score01(v["score"], 10) * (0.6 if known else 1) * (0.5 if v.get("caveats") else 1)
        reason = v["reason"] + (" Caveats: " + "; ".join(v["caveats"]) + "." if v.get("caveats") else "")
        out.append({"id": f"{target_id}-v-{v['id']}", "name": v.get("name"), "ra_deg": round(v["ra_deg"], 6),
                    "dec_deg": round(v["dec_deg"], 6), "size_arcmin": OPEN_ARCMIN, "class": "variable",
                    "score": round(score, 3), "reason": reason, "known": known,
                    "lam_um": round((v["um_min"] + v["um_max"]) / 2, 3),
                    "tile": {"order": ORDER, "ipix": tile(v["ra_deg"], v["dec_deg"])},
                    "evidence": {"field": field["name"], "target_id": target_id,
                                 **{k: v[k] for k in ("pct", "epochs", "dates", "bands", "bands_shared",
                                                      "um_min", "um_max", "field_scatter_pct", "score")}}})
    return out


def judge_field(data: Path, field: dict, target_id: str, outliers: dict) -> dict:
    from .variability import find_variables
    fs_path = data / "field_spectra" / f"{target_id}.json"
    variables = find_variables(json.loads(fs_path.read_text(encoding="utf-8"))) if fs_path.is_file() else {"items": []}
    res = {"field": field, "target_id": target_id, "judged_utc": _now(),
           "outliers_summary": outliers.get("summary"), "n_sources": outliers.get("n_sources"),
           "n_judged": outliers.get("n_judged"), "variables_judged": variables.get("n_judged"),
           "variables_method": variables.get("method"),
           "candidates": candidates(field, target_id, outliers, variables)}
    out = data / "survey" / "fields" / f"{target_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    return res


def write_index(data: Path, api: str | None = None) -> dict:
    fields = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((data / "survey" / "fields").glob("*.json"))]
    cands = sorted((c for f in fields for c in f["candidates"]), key=lambda c: (-c["score"], c["id"]))
    n_src = sum(f.get("n_judged") or 0 for f in fields)
    idx = {"synthetic": False,
           "survey": f"pilot survey (T73–T75), {len(fields)} fields",
           "description": f"Computed, not hand-picked: {n_src} catalogue sources in {len(fields)} pilot fields "
                          f"(the 5 official test fields + quick picks), each measured in every SPHEREx exposure "
                          f"there; listed when the spectrum's shape is out of the field's ordinary range (T86) or "
                          f"the brightness changed between epochs at the same wavelength (T75).",
           "generated_utc": _now(),
           "method": "T85 field spectra (aperture photometry at catalogue positions), T86 spectral outliers, "
                     "pipeline.variability; score = 1 − exp(−raw/scale), × 0.6 for objects SIMBAD already classes, "
                     "× 0.5 with caveats (blend, galaxy)",
           "provenance": [{"service": f"SPHEREx Live API {api or ''}".strip(),
                           "query": "per field: /api/target, /labels, /spectral-outliers; pipeline.variability on "
                                    "data/field_spectra/<id>.json",
                           "retrieved_utc": max((f["judged_utc"] for f in fields), default=_now())}],
           "fields": [{"name": f["field"]["name"], "target_id": f["target_id"], "n_judged": f.get("n_judged"),
                       "candidates": len(f["candidates"]), "summary": f.get("outliers_summary")} for f in fields],
           "candidates": cands}
    out = data / "survey" / "discoveries.json"
    out.write_text(json.dumps(idx, indent=1, ensure_ascii=False), encoding="utf-8")
    return idx


def run(api: str, data: Path, limit: int | None = None, log=print) -> dict:
    m_path = data / "survey" / "manifest.json"
    m = json.loads(m_path.read_text(encoding="utf-8")) if m_path.is_file() else manifest(data)
    failed = []
    for n, f in enumerate(m["fields"][:limit], 1):
        log(f"[{n}/{len(m['fields'][:limit])}] {f['name']}")
        try:
            r = run_field(api, f, log=log)
            if r["outliers"].get("status") != "ready":
                log(f"  skipped: {r['outliers'].get('status')}")
                continue
            res = judge_field(data, f, r["target_id"], r["outliers"])
            log(f"  {len(res['candidates'])} candidates")
        except Exception as e:  # noqa: BLE001 - one field shouldn't stop the survey
            failed.append(f["name"])
            log(f"  FAILED: {e}")
    idx = write_index(data, api)
    log(f"wrote {data / 'survey' / 'discoveries.json'}: {len(idx['candidates'])} candidates from "
        f"{len(idx['fields'])} fields" + (f"; failed: {', '.join(failed)}" if failed else ""))
    return idx


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["manifest", "run", "index"])
    ap.add_argument("--api", default=API)
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument("--limit", type=int)
    a = ap.parse_args(argv)
    if a.cmd == "manifest":
        m = manifest(a.data)
        print(f"wrote {a.data / 'survey' / 'manifest.json'}: {len(m['fields'])} fields")
    elif a.cmd == "run":
        run(a.api.rstrip("/"), a.data, a.limit)
    else:
        idx = write_index(a.data)
        print(f"{len(idx['candidates'])} candidates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
