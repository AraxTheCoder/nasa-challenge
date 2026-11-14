"""Wide stitching test: download full SPHEREx detector images (3.5 deg each), N per epoch at
different pointings. Usage: fetch_full.py <query.json> <detector> <per_epoch> <outdir>"""
import json, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests

q = json.load(open(sys.argv[1])); det = int(sys.argv[2]); k = int(sys.argv[3]); out = Path(sys.argv[4])
out.mkdir(parents=True, exist_ok=True)
pick = []
for ep in sorted({e["epoch"] for e in q["exposures"]}):
    es = sorted([e for e in q["exposures"] if e["epoch"] == ep and e["detector"] == det], key=lambda e: e["mjd_mid"])
    if not es:
        continue
    idx = [round(i * (len(es) - 1) / max(1, k - 1)) for i in range(k)] if k > 1 else [0]
    pick += [es[i] for i in sorted(set(idx))]  # spread over the epoch = different pointings
json.dump([{"obs_id": e["obs_id"], "epoch": e["epoch"], "time_utc": e["time_utc"]} for e in pick], open(out / "picked.json", "w"), indent=1)

def get(e):
    f = out / f"{e['obs_id']}_D{det}.fits"
    if f.exists() and f.stat().st_size > 1e7:
        return f.name, "cached"
    err = None
    for attempt in range(6):
        try:
            t = time.time()
            url = e["fits_url"].replace("https://irsa.ipac.caltech.edu/ibe/data/spherex/", "https://nasa-irsa-spherex.s3.amazonaws.com/")  # AWS Open Data mirror, ~4x faster
            with requests.get(url, stream=True, timeout=600) as r:
                r.raise_for_status()
                tmp = f.with_suffix(".part")
                with open(tmp, "wb") as fh:
                    for chunk in r.iter_content(1 << 20):
                        fh.write(chunk)
            if not open(tmp, "rb").read(6) == b"SIMPLE":
                raise ValueError("not FITS")
            tmp.rename(f)
            return f.name, f"{f.stat().st_size / 1e6:.0f} MB {time.time() - t:.0f}s"
        except Exception as ex:
            err = ex
            time.sleep(min(60, 3 * 2 ** attempt))
    return f.name, f"FAILED {err}"

with ThreadPoolExecutor(6) as pool:
    for name, status in pool.map(get, pick):
        print(name, status, flush=True)
print("DONE", len(pick), flush=True)
