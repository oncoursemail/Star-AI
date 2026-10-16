#!/usr/bin/env bash
# Install or update STAR playtest learning on the Studio machine (brain 2) container. From the repository root on the PC:
#
#   STAR_STUDIO_SSH=<user@address of the Studio machine's LXD host> bash server/studio_lab/playtest-learning-deploy.sh [option]
#
#   (no option)  copy the code (git HEAD: star/, server/studio_lab/) to /opt/star/playtest/app, write brain.env
#                (brain 1's address taken from the night-school env already on the machine; key file path only),
#                install the user units; the switch stays as it is (new install: OFF), the timer is not enabled
#   --enable     switch ON (switch.env) and enable the timer (05:15 UTC daily)
#   --disable    switch OFF and disable the timer
#   --run-now    start one run now in the background (systemctl --user start --no-block)
#   --status     timer/service state and the last log lines
#
# Uses the Studio Lab's Python dependencies (/opt/star/studio-lab/site-packages) and lab home (connector command).
set -euo pipefail
target="${STAR_STUDIO_SSH:?set STAR_STUDIO_SSH to user@address of the Studio machine LXD host}"
container="${STAR_LXC_CONTAINER:-starai}"
pt=/opt/star/playtest
action="${1:-}"
remote() { ssh -o BatchMode=yes -o ConnectTimeout=15 "$target" "lxc exec $container -- bash -c $(printf '%q' "$*")"; }
user_ctl() { remote "runuser -u star -- env XDG_RUNTIME_DIR=/run/user/\$(id -u star) systemctl --user $*"; }
case "$action" in
  --status)
    user_ctl "list-timers star-playtest-learning.timer --no-pager" || true
    user_ctl "status star-playtest-learning.service --no-pager -n 0" || true
    remote "cat $pt/switch.env 2>/dev/null; tail -n 15 /home/star/log/playtest-learning.log 2>/dev/null" || true
    exit 0;;
  --enable)
    remote "echo STAR_PLAYTEST_LEARNING=1 | runuser -u star -- tee $pt/switch.env >/dev/null"
    user_ctl "enable --now star-playtest-learning.timer"; exit 0;;
  --disable)
    remote "echo STAR_PLAYTEST_LEARNING=0 | runuser -u star -- tee $pt/switch.env >/dev/null"
    user_ctl "disable --now star-playtest-learning.timer" || true; exit 0;;
  --run-now)
    user_ctl "start --no-block star-playtest-learning.service"; exit 0;;
  '') ;;
  *) echo "unknown option $action" >&2; exit 2;;
esac
root="$(git rev-parse --show-toplevel)"; cd "$root"
echo "== code (git HEAD $(git rev-parse --short HEAD))"
remote "install -d -o star -g star $pt $pt/app $pt/evidence"
remote "rm -rf $pt/app/star $pt/app/server"
git archive HEAD star server/studio_lab | ssh -o BatchMode=yes "$target" "lxc exec $container -- runuser -u star -- tar -x -C $pt/app"
# brain 1's chat endpoint = the knowledge service's host on the brain port; the key stays in the night-school file.
remote "url=\$(sed -n 's,^STAR_NS_KNOWLEDGE_URL=\(http://[^:/]*\).*,\1:8080,p' /opt/star/learning/env | head -1);
  [ -n \"\$url\" ] || { echo 'no STAR_NS_KNOWLEDGE_URL in /opt/star/learning/env' >&2; exit 1; }
  printf 'STAR_PLAYTEST_BRAIN_URL=%s\nSTAR_PLAYTEST_KEY_FILE=/opt/star/learning/secrets/api_keys\nSTAR_PLAYTEST_MODEL=star-fast\n' \"\$url\" |
  runuser -u star -- tee $pt/brain.env >/dev/null; chmod 600 $pt/brain.env"
remote "[ -f $pt/switch.env ] || echo STAR_PLAYTEST_LEARNING=0 | runuser -u star -- tee $pt/switch.env >/dev/null"
remote "cd /tmp && runuser -u star -- env PYTHONPATH=$pt/app:/opt/star/studio-lab/site-packages python3 -m star.playtest_learning check $pt/app/server/studio_lab/playtest/specs"
echo "== user units"
for unit in star-playtest-learning.service star-playtest-learning.timer; do
  remote "runuser -u star -- cp $pt/app/server/studio_lab/$unit /home/star/.config/systemd/user/$unit"
done
user_ctl "daemon-reload"
user_ctl "list-timers star-playtest-learning.timer --no-pager" || true
