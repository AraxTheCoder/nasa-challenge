# deploy/ — hosting on Google Cloud next to the SPHEREx bucket (T47)

Why: the SPHEREx data is in AWS `us-east-1`. From Europe it came at 0.04-0.1 MB/s per connection on
2026-11-14; from a VM in Google Cloud `us-east4` (N. Virginia) at 38-95 MB/s (measured on the VM).
So the Live API runs there and the browser only gets finished tiles.

| What | Value |
|---|---|
| Project | `nasa-us-east-worker` |
| VM | `instance-20261114-132040`, zone `us-east4-a`, e2-medium, Debian |
| URL | `https://<ip-with-dashes>.sslip.io/` (Caddy gets a Let's Encrypt certificate; no own domain) |
| App | `/opt/spherex/app` (from `git archive HEAD`, no GitHub credentials on the VM), venv `/opt/spherex/venv` |
| Data | `/opt/spherex/data` (index mirror, caches, built fields), kept across updates |
| Services | `spherex` (systemd, `python -m server` on 127.0.0.1:8000), `caddy` (443 → /api/* proxied, rest = `web/`) |

First time (once):

    gcloud compute scp deploy/setup-vm.sh <instance>:/tmp/ --zone us-east4-a
    gcloud compute ssh <instance> --zone us-east4-a --command "sudo bash /tmp/setup-vm.sh <ip-with-dashes>.sslip.io"

Every update (from the repo root, committed state):

    deploy/deploy.sh

Logs: `gcloud compute ssh <instance> --zone us-east4-a --command "sudo journalctl -u spherex -n 100"`.
