"""Reference (exploration code, not the pipeline): fetch cutouts for one detector, 8 in parallel.

    python pipeline/reference/fetch_cutouts.py <query.json> <detector> <size_deg> <outdir>

Skips files that already exist (a crude cache), retries 3 times. ~4 MB and 10-25 s per cutout."""
import json, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests

q = json.load(open(sys.argv[1])); det = int(sys.argv[2]); size = sys.argv[3]; out = Path(sys.argv[4])
out.mkdir(parents=True, exist_ok=True)
ra, dec = q["ra_deg"], q["dec_deg"]
todo = [e for e in q["exposures"] if e["detector"] == det]

def get(e):
    f = out / f"{e['obs_id']}_D{det}.fits"
    if f.exists() and f.stat().st_size > 0:
        return f.name, "cached"
    for attempt in range(3):
        try:
            t = time.time()
            r = requests.get(e["fits_url"], params={"center": f"{ra},{dec}", "size": f"{size}deg"}, timeout=300)
            r.raise_for_status()
            f.write_bytes(r.content)
            return f.name, f"{len(r.content)/1e6:.1f} MB {time.time()-t:.0f}s"
        except Exception as ex:
            err = ex
            time.sleep(3)
    return f.name, f"FAILED {err}"

with ThreadPoolExecutor(8) as pool:
    for name, status in pool.map(get, todo):
        print(name, status, flush=True)
