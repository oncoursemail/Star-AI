# Summary of starkb eval result files written by rreval.sh: recall@k, MRR, latency, rerank time per mode.
import json, glob, os
for f in sorted(glob.glob("/opt/star/src/ramforge/results/kbeval-*-rr*.json"), key=os.path.getmtime):
    d = json.load(open(f))
    for m, v in d["summary"].items():
        print("%-40s %-14s n %2d r@1 %.3f r@3 %.3f r@5 %.3f r@10 %.3f mrr %.4f med %7.0f ms rerank %s" % (os.path.basename(f), m, v["n"], v["recall@1"], v["recall@3"], v["recall@5"], v["recall@10"], v["mrr@10"], v["latency_ms"]["median"], v["stage_mean_ms"].get("rerank_ms")))
