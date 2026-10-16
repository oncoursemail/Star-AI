"""Apprentice dataset: night school's verified worked examples -> train / validation JSONL + a held-out measuring slice.

    python build_dataset.py --examples s1/examples.jsonl s2/examples.jsonl --pool pool/ --golden evals/roblox \
        --out work/apprentice/data

Rules (docs/agents/apprentice-model.md):
- Only rows night school marked verified (passed the app's automatic checks).
- Never golden or holdout evaluation tasks: golden ids and prompt hashes are excluded; the holdout file is never
  opened (any path with "holdout" in its name is refused). The pool's own guard file (hashes) is applied too.
- A fixed 20 % of ALL pool tasks (by task id hash) is the measuring slice: never trained on, whether or not night
  school solved it, so the slice is not biased towards easy tasks.
- Dedupe: one row per task (newest), then one row per normalised prompt and per answer.
- The target is the model's own text: STAR's appended footer (Luau check note, sources list) is cut off.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SYSTEM = ("You are STAR, a Roblox game development assistant. Answer the request with complete, working Luau code in "
          "```lua fenced blocks and a short explanation. Use current Roblox APIs (task.wait, not wait).")
MEASURE_PERCENT = 20
VAL_PERCENT = 10
GUARD_FILE = "forbidden-prompts.json"


def norm_hash(text: str) -> str:
    """Same normalisation as night school's prompt_hash (server/night_school/nightschool/pool.py)."""
    return hashlib.sha256(" ".join(str(text).lower().split()).encode("utf-8")).hexdigest()


def bucket(salt: str, task_id: str) -> int:
    return int(hashlib.sha256((salt + ":" + task_id).encode("utf-8")).hexdigest()[:8], 16) % 100


def is_measure(task_id: str) -> bool:
    return bucket("apprentice-measure", task_id) < MEASURE_PERCENT


def golden_guard(folder: Path | None) -> tuple[set[str], set[str]]:
    ids, hashes = set(), set()
    if folder is None:
        return ids, hashes
    for path in sorted(Path(folder).glob("*.json")):
        name = path.name.lower()
        if "holdout" in name:
            continue                      # the blind exam is never opened
        if "golden" not in name:
            continue
        for row in json.loads(path.read_text(encoding="utf-8")):
            if isinstance(row, dict):
                ids.add(str(row.get("id")))
                if isinstance(row.get("prompt"), str):
                    hashes.add(norm_hash(row["prompt"]))
    return ids, hashes


def load_pool(folder: Path) -> list[dict]:
    tasks, seen = [], set()
    for path in sorted(Path(folder).glob("*.json")):
        if path.name == GUARD_FILE or re.search(r"golden|holdout", path.name, re.I):
            continue
        for row in json.loads(path.read_text(encoding="utf-8")):
            if isinstance(row, dict) and isinstance(row.get("id"), str) and row["id"] not in seen \
                    and row.get("run_mode") == "automated":
                seen.add(row["id"])
                tasks.append({"id": row["id"], "category": row.get("category", ""), "prompt": row.get("prompt", ""),
                              "file": path.name})
    return tasks


def build(example_files: list[Path], pool: Path, golden: Path | None) -> dict:
    from star.eval_checks import split_answer
    for path in [*example_files, pool]:
        if "holdout" in str(path).lower():
            raise SystemExit("refused: the holdout set is never read")
    gold_ids, gold_hashes = golden_guard(golden)
    guard = pool / GUARD_FILE
    if guard.is_file():
        data = json.loads(guard.read_text(encoding="utf-8"))
        gold_ids |= set(data.get("ids") or [])
        gold_hashes |= set(data.get("prompt_sha256") or [])
    pool_tasks = load_pool(pool)
    counts = {"rows_read": 0, "not_verified": 0, "golden_or_holdout": 0, "dup_task": 0, "dup_prompt": 0,
              "dup_answer": 0, "measure_slice_excluded": 0, "empty_after_footer": 0}
    newest: dict[str, dict] = {}
    for path in example_files:
        origin = path.parent.name
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            counts["rows_read"] += 1
            if row.get("verified") is False:
                counts["not_verified"] += 1
                continue
            tid = str(row["task"])
            if tid in gold_ids or norm_hash(row["prompt"]) in gold_hashes or tid.upper().startswith("HO-"):
                counts["golden_or_holdout"] += 1
                continue
            row["_origin"] = origin
            if tid in newest:
                counts["dup_task"] += 1
                if str(row.get("ts", "")) <= str(newest[tid].get("ts", "")):
                    continue
            newest[tid] = row
    rows, seen_p, seen_a = [], set(), set()
    for tid, row in sorted(newest.items()):
        body = split_answer(row["answer"])[0].strip()
        if not body:
            counts["empty_after_footer"] += 1
            continue
        ph, ah = norm_hash(row["prompt"]), norm_hash(body)
        if ph in seen_p:
            counts["dup_prompt"] += 1
            continue
        if ah in seen_a:
            counts["dup_answer"] += 1
            continue
        seen_p.add(ph)
        seen_a.add(ah)
        if is_measure(tid):
            counts["measure_slice_excluded"] += 1
            continue
        rows.append({"id": tid, "category": row.get("category", ""), "origin": row["_origin"],
                     "kind": row.get("kind", ""), "lessons_in_context": bool(row.get("lessons")),
                     "messages": [{"role": "system", "content": SYSTEM},
                                  {"role": "user", "content": row["prompt"]},
                                  {"role": "assistant", "content": body}]})
    train = [r for r in rows if bucket("apprentice-val", r["id"]) >= VAL_PERCENT]
    val = [r for r in rows if bucket("apprentice-val", r["id"]) < VAL_PERCENT]
    measure = sorted((t for t in pool_tasks if is_measure(t["id"]) and t["id"] not in gold_ids
                      and norm_hash(t["prompt"]) not in gold_hashes), key=lambda t: bucket("apprentice-order", t["id"]))
    trained = {r["id"] for r in rows}
    assert not trained & {t["id"] for t in measure}, "a measuring task leaked into training"
    counts.update(train=len(train), val=len(val), measure_tasks=len(measure), pool_tasks=len(pool_tasks),
                  train_categories=len({r["category"] for r in train}))
    return {"train": train, "val": val, "measure": measure, "counts": counts}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--examples", type=Path, nargs="+", required=True)
    ap.add_argument("--pool", type=Path, required=True)
    ap.add_argument("--golden", type=Path, default=ROOT / "evals" / "roblox")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    result = build(args.examples, args.pool, args.golden)
    args.out.mkdir(parents=True, exist_ok=True)
    for name in ("train", "val"):
        with open(args.out / f"{name}.jsonl", "w", encoding="utf-8", newline="\n") as handle:
            for row in result[name]:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    (args.out / "measure.json").write_text(json.dumps(result["measure"], indent=1), encoding="utf-8")
    manifest = {"counts": result["counts"], "system_prompt": SYSTEM,
                "sources": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in args.examples},
                "provenance": "answers: STAR's own models in night school (server 1 star-fast = Qwen3.6-35B-A3B, "
                              "Apache-2.0; server 2 = Gemma 4 E2B); every answer passed the app's automatic checks; "
                              "task prompts: the practice pool (agent-written + generated ledger tasks)."}
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps(result["counts"]))


if __name__ == "__main__":
    main()
