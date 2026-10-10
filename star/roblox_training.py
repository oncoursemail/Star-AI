"""Prepare *human-reviewed* Roblox instruction examples for later model training.

This is DATA PREPARATION, not model weight training or autonomous self-learning.
Never imports private chats, GitHub content or Roblox experiences automatically.
An operator supplies explicit rights-confirmed, tested examples from a JSON file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


_CATEGORIES = frozenset({
    "luau", "ui", "animation", "environment", "performance",
    "gameplay", "debugging", "testing", "assets",
})
_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{2,100}$")
_SECRET = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"\b(?:github_pat_|ghp_|sk-)[A-Za-z0-9_-]{16,}",
    re.IGNORECASE,
)
_SYSTEM = (
    "You are STAR's Roblox engineering assistant. Give accurate Luau and "
    "native Roblox Studio guidance, preserve the requested art direction, "
    "separate client/server state, and never claim edits or tests without evidence."
)


def validate_example(row: dict) -> dict:
    if not isinstance(row, dict):
        raise ValueError("Training example must be an object")
    if row.get("reviewed") is not True or row.get("rights_confirmed") is not True:
        raise ValueError("Example requires explicit human review and rights confirmation")
    if not isinstance(row.get("id"), str) or not _ID.fullmatch(row["id"]):
        raise ValueError("Example needs a stable safe ID")
    if row.get("category") not in _CATEGORIES:
        raise ValueError("Unsupported Roblox training category")
    if not isinstance(row.get("group_id"), str) or not _ID.fullmatch(row["group_id"]):
        raise ValueError("Stable group_id required to keep related examples in the same split")
    if not isinstance(row.get("evidence"), list) or not 1 <= len(row["evidence"]) <= 10:
        raise ValueError("Record a real test, review or screenshot evidence reference")
    if any(not isinstance(s, str) or not 1 <= len(s) <= 200 for s in row["evidence"]):
        raise ValueError("Evidence identifiers must be short strings")
    for key, length in (("instruction", 12000), ("response", 32000)):
        value = row.get(key)
        if not isinstance(value, str) or not 20 <= len(value.strip()) <= length:
            raise ValueError(f"{key} length must be 20..{length}")
        if _SECRET.search(value):
            raise ValueError("Example appears to include a private credential")
    return {
        "id": row["id"], "category": row["category"], "group_id": row["group_id"],
        "instruction": row["instruction"].strip(), "response": row["response"].strip(),
    }


def split_examples(rows: list[dict], *, holdout_percent: int = 20) -> dict:
    """Group-stable split. Never include evaluation answers in training JSONL."""
    if not isinstance(rows, list) or len(rows) > 5000:
        raise ValueError("Expected at most 5000 explicitly supplied examples")
    if not isinstance(holdout_percent, int) or not 5 <= holdout_percent <= 40:
        raise ValueError("Evaluation holdout must be 5..40 percent")
    train, evaluation = [], []
    seen_ids, seen_pairs = set(), set()
    for raw in rows:
        item = validate_example(raw)
        if item["id"] in seen_ids:
            raise ValueError("Duplicate training example ID")
        seen_ids.add(item["id"])
        pair = hashlib.sha256(
            (item["instruction"].casefold() + "\x00" + item["response"]).encode("utf-8")
        ).hexdigest()
        if pair in seen_pairs:
            raise ValueError("Duplicate instruction/answer example")
        seen_pairs.add(pair)
        group_bucket = int(hashlib.sha256(item["group_id"].encode("utf-8")).hexdigest(), 16) % 100
        if group_bucket < holdout_percent:
            evaluation.append({
                "id": item["id"], "category": item["category"],
                "input": item["instruction"], "expected": item["response"],
            })
        else:
            train.append({
                "messages": [
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": item["instruction"]},
                    {"role": "assistant", "content": item["response"]},
                ],
            })
    return {
        "train": train,
        "evaluation": evaluation,
        "counts": {"supplied": len(rows), "train": len(train), "evaluation": len(evaluation)},
        "note": (
            "Accepted flags/evidence are user attestations, not automatically verified. "
            "Review for privacy, licensing and label accuracy before fine-tuning. "
            "STAR did not run training or score any examples."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a rights-confirmed Roblox SFT and held-out evaluation dataset")
    parser.add_argument("--input", type=Path, required=True, help="Reviewed examples.json (never read chats automatically)")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--holdout", type=int, default=20)
    args = parser.parse_args(argv)
    if args.input.stat().st_size > 8_000_000:
        parser.error("Input examples.json exceeds 8 MB")
    result = split_examples(json.loads(args.input.read_text(encoding="utf-8")),
                            holdout_percent=args.holdout)
    if not result["train"] or not result["evaluation"]:
        parser.error("Need at least one training and one held-out evaluation example; add groups")
    directory = args.output_dir.expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    target_files = [directory / "roblox_train.jsonl", directory / "roblox_eval.jsonl",
                    directory / "roblox_dataset_report.json"]
    if any(p.exists() for p in target_files):
        parser.error("Output files already exist; choose a new directory to avoid overwriting reviewed data")
    def jsonl(values: list[dict]) -> str:
        return "".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values)
    target_files[0].write_text(jsonl(result["train"]), encoding="utf-8")
    target_files[1].write_text(jsonl(result["evaluation"]), encoding="utf-8")
    report = {"counts": result["counts"], "holdout_percent": args.holdout, "note": result["note"]}
    target_files[2].write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
