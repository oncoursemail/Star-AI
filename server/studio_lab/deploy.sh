#!/usr/bin/env bash
# Install or update the STAR Studio Lab nightly on the Studio machine (brain 2) container. Run from the repository
# root on the PC:
#
#   STAR_STUDIO_SSH=<user@address of the Studio machine's LXD host> bash server/studio_lab/deploy.sh [--enable] [--status] [--run-now]
#
#   (no option)  copy the code (git HEAD: star/, server/studio_lab/) to /opt/star/studio-lab/app, write the lab home
#                (connector command = the local studio-mcp-multi.sh), install the user units; the timer is NOT enabled
#   --enable     also enable and start the timer (03:30 UTC nightly)
#   --run-now    start one nightly run now (systemctl --user start; returns when it has finished)
#   --status     timer/service state and the last log lines
#
# Needs on the Studio machine: the star user's Studio scripts in /home/star/bin (studio-extra.sh, studio-mcp-multi.sh,
# studio-dialog-guard.sh; project folder server/setup/server2/bin) and the Python dependencies of star.studio_lab
# (mcp, anyio, jsonschema, pydantic) in /opt/star/studio-lab/site-packages (copied from the night-school venv, same
# Python 3.12). The address is operator configuration and is never stored in the repository.
set -euo pipefail
target="${STAR_STUDIO_SSH:?set STAR_STUDIO_SSH to user@address of the Studio machine LXD host}"
container="${STAR_LXC_CONTAINER:-starai}"
lab=/opt/star/studio-lab
enable=0 status=0 run_now=0
for arg in "$@"; do
  case "$arg" in --enable) enable=1;; --status) status=1;; --run-now) run_now=1;; *) echo "unknown option $arg" >&2; exit 2;; esac
done
# Every command runs in a bash INSIDE the container (printf %q keeps the LXD host's shell from expanding it).
remote() { ssh -o BatchMode=yes -o ConnectTimeout=15 "$target" "lxc exec $container -- bash -c $(printf '%q' "$*")"; }
user_ctl() { remote "runuser -u star -- env XDG_RUNTIME_DIR=/run/user/\$(id -u star) systemctl --user $*"; }
if [ "$status" = 1 ]; then
  user_ctl "list-timers star-studio-lab-nightly.timer --no-pager" || true
  user_ctl "status star-studio-lab-nightly.service --no-pager -n 0" || true
  remote "tail -n 15 /home/star/log/studio-lab-nightly.log" || true
  exit 0
fi
root="$(git rev-parse --show-toplevel)"; cd "$root"
echo "== code (git HEAD $(git rev-parse --short HEAD))"
remote "install -d -o star -g star $lab $lab/app $lab/home $lab/home/studio $lab/evidence /opt/star/learning /opt/star/learning/outbox"
remote "chown star:star /opt/star/learning /opt/star/learning/outbox"
remote "rm -rf $lab/app/star $lab/app/server"
git archive HEAD star server/studio_lab | ssh -o BatchMode=yes "$target" "lxc exec $container -- runuser -u star -- tar -x -C $lab/app"
# STAR's own Roblox account id (not a secret; the Open Cloud key stays on the PC): from STAR_LAB_OWN_ACCOUNT or the
# PC lab home's last key check. The Studio machine's lab only edits STAR Test Place or a blank place either way.
account="${STAR_LAB_OWN_ACCOUNT:-$("${STAR_PYTHON:-python}" -c 'import json,os,sys
p=os.path.expanduser("~/.star/roblox-lab-home/roblox/access.json")
try: print(int(json.load(open(p))["last_check"]["account"]["user_id"]))
except Exception: print("")' 2>/dev/null)}"
case "$account" in ''|*[!0-9]*) account_json="";; *) account_json=", \"own_account_id\": $account";; esac
echo "{\"command\": [\"/home/star/bin/studio-mcp-multi.sh\"]$account_json}" |
  ssh -o BatchMode=yes "$target" "lxc exec $container -- runuser -u star -- tee $lab/home/studio/lab-multi.json >/dev/null"
remote "cd /tmp && runuser -u star -- env PYTHONPATH=$lab/app:$lab/site-packages python3 -c 'import star.studio_lab, star.studio_lab_parallel, mcp; print(\"imports ok\")'"
echo "== user units"
remote "runuser -u star -- install -d /home/star/.config/systemd/user"
for unit in star-studio-lab-nightly.service star-studio-lab-nightly.timer; do
  remote "runuser -u star -- cp $lab/app/server/studio_lab/$unit /home/star/.config/systemd/user/$unit"
done
user_ctl "daemon-reload"
[ "$enable" = 1 ] && user_ctl "enable --now star-studio-lab-nightly.timer"
user_ctl "list-timers star-studio-lab-nightly.timer --no-pager" || true
if [ "$run_now" = 1 ]; then
  echo "== one nightly run now"
  user_ctl "start star-studio-lab-nightly.service" || true
  remote "tail -n 25 /home/star/log/studio-lab-nightly.log"
fi
