#!/usr/bin/env bash
# T47: install or update the code from /tmp/spherex-app.tar.gz (made by deploy/deploy.sh). Run as root.
set -euo pipefail
cd /opt/spherex
rm -rf app.new && mkdir app.new && tar -xzf /tmp/spherex-app.tar.gz -C app.new
ln -sfn /opt/spherex/data app.new/data          # data/ (index, chunk + tile caches) survives updates
rm -rf app.old; if [ -d app ]; then mv app app.old; fi; mv app.new app
chown -R spherex:spherex /opt/spherex
[ -x venv/bin/python ] || sudo -u spherex python3 -m venv venv
sudo -u spherex venv/bin/pip install -q --upgrade pip
sudo -u spherex venv/bin/pip install -q -r app/requirements.lock
# Local SPHEREx image index (T31) that tilegen picks images from; once, ~2.5 min next to IRSA.
if [ ! -f data/mirror/index.npz ]; then
  (cd app && sudo -u spherex ../venv/bin/python -m pipeline.mirror harvest \
          && sudo -u spherex ../venv/bin/python -m pipeline.mirror build)
fi
systemctl restart spherex-tilegen
for i in $(seq 1 20); do
  if curl -fsS http://127.0.0.1:8100/health; then echo " <- tilegen up"; exit 0; fi
  sleep 1
done
echo "tilegen did not come up:"; journalctl -u spherex-tilegen -n 50 --no-pager; exit 1
