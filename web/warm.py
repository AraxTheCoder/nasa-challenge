"""Pre-build ("warm") the official test fields in a Live API cache, so the demo opens them instantly.

    python web/warm.py                         # the local API, http://localhost:8000
    python web/warm.py --api https://host      # a deployed API
    python web/warm.py --refresh               # rebuild even if cached (new data release, new pipeline)
    python web/warm.py --only "Barnard's Star" --only "R Draconis"

Reads web/presets.json, the same coordinates the viewer's quick picks request, so the cache ids
match. Requests every field at once (the server shares one download limit across builds), then polls
until all are done. A cold field takes minutes to tens of minutes (IRSA throttles downloads).
Standard library only. Exit code 1 if any field failed.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PRESETS = Path(__file__).resolve().parent / "presets.json"
DONE = {"ready", "no_data", "error"}


def get(url: str) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:  # 400/404/500 carry a JSON body too (CONTRACTS "Live API")
        try:
            return json.load(e)
        except ValueError:
            return {"status": "error", "message": f"HTTP {e.code}"}


def progress_text(body: dict) -> str:
    if body.get("status") != "building":
        return body.get("status", "?") + (f": {body['message']}" if body.get("message") else "")
    p = body.get("progress") or {}
    count = f" {p['done']}/{p['total']}" if p.get("done") is not None and p.get("total") else ""
    return f"building, {p.get('step', '?')}{count}"


def main() -> int:
    ap = argparse.ArgumentParser(prog="python web/warm.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--api", default="http://localhost:8000", help="Live API base URL")
    ap.add_argument("--refresh", action="store_true", help="rebuild even if the field is cached")
    ap.add_argument("--only", action="append", default=[], help="preset name (repeatable)")
    ap.add_argument("--poll", type=float, default=5.0, help="seconds between status checks")
    args = ap.parse_args()
    sys.stdout.reconfigure(line_buffering=True)

    fields = json.loads(PRESETS.read_text(encoding="utf-8"))["fields"]
    if args.only:
        fields = [f for f in fields if f["name"] in args.only]
        if not fields:
            print(f"No preset named {args.only}", file=sys.stderr)
            return 1
    api = args.api.rstrip("/")

    jobs: dict[str, dict] = {}  # name -> {"id", "poll", "last"}
    for f in fields:
        q = {"ra": str(f["ra_deg"]), "dec": str(f["dec_deg"]), "size": str(f.get("size_arcmin", 15))}
        if args.refresh:
            q["refresh"] = "1"
        try:
            body = get(f"{api}/api/target?{urllib.parse.urlencode(q)}")
        except OSError as e:
            print(f"Can't reach the Live API at {api}: {e}", file=sys.stderr)
            return 1
        poll = body.get("poll_url") or (f"/api/jobs/{body['id']}" if body.get("id") else None)
        jobs[f["name"]] = {"id": body.get("id"), "poll": poll, "last": progress_text(body), "status": body.get("status")}
        print(f"{f['name']:<16} {body.get('id') or '-':<24} {jobs[f['name']]['last']}")

    start = time.time()
    while any(j["status"] not in DONE for j in jobs.values()):
        time.sleep(args.poll)
        for name, j in jobs.items():
            if j["status"] in DONE or not j["poll"]:
                continue
            body = get(api + j["poll"])
            j["status"] = body.get("status")
            text = progress_text(body)
            if text != j["last"]:
                j["last"] = text
                print(f"{time.time() - start:6.0f}s  {name:<16} {text}")

    failed = [n for n, j in jobs.items() if j["status"] != "ready"]
    print("\nAll fields ready." if not failed else f"\nNot ready: {', '.join(failed)}")
    for n, j in jobs.items():
        print(f"  {n:<16} {j['status']:<8} {j['id']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
