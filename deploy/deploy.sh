#!/usr/bin/env bash
# T47: push the committed state (HEAD) to the tile-generator VM and restart it.
#   deploy/deploy.sh [instance] [zone]     (gcloud logged in; GCLOUD=<path> if it is not on PATH)
set -euo pipefail
INSTANCE="${1:-instance-20261114-132040}"
ZONE="${2:-us-east4-a}"
GCLOUD="${GCLOUD:-gcloud}"
cd "$(git rev-parse --show-toplevel)"
TMP="$(mktemp -d)"
git archive --format=tar.gz -o "$TMP/spherex-app.tar.gz" HEAD
git show HEAD:deploy/install-app.sh > "$TMP/install-app.sh"      # LF line endings, as committed
# Windows (Git Bash) gcloud wants Windows paths
if command -v cygpath >/dev/null 2>&1; then W() { cygpath -w "$1"; }; else W() { echo "$1"; }; fi
"$GCLOUD" compute scp --zone "$ZONE" --quiet "$(W "$TMP/spherex-app.tar.gz")" "$(W "$TMP/install-app.sh")" "$INSTANCE":/tmp/
"$GCLOUD" compute ssh "$INSTANCE" --zone "$ZONE" --quiet --command "sudo bash /tmp/install-app.sh"
rm -rf "$TMP"
