#!/usr/bin/env bash
# T47: install or update the app from /tmp/spherex-app.tar.gz (made by deploy/deploy.sh). Run as root.
set -euo pipefail
cd /opt/spherex
rm -rf app.new && mkdir app.new && tar -xzf /tmp/spherex-app.tar.gz -C app.new
# data/ lives outside the app folder and survives updates
ln -sfn /opt/spherex/data app.new/data
rm -rf app.old; [ -d app ] && mv app app.old; mv app.new app
chown -R spherex:spherex /opt/spherex
[ -x venv/bin/python ] || sudo -u spherex python3 -m venv venv
sudo -u spherex venv/bin/pip install -q --upgrade pip
sudo -u spherex venv/bin/pip install -q -r app/requirements.lock
# Local SPHEREx image index (T31), once: ~2.5 min from here (IRSA is next door)
if [ ! -f data/mirror/index.npz ]; then
  cd app && sudo -u spherex ../venv/bin/python -m pipeline.mirror harvest && sudo -u spherex ../venv/bin/python -m pipeline.mirror build && cd ..
fi
systemctl restart spherex
sleep 3
curl -fsS http://127.0.0.1:8000/api/health && echo " <- API up"
