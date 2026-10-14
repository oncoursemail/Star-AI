#!/bin/bash
# Copy the training-data generator into the server container and drive it. Run from the PC (Git Bash):
#
#   bash server/training/deploy.sh                      copy the code to /opt/star/training/app
#   bash server/training/deploy.sh --install            ... then install the systemd unit (not started)
#   bash server/training/deploy.sh --suites DIR         copy an evaluation-suite folder (evals/roblox) to the server
#                                                       for the decontamination index (data, never committed)
#   bash server/training/deploy.sh --ctl CMD [ARG]      trainctl.sh CMD inside the container (start, stop, status ...)
#   bash server/training/deploy.sh --exec CMD...        python -m startrain CMD... as user star in the container
#   bash server/training/deploy.sh --live               run tests/live_gates.py (the gates against the real Luau tools)
#
# Where the server is comes from the environment, never from this repository:
#   STAR_SERVER_SSH      ssh target of the LXD host, for example  user@lxd-host  (key auth only)
#   STAR_LXC_CONTAINER   name of the container
# Put both into server/training/.env (ignored by git) or reuse server/knowledge/.env.
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
for envfile in "$HERE/.env" "$HERE/../knowledge/.env"; do
  if [ -f "$envfile" ]; then set -a; . "$envfile"; set +a; break; fi
done
HOST="${STAR_SERVER_SSH:?set STAR_SERVER_SSH (user@host of the LXD host) or create server/training/.env}"
CT="${STAR_LXC_CONTAINER:?set STAR_LXC_CONTAINER or create server/training/.env}"
case "$CT" in *[!A-Za-z0-9_-]*) echo "STAR_LXC_CONTAINER must be a plain name"; exit 2;; esac
remote() { ssh -o BatchMode=yes "$HOST" "lxc exec $CT -- bash -s"; }

case "${1:-}" in
  --ctl)
    shift
    printf 'bash /opt/star/training/app/trainctl.sh %s\n' "$*" | remote
    exit 0 ;;
  --exec)
    shift
    printf 'cd /opt/star/training/app && runuser -u star -- env STAR_TRAIN_HOME=/opt/star/training STAR_KB_APP=/opt/star/knowledge/app STAR_LUAU_TOOLS=/opt/star/knowledge/tools STAR_BRAIN_KEY_FILE=/opt/star/secrets/api_keys /usr/bin/python3 -m startrain %s\n' "$*" | remote
    exit 0 ;;
  --live)
    printf 'cd /opt/star/training/app && runuser -u star -- env STAR_TRAIN_HOME=/opt/star/training STAR_KB_APP=/opt/star/knowledge/app STAR_LUAU_TOOLS=/opt/star/knowledge/tools /usr/bin/python3 tests/live_gates.py\n' | remote
    exit 0 ;;
  --suites)
    DIR="${2:?folder with golden-tasks-*.json, reference/, tests/}"
    tar -C "$DIR" -cf - . | ssh -o BatchMode=yes "$HOST" "lxc exec $CT -- bash -c 'rm -rf /opt/star/training/suites && mkdir -p /opt/star/training/suites && tar -xf - -C /opt/star/training/suites --no-same-owner && chown -R star:star /opt/star/training && chmod -R go-rwx /opt/star/training/suites'"
    echo "suites copied"
    exit 0 ;;
esac

tar -C "$HERE" --exclude='__pycache__' --exclude='.env' --exclude='.pytest_cache' -cf - . |
  ssh -o BatchMode=yes "$HOST" "lxc exec $CT -- bash -c 'mkdir -p /opt/star/training/app && tar -xf - -C /opt/star/training/app --no-same-owner && chown -R star:star /opt/star/training/app'"
echo "code copied to /opt/star/training/app"
if [ "${1:-}" = "--install" ]; then
  remote < "$HERE/install-service.sh"
fi
