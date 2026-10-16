#!/bin/bash
# STAR open Roblox benchmark: the Studio part, on the Studio machine (brain 2) as the user `star`.
#
#   roblox-bench.sh <answers dir> <out dir> [models] [only]
#
# models default "reference,star-fast,star-deep,star-quick"; only = comma-separated task ids (default all).
# Never overlaps the Studio Lab nightly or playtest learning, waits while the quiet lock exists (<= 30 min),
# starts the connector host (as the Studio Lab nightly does), runs `python3 -m star.roblox_benchmark run` against
# the ONE primary Studio (STAR Test Place, guarded path), and always stops the connector host again.
# The answers come from `python3 -m star.roblox_benchmark answers` (brain only; can run anywhere).
set -u
APP=${ROBLOX_BENCH_APP:-/opt/star/roblox-bench/app}
LAB=${STUDIO_LAB_HOME:-/opt/star/studio-lab}
ANSWERS=${1:?answers dir}; OUT=${2:?out dir}; MODELS=${3:-reference,star-fast,star-deep,star-quick}; ONLY=${4:-}
export XDG_RUNTIME_DIR=/run/user/$(id -u) DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus
say() { echo "$(date -u +%FT%TZ) $*"; }
for unit in star-studio-lab-nightly.service star-playtest-learning.service; do
  if systemctl --user is-active --quiet "$unit"; then say "$unit is running: not starting"; exit 3; fi
done
waited=0
while [ -e /opt/star/lock ]; do
  [ "$waited" -ge 1800 ] && { say "quiet lock held for 30 min: not starting"; exit 3; }
  sleep 30; waited=$((waited + 30))
done
cleanup() { systemctl --user stop star-studio-mcp-host 2>/dev/null; say "cleanup: connector host stopped"; }
trap cleanup EXIT
systemctl --user stop star-studio-mcp-host 2>/dev/null
systemd-run --user --unit=star-studio-mcp-host --quiet \
  bash -c 'sleep infinity | STUDIO_MCP_NOLOCK=1 /home/star/bin/studio-mcp-multi.sh >/dev/null' || say "connector host did not start"
sleep 20
cd "$APP" && PYTHONPATH="$APP:$LAB/site-packages" nice -n 5 python3 -m star.roblox_benchmark run \
  --answers "$ANSWERS" --out "$OUT" --home "$LAB/home" --models "$MODELS" ${ONLY:+--only "$ONLY"}
rc=$?
say "benchmark finished rc=$rc"
exit $rc
