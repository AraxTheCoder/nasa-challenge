# deploy/docker: the public tool at https://nasa.jbarkoczi.de/ (T14)

```
browser ──https──▶ AWS nginx (TLS, nasa.jbarkoczi.de) ──WireGuard──▶ 10.0.0.2:8090 (this machine)
                                                                     └ web  (nginx): /  → /web/, static web/ + fixtures/
                                                                       └ /api/ → api (python -m server --public --trust-proxy)
```

Viewer and API share one origin, so `web/api.js` uses `location.origin` as the API (no `?api=`).

| What | Value |
|---|---|
| Port | `10.0.0.2:8090` (WireGuard address only; `BIND_ADDR` / `PORT` in `.env` change it) |
| Code | the repo checkout, bind-mounted read-only (`/app`); the image holds only the Python packages |
| Data | `../../data` bind-mounted read-write: warm caches, image index, community database, shared with dev runs |
| Limits | `--public`: per-IP rates (client IP = first `X-Forwarded-For` entry), 4 jobs at once, cache cap 12 GB + 5 GB disk kept free |
| Admin token | `SPHEREX_ADMIN_TOKEN` in `deploy/docker/.env` (gitignored; needed for `refresh=1` and `POST /api/settings`) |

**Update to the latest main:** `deploy/docker/upgrade.sh` (from anywhere). It pulls main, rebuilds the API image only
when `requirements.lock` / the Dockerfile changed, restarts the API (and nginx when `nginx.conf` changed), and waits
until the API answers. web/ changes are live right after the pull (no-cache + ETag).

```
cd deploy/docker
docker compose up -d --build          # first start; containers restart by themselves after a reboot
docker compose up -d --build          # after requirements.lock changed
docker compose logs -f api            # API log
docker compose down                   # stop
```

## AWS nginx (in front)

TLS certificate for the name (once): `sudo certbot certonly --nginx -d nasa.jbarkoczi.de`. Add the name to the
port-80 redirect block, then:

```nginx
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name nasa.jbarkoczi.de;

    ssl_certificate /etc/letsencrypt/live/nasa.jbarkoczi.de/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/nasa.jbarkoczi.de/privkey.pem;

    client_max_body_size 1m;

    location / {
        proxy_pass http://10.0.0.2:8090;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;   # set, not appended: clients can't fake their IP for the limits
        proxy_set_header X-Forwarded-Proto https;
        proxy_connect_timeout 5s;
        proxy_read_timeout 300s;
        proxy_buffering off;                             # map tiles stream as they are rendered
    }
}
```

Check: `curl -sI https://nasa.jbarkoczi.de/` → `302`, `Location: /web/`; `curl -s https://nasa.jbarkoczi.de/api/health`.
