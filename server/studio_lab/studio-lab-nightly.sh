#!/bin/bash
# STAR Studio Lab nightly run on the Studio machine (brain 2), as the user `star` (systemd user unit
# star-studio-lab-nightly.service, started by star-studio-lab-nightly.timer).
#
#   1. waits while the quiet lock /opt/star/lock exists (timing runs; at most STUDIO_LAB_LOCK_WAIT_S, then skips);
#   2. starts up to STUDIO_LAB_STUDIOS-1 extra Studios (studio-extra.sh: inside the primary's sandbox, no WebView,
#      Auto Recovery dialog answered Ignore), but only while MemAvailable stays above the floor;
#   3. starts one long-lived connector host (all Studios attach to it), then
#      `python -m star.studio_lab nightly <specs> --studios N --rotate K --max-minutes M` (resource-planner admission
#      per spec when the planner is configured, fail-open), evidence under $LAB/evidence, lesson candidates to the
#      night-school outbox ($STAR_NS_HOME/outbox/studio-lab, all CANDIDATES for owner review);
#   4. always stops the extra Studios and the connector host again (STAR's normal path needs exactly one Studio).
#
# Settings (environment, e.g. a drop-in of the service): STUDIO_LAB_STUDIOS (cap, default 2), STUDIO_LAB_ROTATE
# (specs per night, default 16), STUDIO_LAB_MAX_MINUTES (default 45), STUDIO_LAB_KEEP (evidence folders, default 14).
set -u
LAB=${STUDIO_LAB_HOME:-/opt/star/studio-lab}
NS_HOME=${STAR_NS_HOME:-/opt/star/learning}
STUDIOS=${STUDIO_LAB_STUDIOS:-2}; ROTATE=${STUDIO_LAB_ROTATE:-16}; MINUTES=${STUDIO_LAB_MAX_MINUTES:-45}
KEEP=${STUDIO_LAB_KEEP:-14}; LOCK_WAIT=${STUDIO_LAB_LOCK_WAIT_S:-1800}
FLOOR_MB=${STUDIO_LAB_FLOOR_MB:-3300}           # MemAvailable needed before each extra Studio (+2.4 GB each)
LOG="$HOME/log/studio-lab-nightly.log"; mkdir -p "$HOME/log" "$LAB/evidence" "$NS_HOME/outbox/studio-lab"
export XDG_RUNTIME_DIR=/run/user/$(id -u) DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus
say() { echo "$(date -u +%FT%TZ) $*" | tee -a "$LOG"; }
case "$STUDIOS" in 1|2|3) ;; *) say "STUDIO_LAB_STUDIOS must be 1..3"; exit 2;; esac

cleanup() {
  /home/star/bin/studio-extra.sh stop all >/dev/null 2>&1
  systemctl --user stop star-studio-mcp-host 2>/dev/null
  say "cleanup: extra Studios stopped, connector host stopped"
}
trap cleanup EXIT

waited=0
while [ -e /opt/star/lock ]; do
  [ "$waited" -ge "$LOCK_WAIT" ] && { say "quiet lock held for ${LOCK_WAIT}s: skipping tonight"; exit 0; }
  sleep 30; waited=$((waited + 30))
done
/home/star/bin/studio-extra.sh list >/dev/null 2>&1 || true
[ "$(/home/star/bin/studio-extra.sh list | grep -c '^slot=1 ')" = 1 ] || { say "no primary Studio: skipping"; exit 0; }

have=1
for slot in $(seq 2 "$STUDIOS"); do
  avail=$(awk '/^MemAvailable:/{print int($2/1024)}' /proc/meminfo)
  if [ "$avail" -lt "$FLOOR_MB" ]; then say "only ${avail} MB available: staying at $have Studio(s)"; break; fi
  if STUDIO_EXTRA_GUARD_WAIT= /home/star/bin/studio-extra.sh start "$slot" test >> "$LOG" 2>&1; then have=$slot
  else say "slot $slot did not start: staying at $have Studio(s)"; break; fi
done
[ "$have" -gt 1 ] && sleep 45                       # extra Studios load the place; the dialog guard runs meanwhile
systemctl --user stop star-studio-mcp-host 2>/dev/null
systemd-run --user --unit=star-studio-mcp-host --quiet \
  bash -c 'sleep infinity | STUDIO_MCP_NOLOCK=1 /home/star/bin/studio-mcp-multi.sh >/dev/null' || say "connector host did not start"
sleep 5
say "nightly: $have Studio(s), rotate $ROTATE, cap ${MINUTES} min"
cd "$LAB/app" && PYTHONPATH="$LAB/app:$LAB/site-packages" timeout --signal=INT $(( MINUTES * 60 + 300 )) \
  nice -n 5 python3 -m star.studio_lab nightly "$LAB/app/star/studio_lab_specs" --home "$LAB/home" \
  --out "$LAB/evidence" --outbox "$NS_HOME/outbox/studio-lab" --studios "$have" --rotate "$ROTATE" \
  --max-minutes "$MINUTES" --keep "$KEEP" >> "$LOG" 2>&1
rc=$?
say "nightly finished rc=$rc"
exit $rc
