#!/usr/bin/env bash
# Install or update STAR's resource planner. Run from the repository root on the PC (Git Bash):
#
#   STAR_SERVER_SSH=<user@brain 1 LXD host> bash server/planner/deploy.sh [--start]
#   STAR_SERVER2_SSH=<user@brain 2 LXD host> STAR_PLANNER_REPORT_TO=http://<brain 1 container>:8098 \
#       bash server/planner/deploy.sh --agent [--start]
#   STAR_SERVER_SSH=... bash server/planner/deploy.sh --status
#
# Brain 1: copies the planner's few stdlib-only modules to /opt/star/planner/app, creates the report token
# /opt/star/secrets/planner_report_token (never printed), installs star-planner.service; --start enables and
# (re)starts it. It restarts NOTHING else: not star-brain, not night school, not the knowledge service.
# Brain 2 (--agent): the same code, the report token copied over ssh (stdin, never shown), the planner's address in
# /opt/star/planner/env, and star-planner-agent.service.
# Addresses and user names are operator configuration and never stored in the repository.
set -euo pipefail

container="${STAR_LXC_CONTAINER:-starai}"
start=0 agent=0 status=0
while [ $# -gt 0 ]; do
  case "$1" in
    --start) start=1; shift ;;
    --agent) agent=1; shift ;;
    --status) status=1; shift ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
done
root="$(git rev-parse --show-toplevel)"
cd "$root"
files="star/__init__.py star/version.py star/orchestration.py star/agent_resource_planner.py star/studio_test_farm.py
star/resource_probes.py star/resource_planner_service.py star/planner_client.py"

ship() {   # $1 = ssh target: code into /opt/star/planner/app (owner star)
  ssh -o BatchMode=yes -o ConnectTimeout=15 "$1" "lxc exec $container -- install -d -o star -g star /opt/star/planner /opt/star/planner/app"
  # shellcheck disable=SC2086
  git archive HEAD $files | ssh -o BatchMode=yes "$1" "lxc exec $container -- runuser -u star -- tar -x -C /opt/star/planner/app"
  ssh -o BatchMode=yes "$1" "lxc exec $container -- runuser -u star -- python3 -c 'import sys; sys.path.insert(0, \"/opt/star/planner/app\"); import star.resource_planner_service; print(\"planner code ok\")'"
}

if [ "$status" = 1 ]; then
  target="${STAR_SERVER_SSH:?set STAR_SERVER_SSH}"
  ssh -o BatchMode=yes "$target" "lxc exec $container -- systemctl is-active star-planner" || true
  ssh -o BatchMode=yes "$target" "lxc exec $container -- journalctl -u star-planner -n 10 --no-pager -o cat" || true
  ssh -o BatchMode=yes "$target" "lxc exec $container -- curl -s --max-time 5 http://127.0.0.1:8098/v1/status" | head -c 3000 || true
  echo
  exit 0
fi

if [ "$agent" = 0 ]; then
  target="${STAR_SERVER_SSH:?set STAR_SERVER_SSH to user@address of brain 1's LXD host}"
  echo "== brain 1: code (git HEAD $(git rev-parse --short HEAD))"
  ship "$target"
  ssh -o BatchMode=yes "$target" "lxc exec $container -- bash -c 'umask 077; f=/opt/star/secrets/planner_report_token; \
    if [ ! -s \$f ]; then python3 -c \"import secrets; print(secrets.token_hex(24))\" > \$f; chown star:star \$f; echo report token created; fi'"
  ssh -o BatchMode=yes "$target" "lxc exec $container -- tee /etc/systemd/system/star-planner.service >/dev/null" \
    < server/planner/star-planner.service
  ssh -o BatchMode=yes "$target" "lxc exec $container -- systemctl daemon-reload"
  if [ "$start" = 1 ]; then
    ssh -o BatchMode=yes "$target" "lxc exec $container -- bash -c 'systemctl enable star-planner >/dev/null 2>&1; systemctl restart star-planner; sleep 3; systemctl is-active star-planner'"
  fi
  exit 0
fi

target2="${STAR_SERVER2_SSH:?set STAR_SERVER2_SSH to user@address of brain 2s LXD host}"
target1="${STAR_SERVER_SSH:?set STAR_SERVER_SSH (the token is read from brain 1)}"
report_to="${STAR_PLANNER_REPORT_TO:?set STAR_PLANNER_REPORT_TO to http://<brain 1 container>:8098}"
echo "== brain 2: code (git HEAD $(git rev-parse --short HEAD))"
ship "$target2"
ssh -o BatchMode=yes "$target2" "lxc exec $container -- install -d -o star -g star -m 700 /opt/star/secrets"
# The token goes from brain 1 to brain 2 through this PC's pipes only; it is never printed.
ssh -o BatchMode=yes "$target1" "lxc exec $container -- cat /opt/star/secrets/planner_report_token" |
  ssh -o BatchMode=yes "$target2" "lxc exec $container -- bash -c 'umask 077; cat > /opt/star/secrets/planner_report_token; chown star:star /opt/star/secrets/planner_report_token'"
printf 'STAR_PLANNER_REPORT_TO=%s\n' "$report_to" |
  ssh -o BatchMode=yes "$target2" "lxc exec $container -- bash -c 'cat > /opt/star/planner/env; chown star:star /opt/star/planner/env'"
ssh -o BatchMode=yes "$target2" "lxc exec $container -- tee /etc/systemd/system/star-planner-agent.service >/dev/null" \
  < server/planner/star-planner-agent.service
ssh -o BatchMode=yes "$target2" "lxc exec $container -- systemctl daemon-reload"
if [ "$start" = 1 ]; then
  ssh -o BatchMode=yes "$target2" "lxc exec $container -- bash -c 'systemctl enable star-planner-agent >/dev/null 2>&1; systemctl restart star-planner-agent; sleep 3; systemctl is-active star-planner-agent'"
fi
