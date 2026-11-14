# deploy/ — tile generator on Google Cloud next to the SPHEREx bucket (T47)

Why: the SPHEREx data is in AWS `us-east-1`. From Europe it came at 0.04-0.1 MB/s per connection on
2026-11-14; from a VM in Google Cloud `us-east4` (N. Virginia) at 38-95 MB/s (measured on the VM).

Split: **only `tilegen` runs on the VM**: live deep-zoom tiles, and (T57) the cutouts for builds.
Viewer, Live API, builds and all caches stay in Europe / on your PC; the Live API asks the VM for
tiles and cutouts and caches what it gets. Switch between local and VM tile rendering in the viewer
("Tiles" in the map bar) or with `POST /api/settings {"tiles": "local"|"remote"}`.

Cutouts (T57): on "Show" the build asks `GET /cutout?url=&ra=&dec=&size=` for each image; the VM
reads the rows from the bucket, cuts them and returns the cutout FITS gzipped (~200 kB instead of
~2-3 MB of rows per image over the Atlantic). VM down or old → the build reads S3 directly (paused
for 60 s after a failure), then IRSA. `python -m server --cutouts-remote none` turns it off;
`GET /api/settings` shows `cutouts: remote|s3`.

| What | Value |
|---|---|
| Project | `nasa-us-east-worker` |
| VM | `instance-20261114-132040`, zone `us-east4-a`, e2-medium, Debian 13 |
| URL | `https://136-107-125-170.sslip.io/` — only `/health`, `/tiles/live/...` and `/cutout` (Caddy, Let's Encrypt) |
| Code | `/opt/spherex/app` (from `git archive HEAD`; no GitHub credentials on the VM), venv `/opt/spherex/venv` |
| Data | `/opt/spherex/data`: image index mirror, S3 row chunks, rendered tiles; kept across updates |
| Service | `spherex-tilegen` (systemd: `python -m tilegen --port 8100`, `TILEGEN_IMAGES=3`) |

Local side (your PC):

    python -m server --tiles-remote https://136-107-125-170.sslip.io            # starts with local tiles
    python -m server --tiles-remote https://136-107-125-170.sslip.io --use-remote

First time on the VM (done 2026-11-14):

    gcloud compute scp deploy/setup-vm.sh <instance>:/tmp/ --zone us-east4-a
    gcloud compute ssh <instance> --zone us-east4-a --command "sudo bash /tmp/setup-vm.sh 136-107-125-170.sslip.io"

Every update (repo root, committed state; `GCLOUD=` path to gcloud if it is not on PATH):

    deploy/deploy.sh

Logs: `gcloud compute ssh <instance> --zone us-east4-a --command "sudo journalctl -u spherex-tilegen -n 100"`.
Stop paying when not needed: `gcloud compute instances stop <instance> --zone us-east4-a`.
