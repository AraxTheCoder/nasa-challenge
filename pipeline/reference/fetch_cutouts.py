"""Reference (exploration code, not the pipeline): fetch cutouts for one detector, 8 in parallel.

    python pipeline/reference/fetch_cutouts.py <query.json> <detector> <size_deg> <outdir>

Skips files that already exist (a crude cache), retries 6 times with backoff, 4 in parallel. ~4 MB and 10-25 s per cutout."""
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
    err = None
    for attempt in range(6):  # IRSA answers 503 / drops connections under load: back off and retry
        try:
            t = time.time()
            r = requests.get(e["fits_url"], params={"center": f"{ra},{dec}", "size": f"{size}deg"}, timeout=300)
            r.raise_for_status()
            if not r.content.startswith(b"SIMPLE"):
                raise ValueError(f"not a FITS file ({len(r.content)} bytes)")
            tmp = f.with_suffix(".part")
            tmp.write_bytes(r.content)
            tmp.rename(f)  # never leave a half-written file that later counts as cached
            return f.name, f"{len(r.content)/1e6:.1f} MB {time.time()-t:.0f}s"
        except Exception as ex:
            err = ex
            time.sleep(min(60, 3 * 2 ** attempt))
    return f.name, f"FAILED {err}"

results = []
with ThreadPoolExecutor(4) as pool:
    for name, status in pool.map(get, todo):
        print(name, status, flush=True)
        results.append(status)
failed = sum(s.startswith("FAILED") for s in results)
print(f"{len(results) - failed}/{len(results)} cutouts present, {failed} failed", flush=True)
