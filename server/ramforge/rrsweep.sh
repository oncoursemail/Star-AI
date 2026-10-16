# rrsweep.sh : llama-bench on the reranker model, thread/NUMA/flash-attn sweep (live b11541 binary)
M=/opt/star/models/qwen3-reranker-0.6b/qwen3-reranker-0.6b-q8_0.gguf; B=/opt/star/bin
run() { L=$1; shift; r=$(env LD_LIBRARY_PATH=$B "$@" -m $M -lm dio -p 256,1024 -n 0 -r 3 -o json 2>/dev/null | python3 -c "
import json,sys
print(' '.join('pp%d %.0f' % (r['n_prompt'], r['avg_ts']) for r in json.load(sys.stdin)))"); echo "$L: $r"; }
run "t24 distribute interleave fa1 (live)" numactl --interleave=all $B/llama-bench --numa distribute -t 24 -fa 1
run "t24 distribute interleave fa0"       numactl --interleave=all $B/llama-bench --numa distribute -t 24 -fa 0
run "t12 distribute fa1"                  numactl --interleave=all $B/llama-bench --numa distribute -t 12 -fa 1
run "t6 one node (N0) fa1"                numactl -N 0 -m 0 $B/llama-bench -t 6 -fa 1
run "t12 one node incl SMT fa1"           numactl -N 0 -m 0 $B/llama-bench -t 12 -fa 1
run "t12 two nodes (0,1) fa1"             numactl -N 0,1 -m 0,1 $B/llama-bench -t 12 -fa 1
run "t48 distribute fa1"                  numactl --interleave=all $B/llama-bench --numa distribute -t 48 -fa 1
