#!/bin/bash
# rrlab.sh LABEL [server flags...] : temp reranker llama-server on :8094 (live binary + env, live flags + given flags), replay fixture
OUT=/opt/star/src/ramforge/results; M=/opt/star/models/qwen3-reranker-0.6b/qwen3-reranker-0.6b-q8_0.gguf; B=/opt/star/bin-ramforge
L=$1; shift
env LD_LIBRARY_PATH=$B GGML_NUMA_BLOCK=1 LLAMA_RAMFORGE_PLACE=1 numactl --interleave=all $B/llama-server --host 127.0.0.1 --port 8094 \
  -m $M --alias star-rerank --reranking -fa on -lm dio --cache-ram 0 --numa distribute "$@" > $OUT/rr-$L.server.log 2>&1 &
SP=$!
for i in $(seq 1 120); do curl -sf localhost:8094/health >/dev/null && break; sleep 1; done
python3 /opt/star/src/ramforge/rr2.py http://127.0.0.1:8094 $OUT/rrfix10.json $L ${ND:-15} ${MC:-100000} | tee -a $OUT/rr2.jsonl | cut -c1-140
kill $SP; wait $SP 2>/dev/null
