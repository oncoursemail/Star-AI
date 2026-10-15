#!/bin/bash
# par_lab.sh LABEL "NP:K[,K] ..." : temp llama-server on :8094 with -np NP (ctx 32768 per slot), then par2.py with K
# background streams + 1 chat. Live flags otherwise. BIN (default live /opt/star/bin), RFENV (e.g. RAMForge variables).
OUT=/opt/star/src/ramforge/results; M=/opt/star/models/qwen3.6-35b-a3b/Qwen3.6-35B-A3B-Q4_K_M.gguf; BIN=${BIN:-/opt/star/bin}
for spec in $2; do
  np=${spec%%:*}; ks=${spec#*:}
  env LD_LIBRARY_PATH=$BIN ${RFENV:-} numactl --interleave=all $BIN/llama-server --host 127.0.0.1 --port 8094 -m $M \
    --alias star-fast --jinja --reasoning off -fa on -lm dio -c $((32768*np)) -np $np --numa distribute -t 24 -tb 48 \
    > $OUT/$1-np$np.server.log 2>&1 &
  SP=$!
  for i in $(seq 1 240); do curl -sf localhost:8094/health >/dev/null && break; sleep 1; done
  echo "$1 np=$np loaded after ${i}s"
  for k in ${ks//,/ }; do
    python3 /opt/star/src/ramforge/par2.py http://127.0.0.1:8094 $k | sed "s/^/$1 np=$np /" | tee -a $OUT/par2.jsonl
  done
  kill $SP; wait $SP 2>/dev/null
done
