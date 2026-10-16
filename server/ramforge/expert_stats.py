#!/usr/bin/env python3
"""RAMForge expert_stats: how evenly does Qwen3.6-35B-A3B route tokens over its 256 experts?

1) build a corpus from the repo (no user data):  expert_stats.py corpus <repo root> <out dir>
   -> code.txt (Luau from examples/ and non-holdout eval tests) and prose.txt (docs + development task prompts)
2) on the server run llama-imatrix on each file (see run_lab.sh), which stores per-expert routing counts
   in <file>.counts tensors of the GGUF imatrix
3) analyse:  expert_stats.py analyse code.imatrix.gguf [prose.imatrix.gguf]   (needs numpy + gguf-py)
"""
import json
import os
import sys


def corpus(root, out, limit=48000):
    os.makedirs(out, exist_ok=True)
    code, prose = [], []
    for base in ("examples", "evals/roblox/tests"):
        for d, _, fs in os.walk(os.path.join(root, base)):
            for f in sorted(fs):
                if f.endswith((".luau", ".lua")) and not f.startswith("HO-"):
                    with open(os.path.join(d, f), encoding="utf-8", errors="replace") as fh:
                        code.append(fh.read())
    for name in ("practice-tasks-debugging-v1.json", "practice-tasks-security-v1.json", "golden-tasks-v2.json"):
        p = os.path.join(root, "evals/roblox", name)
        if os.path.exists(p):
            data = json.load(open(p, encoding="utf-8"))
            tasks = data if isinstance(data, list) else data.get("tasks", [])
            prose += [t.get("prompt", "") for t in tasks if t.get("split", "development") != "holdout"]
    for f in ("docs/research/server-inference.md", "docs/research/intelligence-architecture.md", "README.md"):
        p = os.path.join(root, f)
        if os.path.exists(p):
            prose.append(open(p, encoding="utf-8", errors="replace").read())
    for name, parts in (("code.txt", code), ("prose.txt", prose)):
        text = "\n\n".join(parts)[:limit]
        with open(os.path.join(out, name), "w", encoding="utf-8") as fh:
            fh.write(text)
        print(name, len(text), "chars")


def load_counts(path):
    sys.path.insert(0, os.environ.get("GGUF_PY", "/opt/star/src/llama.cpp/gguf-py"))
    import numpy as np
    from gguf import GGUFReader
    r = GGUFReader(path)
    out = {}
    for t in r.tensors:
        if t.name.endswith(".counts") and "ffn_gate_exps" in t.name:
            layer = int(t.name.split(".")[1])
            out[layer] = np.array(t.data, dtype=np.float64).reshape(-1)
    return out


def analyse(paths):
    import numpy as np
    sets = [load_counts(p) for p in paths]
    res = {"files": paths, "layers": {}}
    k_vals = (8, 16, 32, 64)
    agg = {k: [] for k in k_vals}
    ratios, cvs, ents, overlaps = [], [], [], []
    for layer in sorted(sets[0]):
        c = sets[0][layer]
        if c.sum() == 0:
            continue
        p = c / c.sum()
        srt = np.sort(p)[::-1]
        row = {"tokens_x_k": int(c.sum()), "max_over_mean": round(float(srt[0] * len(p)), 2),
               "cv": round(float(p.std() / p.mean()), 3),
               "entropy_frac": round(float(-(p[p > 0] * np.log(p[p > 0])).sum() / np.log(len(p))), 4),
               "unused": int((c == 0).sum())}
        for k in k_vals:
            row["top%d_share" % k] = round(float(srt[:k].sum()), 3)
            agg[k].append(srt[:k].sum())
        ratios.append(row["max_over_mean"]); cvs.append(row["cv"]); ents.append(row["entropy_frac"])
        if len(sets) > 1 and layer in sets[1] and sets[1][layer].sum() > 0:
            a = set(np.argsort(c)[::-1][:32]); b = set(np.argsort(sets[1][layer])[::-1][:32])
            row["top32_overlap_with_2nd"] = round(len(a & b) / 32, 3)
            overlaps.append(row["top32_overlap_with_2nd"])
        res["layers"][layer] = row
    res["summary"] = {
        "layers": len(res["layers"]),
        "uniform_topk_share": {k: round(k / 256, 3) for k in k_vals},
        "mean_topk_share": {k: round(float(np.mean(v)), 3) for k, v in agg.items()},
        "max_over_mean_median": round(float(np.median(ratios)), 2),
        "cv_median": round(float(np.median(cvs)), 3),
        "entropy_frac_median": round(float(np.median(ents)), 4),
    }
    if overlaps:
        res["summary"]["top32_overlap_code_vs_prose_mean"] = round(float(np.mean(overlaps)), 3)
    print(json.dumps(res["summary"], indent=1))
    return res


if __name__ == "__main__":
    if sys.argv[1] == "corpus":
        corpus(sys.argv[2], sys.argv[3])
    else:
        r = analyse(sys.argv[2:])
        out = os.environ.get("OUT")
        if out:
            json.dump(r, open(out, "w"), indent=1)
