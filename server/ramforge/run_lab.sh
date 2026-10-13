#!/bin/bash
# RAMForge lab runner (server 1 container, run as user star, ONLY while holding the quiet lock).
# Never touches the live star-brain service: test binaries run on their own and llama-server uses port 8094.
#
#   run_lab.sh bw                          NUMA read-bandwidth suite (numa_bw), ~2 min
#   run_lab.sh bench LABEL [ENV=V ...]     llama-bench pp512/tg128 x3 with the RAMForge build, env vars as given
#   run_lab.sh server LABEL [ENV=V ...] -- [llama-server flags]   temp server :8094 + specbench, then stop
#   run_lab.sh experts                     llama-imatrix routing counts on code.txt / prose.txt, ~6 min
#   run_lab.sh busy                        CPU use of the live star-fast process over 3 s (should be ~0 before a run)
#
# Paths can be overridden: RF (lab dir), BIN (RAMForge build), M (model), OUT (results).
set -u
RF=${RF:-/opt/star/src/ramforge}
BIN=${BIN:-/opt/star/src/llama.cpp-ramforge/build/bin}
M=${M:-/opt/star/models/qwen3.6-35b-a3b/Qwen3.6-35B-A3B-Q4_K_M.gguf}
OUT=${OUT:-$RF/results}
P=8094
mkdir -p "$OUT"

drop_model_cache() {  # so interleave/placement decide where weights go, not the page cache
  python3 - "$M" <<'PY'
import os, sys
for p in sys.argv[1:]:
    try:
        fd = os.open(p, os.O_RDONLY); os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED); os.close(fd)
    except OSError:
        pass
PY
}

busy() {
  local pid; pid=$(pgrep -f -- "--alias star-fast" | head -1)
  [ -z "$pid" ] && { echo "live star-fast: not running"; return; }
  local a b; a=$(awk '{print $14+$15}' /proc/$pid/stat); sleep 3; b=$(awk '{print $14+$15}' /proc/$pid/stat)
  echo "live star-fast pid $pid: $(( (b - a) / 3 ))% CPU over 3 s (100 = one core)"
}

case "${1:-}" in
  busy) busy ;;
  bw)
    busy
    numastat -m | grep MemFree
    for spec in node:0:0 node:1:1 node:2:2 node:3:3 node:0:1 node:0:2 node:0:3 node:1:0 local-all interleave-all onenode-all:0 local-all interleave-all; do
      "$RF/numa_bw" "$spec" 3 | tee -a "$OUT/bw-$(date -u +%H%M).jsonl"
    done ;;
  bench)
    L=$2; shift 2
    busy; drop_model_cache
    numastat -m | grep MemFree > "$OUT/$L.memfree"
    rm -f "$OUT/$L.prof"
    BGPID=""
    if [ -n "${BG:-}" ]; then   # heavy background job pinned to node $BG (6 threads streaming that node's memory)
      "$RF/numa_bw" "node:$BG:$BG" 900 > "$OUT/$L.bg.json" 2>&1 & BGPID=$!; sleep 2
    fi
    env GGML_RF_PROFILE="$OUT/$L.prof" "$@" ${NUMACMD:-numactl --interleave=all} "$BIN/llama-bench" -m "$M" -lm dio ${NUMAFLAG:---numa distribute} \
      -t ${T:-24} -fa 1 -p ${PP:-512} -n 128 -r ${R:-3} -o json > "$OUT/$L.bench.json" 2> "$OUT/$L.bench.err"
    [ -n "$BGPID" ] && kill $BGPID 2>/dev/null
    grep -E "ramforge:" "$OUT/$L.bench.err"
    python3 - "$OUT/$L.bench.json" <<'PY'
import json, sys
for r in json.load(open(sys.argv[1])):
    print("%s pp%s/tg%s: %.2f +- %.2f tok/s" % (r.get("n_threads"), r["n_prompt"], r["n_gen"], r["avg_ts"], r["stddev_ts"]))
PY
    busy ;;
  server)
    L=$2; shift 2
    ENVS=(); while [ $# -gt 0 ] && [ "$1" != "--" ]; do ENVS+=("$1"); shift; done; [ "${1:-}" = "--" ] && shift
    busy; drop_model_cache
    env "${ENVS[@]}" GGML_RF_PROFILE="$OUT/$L.prof" numactl --interleave=all "$BIN/llama-server" --host 127.0.0.1 --port $P \
      -m "$M" --alias star-fast --jinja --reasoning off -fa on -lm dio -c 32768 -np 1 --numa distribute -t 24 -tb 48 "$@" \
      > "$OUT/$L.server.log" 2>&1 &
    SP=$!
    for i in $(seq 1 240); do curl -sf localhost:$P/health >/dev/null && break; sleep 1; done
    echo "$L loaded after ${i}s"; grep -E "ramforge:" "$OUT/$L.server.log"
    numastat -p $SP | tail -2
    python3 "$RF/specbench.py" --base http://127.0.0.1:$P --tag "$L" --reps "${REPS:-2}" ${ONLY:+--only $ONLY} --out "$OUT/$L.spec.json"
    kill $SP; wait $SP 2>/dev/null
    busy ;;
  experts)
    busy
    for f in code prose; do
      numactl --interleave=all "$BIN/llama-imatrix" -m "$M" -f "$RF/corpus/$f.txt" -o "$OUT/$f.imatrix.gguf" --output-format gguf \
        -c 512 -t 48 --numa distribute -lm dio > "$OUT/$f.imatrix.log" 2>&1
      tail -2 "$OUT/$f.imatrix.log"
    done
    OUT_JSON="$OUT/expert-stats.json"
    OUT=$OUT_JSON /opt/star/knowledge/venv/bin/python "$RF/expert_stats.py" analyse "$OUT/code.imatrix.gguf" "$OUT/prose.imatrix.gguf" ;;
  *) sed -n 2,12p "$0"; exit 2 ;;
esac
