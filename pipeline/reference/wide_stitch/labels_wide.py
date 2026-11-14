"""Labels for the wide stitch test: notable/fast SIMBAD objects + brightest stars over the whole region,
moved to each epoch's date. Usage: labels_wide.py <hips_wide_dir>"""
import json, sys, time, io, math, collections
from pathlib import Path
import numpy as np, requests
from astropy.io.votable import parse_single_table
from astropy.time import Time
sys.path.insert(0, ".")
from pipeline.labels import SIMBAD_TAP, KIND, NOTABLE_OTYPES

d = Path(sys.argv[1]); summ = json.load(open(d / "summary.json"))
ra0, dec0, R = summ["ra_deg"], summ["dec_deg"], 3.6

def tap(q):
    for url in SIMBAD_TAP:
        try:
            r = requests.post(url + "/sync", data={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "votable", "QUERY": q}, timeout=60)
            r.raise_for_status()
            return url, parse_single_table(io.BytesIO(r.content)).to_table()
        except Exception as e:
            print("mirror failed", url.split("/")[2], str(e)[:50])
    raise SystemExit("SIMBAD down")

notable = "','".join(sorted(NOTABLE_OTYPES))
q1 = (f"SELECT main_id, ra, dec, pmra, pmdec, otype FROM basic WHERE CONTAINS(POINT('ICRS',ra,dec), CIRCLE('ICRS',{ra0},{dec0},{R}))=1 "
      f"AND (pmra*pmra + pmdec*pmdec > 40000 OR otype IN ('{notable}'))")
q2 = (f"SELECT TOP 40 b.main_id, b.ra, b.dec, b.pmra, b.pmdec, b.otype, f.flux AS vmag FROM basic AS b JOIN flux AS f ON f.oidref = b.oid "
      f"WHERE CONTAINS(POINT('ICRS',b.ra,b.dec), CIRCLE('ICRS',{ra0},{dec0},{R}))=1 AND f.filter = 'V' AND f.flux < 7.5 ORDER BY vmag")
t0 = time.time(); u1, t1 = tap(q1); u2, t2 = tap(q2)
print(f"SIMBAD: {len(t1)} notable/fast + {len(t2)} bright, {time.time() - t0:.1f}s")
ep_mjd = {e["epoch"]: float(np.mean([Time(x + "T12:00:00").mjd for x in e["dates"]])) for e in summ["epochs"]}
objs = {}
for tab, why in ((t1, "notable"), (t2, "bright")):
    for r in tab:
        name = str(r["main_id"]).replace("NAME ", "").replace("V* ", "").strip()
        if name in objs or np.ma.is_masked(r["ra"]):
            continue
        pmra = 0.0 if np.ma.is_masked(r["pmra"]) else float(r["pmra"]); pmdec = 0.0 if np.ma.is_masked(r["pmdec"]) else float(r["pmdec"])
        ra, dec, ot = float(r["ra"]), float(r["dec"]), str(r["otype"])
        pos = {ep: [ra + pmra * (m - 51544.5) / 365.25 / 3.6e6 / math.cos(math.radians(dec)), dec + pmdec * (m - 51544.5) / 365.25 / 3.6e6]
               for ep, m in ep_mjd.items()}
        objs[name] = {"name": name, "kind": KIND.get(ot, ot), "otype": ot, "pm_arcsec_yr": round(math.hypot(pmra, pmdec) / 1000, 3),
                      "V": round(float(r["vmag"]), 1) if why == "bright" and not np.ma.is_masked(r["vmag"]) else None, "why": why, "pos": pos}
out = sorted(objs.values(), key=lambda o: (o["name"] != "Barnard's star", -o["pm_arcsec_yr"]))
json.dump({"epoch_mjd": ep_mjd, "objects": out,
           "provenance": [{"service": "SIMBAD TAP " + u1, "query": q1}, {"service": "SIMBAD TAP " + u2, "query": q2}]},
          open(d / "labels_wide.json", "w"), indent=1)
print(len(out), "objects; fastest:", [(o["name"], o["pm_arcsec_yr"]) for o in out[:5]])
print(collections.Counter(o["kind"] for o in out).most_common(8))
