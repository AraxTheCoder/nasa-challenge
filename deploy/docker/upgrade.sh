#!/usr/bin/env bash
# T14: bring the public tool (https://nasa.jbarkoczi.de/) up to date with main. Run from anywhere:
#   deploy/docker/upgrade.sh
# Pulls main, rebuilds the API image only when its Python packages changed, restarts what changed,
# and waits until the API answers again.
set -euo pipefail
cd "$(dirname "$0")"
repo=$(git rev-parse --show-toplevel)

branch=$(git -C "$repo" rev-parse --abbrev-ref HEAD)
if [ "$branch" != "main" ]; then
  echo "The checkout is on '$branch', not main: switch first (git checkout main)." >&2
  exit 1
fi

before=$(git -C "$repo" rev-parse HEAD)
git -C "$repo" pull --ff-only --quiet
after=$(git -C "$repo" rev-parse HEAD)

changed() { [ "$before" != "$after" ] && git -C "$repo" diff --name-only "$before" "$after" | grep -qE "$1"; }

if [ "$before" = "$after" ]; then
  echo "Already at $(git -C "$repo" log --oneline -1)."
  docker compose up -d                        # make sure it runs (e.g. after a reboot without the service)
else
  echo "Updated to $(git -C "$repo" log --oneline -1)."
  if changed '^(requirements\.lock|deploy/docker/Dockerfile|\.dockerignore)$'; then
    echo "Python packages changed: rebuilding the API image."
    docker compose up -d --build
  else
    docker compose up -d                      # applies compose.yaml changes, if any
    docker compose restart api                # new server code
  fi
  if changed '^deploy/docker/nginx\.conf$'; then
    docker compose restart web
  fi
fi

# wait for the API (startup takes a few seconds; the image index is loaded in the background)
port=$(docker compose port web 80)
for i in $(seq 1 30); do
  if curl -sf "http://$port/api/health" >/dev/null; then
    echo "Up: http://$port/ (public: https://nasa.jbarkoczi.de/)"
    exit 0
  fi
  sleep 2
done
echo "The API did not answer within 60 s. Log: docker compose -f $(pwd)/compose.yaml logs --tail 50 api" >&2
exit 1
