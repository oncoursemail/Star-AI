#!/bin/bash
# STAR Blender Lab on brain 2 (inside the STAR container, as user star). On demand, never 24/7.
#
#   blender-lab.sh status            one JSON line: running?, Lab MCP port open?, memory, Studios, caps
#   blender-lab.sh start [file.blend]  start the Blender GUI on the virtual display with the official Blender Lab
#                                    MCP add-on bound to 127.0.0.1:9876. Refuses below the memory floor. Runs as a
#                                    transient user unit (MemoryMax, no swap, RuntimeMaxSec) so it can
#                                    never push the Studios into out-of-memory.
#   blender-lab.sh stop              stop it (always do this when STAR is done)
#   blender-lab.sh mcp-server        the Lab MCP server as an MCP stdio server (stdin/stdout = JSON-RPC), talking to
#                                    127.0.0.1:9876. From another machine:
#                                    ssh <host> lxc exec <container> -- sudo -u <user> -H <bin>/blender-lab.sh mcp-server
#   blender-lab.sh shot <name> [x y w h]  PNG of the Blender window (what a person sees), optional crop -> sandbox/shots/<name>.png
#   blender-lab.sh fetch <rel>       write a file of the sandbox folder to stdout (size limit 24 MB, no symlinks)
#   blender-lab.sh list              list the sandbox folder (relative names, sizes)
#
# SECURITY. The Lab add-on executes whatever Python it is sent, with no guard. So: it listens on 127.0.0.1 only, only
# while the GUI runs, the GUI runs only on request and dies after RuntimeMaxSec (default 30 min), memory is capped,
# the sandbox folder is the only place STAR's wrappers write, and the exposure to STAR (star/blender_brain2.py) is
# settings-gated and allow-listed. Anything running as user star inside this container can still reach the port
# while Blender is up: do not run untrusted programs in the container meanwhile.
#
# Exit codes: 2 usage, 3 Blender or the add-on missing, 4 already running / not running, 5 memory floor, 6 Lab MCP
# port did not open, 7 bad file name.
set -u
LAB=${BLENDER_LAB_HOME:-$HOME/blender-lab}
SANDBOX=$LAB/sandbox
UNIT=star-blender
DISP=${BLENDER_LAB_DISPLAY:-:1}
PORT=${BLENDER_LAB_PORT:-9876}
MEM_MAX=${BLENDER_LAB_MEM_MAX:-2560M}
# MemoryHigh is off by default: without swap it throttles the process into an endless stall instead of failing.
MEM_HIGH=${BLENDER_LAB_MEM_HIGH:-}
MIN_AVAILABLE_MB=${BLENDER_LAB_MIN_MB:-3000}
RUNTIME_MAX=${BLENDER_LAB_RUNTIME_MAX:-1800}
BLENDER=${BLENDER_PATH:-/opt/blender/blender}
LOG=$LAB/logs/blender-lab.log
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
mkdir -p "$LAB/logs" "$SANDBOX/shots" 2>/dev/null

say() { echo "$(date -u +%FT%TZ) $*" >> "$LOG"; }
refuse() { say "refused: $2"; echo "blender-lab: $2" >&2; exit "$1"; }
available_mb() { awk '/^MemAvailable:/{print int($2/1024)}' /proc/meminfo; }
unit_active() { systemctl --user is-active --quiet "$UNIT.service"; }
port_open() { (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; }
studios() { pgrep -fc '^/.*/RobloxStudioBeta.exe roblox-studio' 2>/dev/null || true; }
# A relative sandbox name: letters, digits, dot, dash, underscore, one level of folder at most.
valid_rel() { [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,79}(/[A-Za-z0-9][A-Za-z0-9._-]{0,79})?$ ]] && [[ "$1" != *..* ]]; }

cmd=${1:-}; shift || true
case "$cmd" in
status)
  running=false; unit_active && running=true
  mcp=false; port_open && mcp=true
  rss=0
  if $running; then rss=$(( $(systemctl --user show "$UNIT.service" -p MemoryCurrent --value 2>/dev/null | grep -E '^[0-9]+$' || echo 0) / 1048576 )); fi
  printf '{"running":%s,"mcp_port_open":%s,"display":"%s","port":%s,"available_mb":%s,"min_available_mb":%s,"blender_mb":%s,"mem_max":"%s","studios":%s,"runtime_max_s":%s,"blender":"%s"}\n' \
    "$running" "$mcp" "$DISP" "$PORT" "$(available_mb)" "$MIN_AVAILABLE_MB" "$rss" "$MEM_MAX" "$(studios)" "$RUNTIME_MAX" \
    "$([ -x "$BLENDER" ] && "$BLENDER" --version 2>/dev/null | head -1 | tr -d '"' || echo missing)"
  ;;
start)
  [ -x "$BLENDER" ] || refuse 3 "Blender not found at $BLENDER"
  [ -d "$HOME/.config/blender/5.2/extensions/user_default/mcp" ] || refuse 3 "the Blender Lab MCP add-on is not installed (see server/brain2_blender/07-container-blender.sh)"
  unit_active && refuse 4 "already running (blender-lab.sh stop first)"
  avail=$(available_mb)
  [ "$avail" -ge "$MIN_AVAILABLE_MB" ] || refuse 5 "only $avail MB available, need $MIN_AVAILABLE_MB MB (the Studios come first); nothing started"
  file=""
  if [ -n "${1:-}" ]; then
    valid_rel "$1" || refuse 7 "bad scene name"
    file=$SANDBOX/$1
    [ -f "$file" ] || refuse 7 "no such scene in the sandbox"
  fi
  t0=$(date +%s.%N)
  systemd-run --user --unit="$UNIT" --collect -q \
    -p MemoryMax="$MEM_MAX" ${MEM_HIGH:+-p MemoryHigh="$MEM_HIGH"} -p MemorySwapMax=0 -p RuntimeMaxSec="$RUNTIME_MAX" \
    -p Nice=5 -p CPUWeight=50 \
    --setenv=DISPLAY="$DISP" --setenv=BLENDER_LAB_PORT="$PORT" --setenv=BLENDER_LAB_SANDBOX="$SANDBOX" \
    "$BLENDER" --online-mode --factory-startup --python "$LAB/startup.py" ${file:+"$file"} \
    >/dev/null 2>&1 || refuse 4 "systemd-run failed"
  say "start unit (avail ${avail} MB, cap $MEM_MAX, display $DISP) scene=${file:-none}"
  for i in $(seq 1 300); do
    port_open && break
    unit_active || { say "unit died during start"; refuse 6 "Blender exited during start (see journalctl --user -u $UNIT)"; }
    sleep 0.1
  done
  port_open || { systemctl --user stop "$UNIT.service" 2>/dev/null; refuse 6 "Lab MCP port $PORT did not open in 30 s; stopped"; }
  t1=$(date +%s.%N)
  printf '{"started":true,"mcp_port":%s,"display":"%s","seconds_to_mcp":%.2f,"available_mb_before":%s}\n' "$PORT" "$DISP" "$(echo "$t1 - $t0" | bc)" "$avail"
  ;;
stop)
  unit_active || { echo '{"stopped":false,"was_running":false}'; exit 0; }
  systemctl --user stop "$UNIT.service"; say "stop"
  echo '{"stopped":true,"was_running":true}'
  ;;
mcp-server)
  [ -x "$LAB/venv/bin/python" ] && [ -d "$LAB/mcp/blmcp" ] || refuse 3 "the Lab MCP server is not installed (see server/brain2_blender/07-container-blender.sh)"
  cd "$LAB/mcp" || refuse 3 "no lab folder"
  say "mcp-server session"
  # stdout is the MCP stream: nothing else may print there. Never reaches anything but 127.0.0.1.
  BLENDER_MCP_HOST=127.0.0.1 BLENDER_MCP_PORT="$PORT" BLENDER_PATH="$BLENDER" PYTHONPATH="$LAB/mcp" \
    exec "$LAB/venv/bin/python" -m blmcp --transport stdio 2>>"$LAB/logs/mcp-server.err"
  ;;
shot)
  # shot <name> [x y w h]: PNG of the Blender window (what a person sees), optionally cropped to a rectangle given in
  # window pixels (STAR uses this to cut the 3D viewport out; the add-on's own screenshot tools return black here).
  valid_rel "${1:-}" && [[ "$1" != */* ]] || refuse 7 "bad shot name"
  out=$SANDBOX/shots/${1%.png}.png
  [ $# -eq 1 ] || [ $# -eq 5 ] || refuse 2 "usage: shot <name> [x y w h]"
  export DISPLAY=$DISP
  win=$(xdotool search --name "Blender 5" 2>/dev/null | head -1)
  [ -n "$win" ] || refuse 6 "no Blender window on $DISP"
  # The Studios share this display and have no compositor: a Studio window above Blender would be in the picture.
  xdotool windowraise "$win" 2>/dev/null; sleep 0.3
  if [ $# -ge 5 ]; then
    for v in "$2" "$3" "$4" "$5"; do [[ "$v" =~ ^[0-9]{1,4}$ ]] || refuse 7 "bad crop"; done
    import -window "$win" png:- 2>/dev/null | convert png:- -crop "${4}x${5}+${2}+${3}" +repage "$out" || refuse 6 "screenshot failed"
  else
    import -window "$win" "$out" 2>/dev/null || refuse 6 "screenshot failed"
  fi
  printf '{"path":"shots/%s","bytes":%s}
' "$(basename "$out")" "$(stat -c %s "$out")"
  ;;
fetch)
  valid_rel "${1:-}" || refuse 7 "bad file name"
  f=$SANDBOX/$1
  [ -f "$f" ] && [ ! -L "$f" ] || refuse 7 "no such file in the sandbox"
  [ "$(stat -c %s "$f")" -le 25165824 ] || refuse 7 "file larger than 24 MB"
  cat "$f"
  ;;
list)
  (cd "$SANDBOX" && find . -maxdepth 2 -type f ! -type l -printf '%P\t%s\n' | sort | head -200)
  ;;
*)
  sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//' >&2
  exit 2
  ;;
esac
