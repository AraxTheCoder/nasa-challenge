#!/usr/bin/env bash
# T47: one-time setup of the Google Cloud VM (Debian, us-east4). Run as root: sudo bash setup-vm.sh <host>
# <host> is the public name Caddy gets a certificate for, e.g. 136-107-125-170.sslip.io
set -euo pipefail
HOST="${1:?usage: setup-vm.sh <host, e.g. 1-2-3-4.sslip.io>}"
apt-get update -q
apt-get install -y -q python3 python3-venv python3-pip git curl caddy
id spherex >/dev/null 2>&1 || useradd --system --create-home --home-dir /opt/spherex --shell /usr/sbin/nologin spherex
mkdir -p /opt/spherex/app /opt/spherex/data
chown -R spherex:spherex /opt/spherex

cat > /etc/systemd/system/spherex.service <<UNIT
[Unit]
Description=SPHEREx Blink Live API (T47)
After=network-online.target
Wants=network-online.target

[Service]
User=spherex
WorkingDirectory=/opt/spherex/app
ExecStart=/opt/spherex/venv/bin/python -m server --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/caddy/Caddyfile <<CADDY
${HOST} {
	encode gzip
	handle /api/* {
		reverse_proxy 127.0.0.1:8000
	}
	handle {
		root * /opt/spherex/app/web
		file_server
	}
}
CADDY
systemctl daemon-reload
systemctl enable spherex caddy
systemctl restart caddy
echo "setup done for https://${HOST}/"
