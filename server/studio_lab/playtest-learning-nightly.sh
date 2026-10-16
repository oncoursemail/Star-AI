#!/bin/bash
# STAR playtest learning, unattended run on the Studio machine (brain 2), as the user `star`
# (systemd user unit star-playtest-learning.service, started by star-playtest-learning.timer).
#
#   0. switch: does nothing unless STAR_PLAYTEST_LEARNING=1 (deploy writes it to $PT/switch.env with --enable);
#   1. never overlaps the Studio Lab nightly (skips while its service runs) and waits while the quiet lock exists;
#   2. starts the connector host (as the Studio Lab nightly does) and runs
#      `python -m star.playtest_learning run <specs> --home <lab home> --outbox $NS_HOME/outbox/playtest`:
#      STAR (brain 1's star-fast) writes each game, the robot plays it in the ONE primary Studio, failures go back
#      to STAR as fix tasks, re-playtest; evidence under $PT/evidence, candidates in the night-school outbox;
#   3. always stops the connector host again.
set -u
PT=${PLAYTEST_HOME:-/opt/star/playtest}
LAB=${STUDIO_LAB_HOME:-/opt/star/studio-lab}
NS_HOME=${STAR_NS_HOME:-/opt/star/learning}
MINUTES=${PLAYTEST_MAX_MINUTES:-150}; LOCK_WAIT=${PLAYTEST_LOCK_WAIT_S:-1800}; KEEP=${PLAYTEST_KEEP:-14}
LOG="$HOME/log/playtest-learning.log"; mkdir -p "$HOME/log" "$PT/evidence" "$NS_HOME/outbox/playtest"
export XDG_RUNTIME_DIR=/run/user/$(id -u) DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus
say() { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }
[ -f "$PT/switch.env" ] && . "$PT/switch.env"
[ -f "$PT/brain.env" ] && . "$PT/brain.env"
export STAR_PLAYTEST_LEARNING STAR_PLAYTEST_BRAIN_URL STAR_PLAYTEST_KEY_FILE STAR_PLAYTEST_MODEL 2>/dev/null
[ "${STAR_PLAYTEST_LEARNING:-}" = 1 ] || { say "switched off ($PT/switch.env): nothing to do"; exit 0; }
if systemctl --user is-active --quiet star-studio-lab-nightly.service; then
  say "Studio Lab nightly is running: skipping"; exit 0
fi
waited=0
while [ -e /opt/star/lock ]; do
  [ "$waited" -ge "$LOCK_WAIT" ] && { say "quiet lock held for ${LOCK_WAIT}s: skipping"; exit 0; }
  sleep 30; waited=$((waited + 30))
done
cleanup() { systemctl --user stop star-studio-mcp-host 2>/dev/null; say "cleanup: connector host stopped"; }
trap cleanup EXIT
systemctl --user stop star-studio-mcp-host 2>/dev/null
systemd-run --user --unit=star-studio-mcp-host --quiet \
  bash -c 'sleep infinity | STUDIO_MCP_NOLOCK=1 /home/star/bin/studio-mcp-multi.sh >/dev/null' || say "connector host did not start"
sleep 20
say "playtest learning: cap ${MINUTES} min"
cd "$PT/app" && PYTHONPATH="$PT/app:$LAB/site-packages" timeout --signal=INT $(( MINUTES * 60 + 900 )) \
  nice -n 5 python3 -m star.playtest_learning run "$PT/app/star/playtest_specs" --home "$LAB/home" \
  --out "$PT/evidence" --outbox "$NS_HOME/outbox/playtest" --max-minutes "$MINUTES" >> "$LOG" 2>&1
rc=$?
# keep the newest $KEEP evidence folders
ls -1d "$PT"/evidence/playtest-* 2>/dev/null | sort | head -n -"$KEEP" | while read -r old; do rm -rf -- "$old"; done
say "playtest learning finished rc=$rc"
exit $rc
