#!/bin/bash
# usage: ab.sh LABEL BINDIR [extra llama-server flags...]   (run as user star, under the quiet lock)
L=$1; B=$2; shift 2
M=/opt/star/models/qwen3.6-35b-a3b/Qwen3.6-35B-A3B-Q4_K_M.gguf
P=8094; OUT=/opt/star/bench/ab-20261013; mkdir -p $OUT
python3 - <<'PY'
import os
for root in ("/opt/star/models", "/opt/star/models-candidates"):
    for d, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(d, f)
            try:
                fd = os.open(p, os.O_RDONLY); os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED); os.close(fd)
            except OSError: pass
PY
numastat -m | grep -E "MemFree" > $OUT/$L.numa-before
EXTRA=${NUMACMD:-"numactl --interleave=all"}
COMMON=${COMMON:-"--reasoning off -fa on -lm dio"}
LD_LIBRARY_PATH=$B $EXTRA $B/llama-server --host 127.0.0.1 --port $P -m ${MODEL:-$M} --alias star-fast --jinja $COMMON \
  -c ${CTX:-65536} -np ${NP:-2} ${NUMAFLAG:---numa distribute} -t ${T:-24} -tb ${TB:-48} "$@" > $OUT/$L.server.log 2>&1 &
SP=$!
for i in $(seq 1 180); do curl -sf localhost:$P/health >/dev/null && break; sleep 1; done
echo "$L loaded after ${i}s"
PID=$(pgrep -f "port $P" | head -1)
numastat -p $SP | tail -2 > $OUT/$L.numa-proc
[ -z "$SKIPVAL" ] && python3 /opt/star/bench/validate.py --base http://127.0.0.1:$P --models star-fast --reps 3 --no-contention --tag $L --out $OUT/$L.validate.json | grep -v saved
for n in ${PAR:-2}; do python3 /opt/star/bench/par.py http://127.0.0.1:$P star-fast $n | tee $OUT/$L.par$n.json; done
grep -m1 -E "system_info" $OUT/$L.server.log | cut -c1-200
kill $SP; wait $SP 2>/dev/null
cat $OUT/$L.numa-proc
