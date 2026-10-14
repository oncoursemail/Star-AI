# Summary of run_lab.sh server results (results/SV*.spec.json): gen/prompt tok/s, first token, greedy text identity vs the first run.
import json, glob, os
D = "/opt/star/src/ramforge/results"
ref = None
for f in sorted(glob.glob(D + "/SV*.spec.json"), key=os.path.getmtime):
    j = json.load(open(f)); rows = j["rows"]
    shas = [r["sha"] for r in rows]
    if ref is None: ref = shas
    same = sum(a == b for a, b in zip(shas, ref))
    pn = sum(r["prompt_n"] or 0 for r in rows); pms = sum(r["prompt_ms"] or 0 for r in rows)
    ft = sorted((r["prompt_ms"] or 0) / 1000 for r in rows)
    big = [r for r in rows if r["kind"] == "code_edit"]
    print("%-9s gen %.2f tok/s | prompt %d tok in %.1f s = %.1f tok/s | first token median %.2f s, code_edit %s s | text identical to SVA0-1: %d/%d"
          % (j["tag"], j["summary"]["all"]["gen_tps"], pn, pms / 1000, pn / (pms / 1000), ft[len(ft) // 2],
             "/".join("%.2f" % ((r["prompt_ms"] or 0) / 1000) for r in big), same, len(ref)))
