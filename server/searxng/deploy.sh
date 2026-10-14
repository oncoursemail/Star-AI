#!/bin/bash
# Copy server/searxng to the server's starai container and run install.sh there (from the PC, Git Bash).
#   STAR_SERVER_SSH=<user>@<server> bash server/searxng/deploy.sh
# (the address is not in the repo; see the private notes). Never restarts star-brain.
set -eu
: "${STAR_SERVER_SSH:?set STAR_SERVER_SSH=<user>@<server>}"
CONTAINER="${STAR_CONTAINER:-starai}"
cd "$(dirname "$0")"
tar -cf - settings.yml searxng.service star-search-gateway.service gateway.py install.sh \
  | ssh -o BatchMode=yes "$STAR_SERVER_SSH" "lxc exec $CONTAINER -- bash -c 'rm -rf /tmp/star-searxng && mkdir -p /tmp/star-searxng && tar -C /tmp/star-searxng -xf - && bash /tmp/star-searxng/install.sh'"
