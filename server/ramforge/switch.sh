#!/bin/bash
# Opt-in switch for the RAMForge NUMA-local build on the live brain (server 1, run as root INSIDE the starai container).
# It never restarts anything: after `on` or `off`, restart star-brain yourself in a quiet window.
#
#   switch.sh install   copy the RAMForge build (build.sh output) to /opt/star/bin-ramforge (live /opt/star/bin untouched)
#   switch.sh on        write the star-brain drop-in: same ExecStart, but the RAMForge binary + GGML_NUMA_BLOCK=1 and
#                       LLAMA_RAMFORGE_PLACE=1 (thread k on node k*4/n, weights bound to the node whose threads read them)
#   switch.sh off       remove the drop-in (back to the live b11541 binary and default placement)
#   switch.sh status    drop-in present?, which binary the running star-fast uses, its RAMForge env, last placement line
#
# The router starts every model from its own binary (/proc/self/exe) with its own environment, so the drop-in applies
# to all models. Placement only moves pages (results are bit-identical); unset variables = stock b11541 behaviour.
set -euo pipefail
SRC=${SRC:-/opt/star/src/llama.cpp-ramforge/build/bin}
DST=${DST:-/opt/star/bin-ramforge}
UNIT=star-brain
DROPDIR=${DROPDIR:-/etc/systemd/system/$UNIT.service.d}   # override only for a dry test
DROP=$DROPDIR/ramforge.conf

case "${1:-}" in
  install)
    [ -x "$SRC/llama-server" ] || { echo "no build at $SRC (run build.sh as user star first)"; exit 1; }
    mkdir -p "$DST"
    cp -a "$SRC"/llama-server "$SRC"/lib*.so* "$DST"/
    chown -R star:star "$DST"
    LD_LIBRARY_PATH=$DST ldd "$DST/llama-server" | grep -E "llama|ggml|mtmd" | grep -v "$DST" && { echo "a library resolves outside $DST"; exit 1; }
    LD_LIBRARY_PATH=$DST ldd "$DST/libllama-server-impl.so" | grep -E "llama|ggml|mtmd" | grep -v "$DST" && { echo "a library resolves outside $DST"; exit 1; }
    echo "installed to $DST (libraries resolve inside it)" ;;
  on)
    [ -x "$DST/llama-server" ] || { echo "run '$0 install' first"; exit 1; }
    frag=$(systemctl show -p FragmentPath --value $UNIT)
    # ExecStart of the live unit, continuation lines joined, with only the binary path swapped (no address is copied
    # into the repo: it is read from the installed unit at run time).
    exec_line=$(awk '/^ExecStart=/{f=1} f{l=$0; c=(l ~ /\\[[:space:]]*$/); sub(/\\[[:space:]]*$/, "", l); printf "%s", l; if (!c) exit}' "$frag" \
                | sed 's#^ExecStart=##')
    case "$exec_line" in *"/opt/star/bin/llama-server"*) ;; *) echo "ExecStart does not use /opt/star/bin/llama-server; refusing"; exit 1 ;; esac
    new=${exec_line//\/opt\/star\/bin\/llama-server/$DST/llama-server}
    mkdir -p "$DROPDIR"
    cat > "$DROP" <<EOF
# RAMForge NUMA-local placement (server/ramforge/switch.sh). Remove with: switch.sh off
[Service]
Environment=LD_LIBRARY_PATH=$DST
Environment=GGML_NUMA_BLOCK=1
Environment=LLAMA_RAMFORGE_PLACE=1
ExecStart=
ExecStart=$new
EOF
    systemctl daemon-reload
    echo "drop-in written: $DROP"; echo "NOT restarted. Apply in a quiet window: systemctl restart $UNIT" ;;
  off)
    rm -f "$DROP"; rmdir "$DROPDIR" 2>/dev/null || true
    systemctl daemon-reload
    echo "drop-in removed. NOT restarted. Apply in a quiet window: systemctl restart $UNIT" ;;
  status)
    [ -f "$DROP" ] && { echo "drop-in: $DROP"; grep -E "^Environment" "$DROP"; } || echo "drop-in: none (stock binary)"
    pid=$(pgrep -f -- "llama-server.*--alias star-fast" | head -1 || true)
    if [ -n "$pid" ]; then
      echo "star-fast pid $pid binary: $(readlink /proc/$pid/exe)"
      tr '\0' '\n' < /proc/$pid/environ | grep -E "^(GGML_NUMA_BLOCK|LLAMA_RAMFORGE_PLACE|LD_LIBRARY_PATH)=" || echo "  no RAMForge variables"
    else
      echo "star-fast not running"
    fi
    journalctl -u $UNIT --no-pager -n 20000 | grep "ramforge: placed" | tail -3 || true ;;
  *) sed -n 2,13p "$0"; exit 2 ;;
esac
