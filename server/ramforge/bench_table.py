# Summary of run_lab.sh bench results (results/*.bench.json): pp/tg tok/s and the placement line, oldest first.
import json, glob, os, sys
d = sys.argv[1] if len(sys.argv) > 1 else "/opt/star/src/ramforge/results"
for f in sorted(glob.glob(d + "/*.bench.json"), key=os.path.getmtime):
    L = os.path.basename(f)[:-11]
    try:
        rs = json.load(open(f))
    except Exception as e:
        print(L, "BAD", e); continue
    pp = [r for r in rs if r["n_gen"] == 0]; tg = [r for r in rs if r["n_prompt"] == 0]
    err = open(f[:-10] + "bench.err").read()
    rf = [l for l in err.splitlines() if l.startswith("ramforge:")]
    print("%-14s pp %7.2f +-%5.2f  tg %6.2f +-%4.2f  %s" % (L, pp[0]["avg_ts"] if pp else 0, pp[0]["stddev_ts"] if pp else 0,
          tg[0]["avg_ts"] if tg else 0, tg[0]["stddev_ts"] if tg else 0, rf[0][:150] if rf else ""))
