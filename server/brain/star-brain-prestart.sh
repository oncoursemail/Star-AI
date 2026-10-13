#!/bin/bash
# STAR Brain pre-start step (systemd ExecStartPre, runs as user star, needs no root).
#
# Why: the brain is started under `numactl --interleave=all` so that the model weights are spread over all four
# memory nodes (one DDR4 channel each). Interleave is best effort: a node with no FREE memory at load time is silently
# skipped and the weights pile up on the other nodes, which costs up to half of the generation speed
# (measured 2026-10-10: 5.7 tok/s with two nodes full, 9.6 tok/s with all four available).
# Free memory is usually missing because of cold page cache (downloaded model files, old mmap'd weights).
#
# What it does:
#   1. drops the model files themselves from the page cache (they are loaded with DirectIO, so the cache is useless);
#   2. for every node that still has less than STAR_NODE_FREE_MB free, allocates and immediately releases memory bound
#      to that node, which makes the kernel drop cold, unmapped page cache there. The request is capped at what is
#      free plus 80% of the unmapped, non-shared page cache of that node, and the helper marks itself as the preferred
#      out-of-memory victim, so it cannot push anything else out of memory.
# It never fails the service start: every step is best effort and the script always exits 0.

# Default target: the proposed fleet needs about 14.6 GB per node (58 GB over four nodes); 16 GB leaves a margin.
NEED_MB=${STAR_NODE_FREE_MB:-16000}
MODEL_DIRS=${STAR_MODEL_DIRS:-"/opt/star/models /opt/star/spec"}

for d in $MODEL_DIRS; do
  for f in "$d"/*.gguf "$d"/*/*.gguf; do
    [ -f "$f" ] && dd of="$f" oflag=nocache conv=notrunc,fdatasync count=0 status=none 2>/dev/null
  done
done

for mi in /sys/devices/system/node/node[0-9]*/meminfo; do
  [ -r "$mi" ] || continue
  n=${mi%/meminfo}; n=${n##*node}
  free=$(awk '/MemFree:/{print int($4/1024)}' "$mi")
  if [ "$free" -lt "$NEED_MB" ] && command -v numactl >/dev/null && command -v python3 >/dev/null; then
    file=$(awk '/FilePages:/{print int($4/1024)}' "$mi")
    mapped=$(awk '/ Mapped:/{print int($4/1024)}' "$mi")
    shmem=$(awk '/ Shmem:/{print int($4/1024)}' "$mi")
    cold=$(( file - mapped - shmem )); [ "$cold" -lt 0 ] && cold=0
    cap=$(( free + cold * 8 / 10 ))
    want=$NEED_MB; [ "$want" -gt "$cap" ] && want=$cap
    if [ "$want" -gt "$free" ]; then
      ( echo 1000 > /proc/self/oom_score_adj 2>/dev/null
        exec numactl --cpunodebind="$n" --membind="$n" python3 -c "x = b'\1' * ($want << 20)" ) >/dev/null 2>&1
    fi
  fi
  echo "star-brain prestart: node $n free $(awk '/MemFree:/{print int($4/1024)}' "$mi") MB (target $NEED_MB)"
done
exit 0
