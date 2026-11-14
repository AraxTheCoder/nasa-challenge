#!/usr/bin/env bash
# T47: one-time setup of the Google Cloud VM (Debian, us-east4) as a tile generator ONLY.
# Everything else (viewer, Live API, builds) stays in Europe / on your PC and asks this VM for
# live deep-zoom tiles (python -m server --tiles-remote https://<host>).
#   sudo bash setup-vm.sh <host>      e.g. 136-107-125-170.sslip.io
set -euo pipefail
HOST="${1:?usage: setup-vm.sh <host, e.g. 1-2-3-4.sslip.io>}"
apt-get update -q
apt-get install -y -q python3 python3-venv python3-pip curl caddy
id spherex >/dev/null 2>&1 || useradd --system --create-home --home-dir /opt/spherex --shell /usr/sbin/nologin spherex
mkdir -p /opt/spherex/app /opt/spherex/data
chown -R spherex:spherex /opt/spherex

cat > /etc/systemd/system/spherex-tilegen.service <<UNIT
[Unit]
Description=SPHEREx live tile generator (tilegen, T47)
After=network-online.target
Wants=network-online.target

[Service]
User=spherex
WorkingDirectory=/opt/spherex/app
ExecStart=/opt/spherex/venv/bin/python -m tilegen --host 127.0.0.1 --port 8100 --slots 8
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1
# Next to the bucket S3 is fast (38-95 MB/s measured): use 3 images per tile, as designed.
Environment=TILEGEN_IMAGES=3

[Install]
WantedBy=multi-user.target
UNIT

# Only the tile generator is reachable from outside; HTTPS via Let's Encrypt on sslip.io.
cat > /etc/caddy/Caddyfile <<CADDY
${HOST} {
	encode gzip
	@tilegen path /tiles/* /health
	handle @tilegen {
		reverse_proxy 127.0.0.1:8100
	}
	handle {
		respond "SPHEREx tile generator. GET /health, /tiles/live/..." 404
	}
}
CADDY
systemctl daemon-reload
systemctl enable spherex-tilegen caddy
systemctl restart caddy
echo "setup done for https://${HOST}/"
