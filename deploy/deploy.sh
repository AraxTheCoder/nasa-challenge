#!/usr/bin/env bash
# T47: push the current commit to the Google Cloud VM and (re)start it.
#   deploy/deploy.sh [instance] [zone]      (gcloud must be logged in; see deploy/README.md)
set -euo pipefail
INSTANCE="${1:-instance-20261114-132040}"
ZONE="${2:-us-east4-a}"
GCLOUD="${GCLOUD:-gcloud}"
cd "$(git rev-parse --show-toplevel)"
git archive --format=tar.gz -o /tmp/spherex-app.tar.gz HEAD
"$GCLOUD" compute scp --zone "$ZONE" --quiet /tmp/spherex-app.tar.gz deploy/install-app.sh deploy/setup-vm.sh "$INSTANCE":/tmp/
"$GCLOUD" compute ssh "$INSTANCE" --zone "$ZONE" --quiet --command "sudo bash /tmp/install-app.sh"
