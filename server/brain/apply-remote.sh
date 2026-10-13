#!/bin/bash
# Remote half of apply.sh. Runs INSIDE the starai container as root; apply.sh pipes it in and sets MODE.
# Do not run it by hand. MODE = lock | unlock | check | apply | rollback | status
set -u
MODE=${MODE:-check}
STAGE=/opt/star/setup-proposed
CONF=/opt/star/config/models.ini
UNIT=/etc/systemd/system/star-brain.service
PRE=/opt/star/bin/star-brain-prestart.sh
BK_ROOT=/opt/star/config/backups
KEYFILE=/opt/star/secrets/api_keys
LOCK=/opt/star/lock
ROLE=apply
WAIT_READY_S=${WAIT_READY_S:-900}
export LD_LIBRARY_PATH=/opt/star/bin
say() { echo "[apply] $*"; }
die() { echo "[apply] ERROR: $*"; exit 1; }

lock_take() {
  until mkdir "$LOCK" 2>/dev/null; do
    grep -q "^$ROLE" "$LOCK/owner" 2>/dev/null && break
    if [ ! -f "$LOCK/owner" ] || [ $(( $(date +%s) - $(stat -c %Y "$LOCK/owner") )) -gt 1800 ]; then
      say "removing stale lock ($(cat "$LOCK/owner" 2>/dev/null))"; rm -rf "$LOCK"; continue
    fi
    say "server lock is held by: $(cat "$LOCK/owner" 2>/dev/null) - waiting 60 s"; sleep 60
  done
  echo "$ROLE $(date -u +%H:%M)" > "$LOCK/owner"
}
lock_touch() { grep -q "^$ROLE" "$LOCK/owner" 2>/dev/null && echo "$ROLE $(date -u +%H:%M)" > "$LOCK/owner"; }
lock_release() { grep -q "^$ROLE" "$LOCK/owner" 2>/dev/null && rm -rf "$LOCK"; }

# Models that models.ini expects under /opt/star/models but that still sit in the research download folder.
# Format: <source> <destination>. A move inside one filesystem is instant; an existing destination is left alone.
moves() {
  grep -E '^; *move:' "$STAGE/models.ini" | sed -E 's/^; *move: *//'
}
ini_paths() { grep -E '^(model|mmproj|model-draft) *=' "$1" | sed -E 's/^[a-z-]+ *= *//'; }

api() { curl -s -m 8 -H "Authorization: Bearer $(head -1 "$KEYFILE")" "http://127.0.0.1:8080$1"; }
model_states() {  # prints "<id> <status>" per model
  api /v1/models | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
for m in d.get("data", []):
    print(m.get("id"), (m.get("status") or {}).get("value"))'
}
startup_models() { # ids with load-on-startup = true in an ini file
  awk '/^\[/{sec=$0; gsub(/[\[\]]/,"",sec)} /^load-on-startup *= *true/{print sec}' "$1"
}
wait_ready() { # wait_ready <ini> : health ok and every load-on-startup model reports "loaded"
  local ini=$1 t=0 want st missing
  want=$(startup_models "$ini")
  while [ $t -lt "$WAIT_READY_S" ]; do
    if ! systemctl is-active --quiet star-brain; then
      if [ "$(systemctl is-failed star-brain)" = failed ]; then say "service entered failed state"; return 1; fi
    fi
    if curl -s -m 3 http://127.0.0.1:8080/health | grep -q '"ok"'; then
      st=$(model_states); missing=""
      for m in $want; do echo "$st" | grep -q "^$m loaded$" || missing="$missing $m"; done
      if [ -z "$missing" ]; then say "ready after about ${t}s: $(echo "$st" | tr '\n' ';')"; return 0; fi
      if echo "$st" | grep -q -E ' (failed|error)$'; then say "a model failed to load: $(echo "$st" | tr '\n' ';')"; return 1; fi
    fi
    sleep 5; t=$((t+5)); [ $((t % 60)) -eq 0 ] && { lock_touch; say "still loading (${t}s)"; }
  done
  say "not ready after ${WAIT_READY_S}s"; return 1
}
report() {
  say "per-model processes (threads from the command line, resident memory per NUMA node in MB):"
  for pid in $(pgrep -u star -f 'llama-server .*--alias'); do
    local a alias t tb
    a=$(tr '\0' ' ' < /proc/$pid/cmdline)
    alias=$(echo "$a" | sed -n 's/.*--alias \([^ ]*\).*/\1/p')
    t=$(echo "$a" | sed -n 's/.* --threads \([0-9]*\).*/\1/p'); tb=$(echo "$a" | sed -n 's/.*--threads-batch \([0-9]*\).*/\1/p')
    echo "  $alias: threads=${t:-default} threads-batch=${tb:-default} | $(numastat -p "$pid" 2>/dev/null | tail -1 | sed 's/Total *//' | awk '{printf "node0 %d  node1 %d  node2 %d  node3 %d  total %d", $1, $2, $3, $4, $5}')"
  done
  say "a model whose four node numbers differ by more than about 30% was loaded while a node was short of free memory;"
  say "restart the service (the pre-start step frees page cache) if that happens to star-fast."
}

preflight() {
  local bad=0 f k keys known
  for b in numactl numastat python3 curl; do command -v $b >/dev/null || { say "missing tool: $b"; bad=1; }; done
  for f in models.ini star-brain.service star-brain-prestart.sh; do [ -s "$STAGE/$f" ] || { say "staged file missing: $STAGE/$f"; bad=1; }; done
  [ $bad -eq 0 ] || return 1
  bash -n "$STAGE/star-brain-prestart.sh" || { say "prestart script has a syntax error"; bad=1; }
  # every model file must exist either at its final place or at the source of a pending move
  while read -r src dst; do
    [ -z "${src:-}" ] && continue
    [ -e "$dst" ] || [ -e "$src" ] || { say "neither $dst nor $src exists"; bad=1; }
  done < <(moves)
  for f in $(ini_paths "$STAGE/models.ini"); do
    [ -e "$f" ] || moves | awk '{print $2}' | grep -qx "$f" || { say "file referenced in models.ini does not exist: $f"; bad=1; }
  done
  # every key must be a llama-server long option (or one of the router-only preset keys)
  known=$(sudo -u star env LD_LIBRARY_PATH=/opt/star/bin /opt/star/bin/llama-server --help 2>&1 | grep -o -E -- '--[a-z][a-z0-9-]+' | sed 's/^--//' | sort -u)
  keys=$(grep -E '^[a-z][a-z0-9-]* *=' "$STAGE/models.ini" | sed -E 's/ *=.*//' | sort -u)
  for k in $keys; do
    case "$k" in version|load-on-startup|stop-timeout|dedup-cache-models|c) continue;; esac
    echo "$known" | grep -qx "$k" || { say "models.ini key is not a llama-server option: $k"; bad=1; }
  done
  local need_gb avail_gb
  need_gb=$(grep -E '^; *ram-gb:' "$STAGE/models.ini" | sed -E 's/[^0-9]//g' | head -1); need_gb=${need_gb:-60}
  avail_gb=$(awk '/MemTotal/{print int($2/1048576)}' /proc/meminfo)
  [ "$avail_gb" -ge "$need_gb" ] || { say "only ${avail_gb} GB RAM, the fleet needs about ${need_gb} GB"; bad=1; }
  [ $bad -eq 0 ] && say "pre-flight ok (files present, keys valid, ${avail_gb} GB RAM for a ${need_gb} GB fleet)"
  return $bad
}

do_rollback() { # do_rollback [stamp]
  local stamp=${1:-$(cat "$BK_ROOT/LATEST" 2>/dev/null)}
  [ -n "$stamp" ] && [ -d "$BK_ROOT/$stamp" ] || die "no backup to roll back to under $BK_ROOT"
  say "rolling back to backup $stamp"
  cp -p "$BK_ROOT/$stamp/models.ini" "$CONF"
  cp -p "$BK_ROOT/$stamp/star-brain.service" "$UNIT"
  if [ -f "$BK_ROOT/$stamp/star-brain-prestart.sh" ]; then cp -p "$BK_ROOT/$stamp/star-brain-prestart.sh" "$PRE"; else rm -f "$PRE"; fi
  systemctl daemon-reload
  systemctl restart star-brain
  if wait_ready "$CONF"; then say "rollback complete: the previous configuration is serving again"; else say "ROLLBACK DID NOT COME UP: check 'journalctl -u star-brain -n 80'"; return 1; fi
}

case "$MODE" in
  lock)    lock_take; say "server lock taken ($(cat $LOCK/owner))";;
  unlock)  lock_release; say "server lock released";;
  status)  systemctl is-active star-brain; model_states; report;;
  check)   preflight || exit 1;;
  rollback) lock_take; do_rollback "${STAMP:-}"; rc=$?; report; exit $rc;;
  apply)
    lock_take
    preflight || die "pre-flight failed, nothing was changed"
    stamp=$(date -u +%Y%m%d-%H%M%S)
    mkdir -p "$BK_ROOT/$stamp"
    cp -p "$CONF" "$BK_ROOT/$stamp/models.ini"
    cp -p "$UNIT" "$BK_ROOT/$stamp/star-brain.service"
    [ -f "$PRE" ] && cp -p "$PRE" "$BK_ROOT/$stamp/star-brain-prestart.sh"
    echo "$stamp" > "$BK_ROOT/LATEST"
    say "backup written to $BK_ROOT/$stamp"
    while read -r src dst; do
      [ -z "${src:-}" ] && continue
      if [ -e "$dst" ]; then continue; fi
      mkdir -p "$(dirname "$dst")" && mv "$src" "$dst" && say "moved $(basename "$src") into $(dirname "$dst")"
    done < <(moves)
    install -o star -g star -m 644 "$STAGE/models.ini" "$CONF"
    install -o star -g star -m 755 "$STAGE/star-brain-prestart.sh" "$PRE"
    install -o root -g root -m 644 "$STAGE/star-brain.service" "$UNIT"
    chown -R star:star /opt/star/models
    systemctl daemon-reload
    say "restarting star-brain (the brain is unavailable for one to three minutes)"
    systemctl restart star-brain
    if wait_ready "$CONF"; then
      report
      say "APPLIED. Backup id: $stamp. To undo: bash apply.sh rollback"
    else
      journalctl -u star-brain -n 25 --no-pager 2>/dev/null | cut -c1-220
      say "the new configuration did not come up: rolling back automatically"
      do_rollback "$stamp"
      exit 1
    fi
    ;;
  *) die "unknown MODE $MODE";;
esac
