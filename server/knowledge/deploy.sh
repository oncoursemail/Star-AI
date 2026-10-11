#!/bin/bash
# Copy the knowledge service into the server's LXD container at /opt/star/knowledge/app and make
# sure its Python environment exists. Run from the PC (Git Bash):
#
#   bash server/knowledge/deploy.sh             # copy code, check the environment
#   bash server/knowledge/deploy.sh --install   # ... then install/refresh the systemd units and
#                                               #     restart star-knowledge (install-service.sh)
#   bash server/knowledge/deploy.sh --run FILE  # run a shell script inside the container
#
# Where the server is comes from the environment, never from this repository:
#   STAR_SERVER_SSH      ssh target of the LXD host, for example  user@192.168.1.20  (key auth only)
#   STAR_LXC_CONTAINER   name of the container the service lives in
# Put both into server/knowledge/.env (ignored by git) to avoid typing them.
# Touches only /opt/star/knowledge inside the container (and, with --install, the star-knowledge* units).
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$HERE/.env" ]; then set -a; . "$HERE/.env"; set +a; fi
HOST="${STAR_SERVER_SSH:?set STAR_SERVER_SSH (for example user@192.168.1.20) or create server/knowledge/.env}"
CT="${STAR_LXC_CONTAINER:?set STAR_LXC_CONTAINER (the LXD container name) or create server/knowledge/.env}"
case "$CT" in *[!A-Za-z0-9_-]*) echo "STAR_LXC_CONTAINER must be a plain name"; exit 2;; esac
remote() { ssh -o BatchMode=yes "$HOST" "lxc exec $CT -- bash -s"; }

if [ "${1:-}" = "--run" ]; then
  remote < "$2"
  exit 0
fi

tar -C "$HERE" --exclude='__pycache__' --exclude='eval/results' --exclude='.env' --exclude='.pytest_cache' -cf - . |
  ssh -o BatchMode=yes "$HOST" "lxc exec $CT -- bash -c 'mkdir -p /opt/star/knowledge/app && tar -xf - -C /opt/star/knowledge/app --no-same-owner && chown -R star:star /opt/star/knowledge/app'"
remote <<'REMOTE'
set -eu
cd /opt/star/knowledge
if [ ! -x venv/bin/python ]; then
  runuser -u star -- python3 -m venv --system-site-packages venv
  runuser -u star -- venv/bin/pip install --quiet --disable-pip-version-check 'numpy>=1.26,<3'
fi
runuser -u star -- venv/bin/python -c "import numpy, requests, yaml, sqlite3; print('env ok: numpy', numpy.__version__, 'sqlite', sqlite3.sqlite_version)"
ls app
REMOTE
if [ "${1:-}" = "--install" ]; then
  remote < "$HERE/install-service.sh"
fi
