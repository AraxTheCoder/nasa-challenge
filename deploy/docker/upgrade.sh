#!/usr/bin/env bash
# T14: bring the public tool (https://nasa.jbarkoczi.de/) up to date with main. Run from anywhere:
#   deploy/docker/upgrade.sh
# Pulls main, then compares the checkout with the commit the running API was last deployed from
# (deploy/docker/.deployed, not committed): something else may have pulled the same checkout already
# (e.g. a dev server's auto-pull), so "the pull brought nothing" does not mean "the API is current".
# Rebuilds the API image only when its Python packages changed, restarts what changed, waits for health.
set -euo pipefail
cd "$(dirname "$0")"
repo=$(git rev-parse --show-toplevel)
state=.deployed

branch=$(git -C "$repo" rev-parse --abbrev-ref HEAD)
if [ "$branch" != "main" ]; then
  echo "The checkout is on '$branch', not main: switch first (git checkout main)." >&2
  exit 1
fi

# another process may be pulling the same checkout at this moment (FETCH_HEAD race): retry a few times
pull_failed=0
for i in 1 2 3; do
  if err=$(git -C "$repo" pull --ff-only --quiet 2>&1); then pull_failed=0; break; fi
  pull_failed=1
  sleep 5
done
[ "$pull_failed" = 1 ] && echo "warning: git pull failed (deploying the checkout as it is): $err" >&2

head=$(git -C "$repo" rev-parse HEAD)
deployed=$(cat "$state" 2>/dev/null || echo none)

changed() {   # does anything matching $1 differ between the deployed commit and the checkout?
  [ "$deployed" = none ] && return 0
  git -C "$repo" diff --name-only "$deployed" "$head" 2>/dev/null | grep -qE "$1" || \
    ! git -C "$repo" cat-file -e "$deployed^{commit}" 2>/dev/null
}

if [ "$deployed" = "$head" ]; then
  echo "Already at $(git -C "$repo" log --oneline -1)."
  docker compose up -d                        # make sure it runs
else
  echo "Deploying $(git -C "$repo" log --oneline -1) (was ${deployed:0:7})."
  if changed '^(requirements\.lock|deploy/docker/Dockerfile|\.dockerignore)$'; then
    echo "Python packages changed: rebuilding the API image."
    docker compose up -d --build
  else
    docker compose up -d                      # applies compose.yaml changes, if any
  fi
  docker compose restart api                  # new server code
  if changed '^deploy/docker/nginx\.conf$'; then
    docker compose restart web
  fi
fi

# wait for the API (startup takes a few seconds; the image index is loaded in the background)
port=$(docker compose port web 80)
for i in $(seq 1 30); do
  if curl -sf "http://$port/api/health" >/dev/null; then
    echo "$head" > "$state"
    echo "Up: http://$port/ (public: https://nasa.jbarkoczi.de/)"
    exit $(( pull_failed ? 2 : 0 ))
  fi
  sleep 2
done
echo "The API did not answer within 60 s. Log: docker compose -f $(pwd)/compose.yaml logs --tail 50 api" >&2
exit 1
