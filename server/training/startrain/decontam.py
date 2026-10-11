"""Decontamination against the evaluation suites (gate G8) and the index builder.

The evaluation suites (the golden tasks, their reference answers, deliberately bad answers and unit tests, and
other question files) are the gate that measures the training pilot. Nothing in them may reach the training data:
the generator never reads them while writing tasks; it only compares finished candidates against this index.
Every text in every suite becomes an index item; a candidate is rejected when its task text, solution or tests
match any item exactly or fuzzily (token 5-gram Jaccard / containment, shared 8-grams, embedding cosine).

The index is built from a suite folder (`evals/roblox` of the app repository) copied to the server; it holds
hashes and shingles, plus embeddings of the task texts, and is not committed to any repository.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import similarity as sim

INDEX_SCHEMA = 1
EMBED_PREFIX = "task: sentence similarity | query: "


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")


def collect_items(suite_root: Path, extra_files: list[Path] | None = None) -> tuple[list[dict], dict]:
    """(items, file hashes). Items: {id, kind, source, text}. kind is prompt, answer, test or other."""
    items: list[dict] = []
    hashes: dict[str, str] = {}

    def note(path: Path, raw: bytes) -> None:
        hashes[str(path.relative_to(suite_root)) if path.is_relative_to(suite_root) else path.name] = \
            hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()

    for path in sorted(suite_root.glob("golden-tasks-*.json")):
        raw = path.read_bytes()
        note(path, raw)
        for task in json.loads(raw.decode("utf-8")):
            for key in ("prompt", "goal"):
                if isinstance(task.get(key), str) and task[key].strip():
                    items.append({"id": f"{path.stem}:{task.get('id')}:{key}", "kind": "prompt",
                                  "source": path.name, "text": task[key]})
    for folder, kind in (("reference", "answer"), ("tests", "test")):
        for path in sorted((suite_root / folder).glob("*")) if (suite_root / folder).is_dir() else []:
            if path.is_file():
                note(path, path.read_bytes())
                items.append({"id": f"{folder}/{path.name}", "kind": kind, "source": folder, "text": _read(path)})
    for path in sorted(suite_root.glob("*.luau")):
        note(path, path.read_bytes())
        items.append({"id": path.name, "kind": "test", "source": path.name, "text": _read(path)})
    for path in extra_files or []:
        raw = path.read_bytes()
        note(path, raw)
        if path.suffix == ".jsonl":
            for n, line in enumerate(raw.decode("utf-8", "replace").splitlines()):
                if not line.strip() or line.lstrip().startswith("//"):
                    continue
                row = json.loads(line)
                for key in ("question", "query", "prompt", "task"):
                    if isinstance(row.get(key), str) and row[key].strip():
                        items.append({"id": f"{path.name}:{n}:{key}", "kind": "prompt", "source": path.name,
                                      "text": row[key]})
        elif path.suffix == ".json":
            data = json.loads(raw.decode("utf-8"))
            rows = data if isinstance(data, list) else data.get("cases") or data.get("tasks") or []
            for n, row in enumerate(rows):
                if isinstance(row, dict):
                    for key in ("prompt", "question", "query", "task", "goal"):
                        if isinstance(row.get(key), str) and row[key].strip():
                            items.append({"id": f"{path.name}:{n}:{key}", "kind": "prompt", "source": path.name,
                                          "text": row[key]})
    return items, hashes


def build_index(suite_root: Path, extra_files: list[Path] | None = None, embed=None) -> dict:
    """`embed(list[str]) -> list[vector]` is optional (task texts get vectors when it is given)."""
    items, hashes = collect_items(suite_root, extra_files)
    if not items:
        raise ValueError("no suite items found under " + str(suite_root))
    out = []
    for item in items:
        is_code = item["kind"] in ("answer", "test")
        toks = sim.tokens(item["text"], code=is_code)
        out.append({
            "id": item["id"], "kind": item["kind"], "source": item["source"],
            "hash": sim.text_hash(item["text"], code=is_code),
            "sh5": sorted(sim.shingles(toks, 5)), "sh8": sorted(sim.shingles(toks, 8)),
            "chars": len(item["text"]),
        })
    if embed is not None:
        prompts = [(i, it) for i, it in enumerate(items) if it["kind"] == "prompt"]
        for start in range(0, len(prompts), 16):
            batch = prompts[start:start + 16]
            vectors = embed([EMBED_PREFIX + it["text"][:2000] for _, it in batch])
            for (i, _), vector in zip(batch, vectors):
                out[i]["vec"] = [round(x, 5) for x in vector]
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    return {"schema": INDEX_SCHEMA, "suite_files": hashes, "suite_digest": digest, "items": out,
            "counts": {"items": len(out), "embedded": sum(1 for o in out if "vec" in o)}}


class Decontaminator:
    def __init__(self, index: dict, settings):
        if index.get("schema") != INDEX_SCHEMA:
            raise ValueError("decontamination index has an unknown schema")
        self.s = settings
        self.digest = index["suite_digest"]
        self.items = []
        for raw in index["items"]:
            self.items.append({**raw, "sh5": set(raw["sh5"]), "sh8": set(raw["sh8"])})

    @classmethod
    def load(cls, path: Path, settings) -> "Decontaminator":
        return cls(json.loads(path.read_text(encoding="utf-8")), settings)

    def check_text(self, fp: dict) -> str:
        """"" when the candidate does not overlap any suite item, else a short reason (no suite text)."""
        s = self.s
        for item in self.items:
            kind = item["kind"]
            if fp["prompt_hash"] == item["hash"] or fp["code_hash"] == item["hash"]:
                return f"exact match with a {kind} of the evaluation suites"
            if kind == "prompt":
                if sim.jaccard(fp["prompt_sh5"], item["sh5"]) >= s.decontam_jaccard:
                    return "task text near-duplicates an evaluation prompt (5-gram Jaccard)"
                if sim.containment(fp["prompt_sh5"], item["sh5"]) >= s.decontam_containment \
                        or sim.containment(item["sh5"], fp["prompt_sh5"]) >= 0.8:
                    return "task text contains an evaluation prompt (5-gram containment)"
                if len(fp["prompt_sh8"] & item["sh8"]) >= 2:
                    return "task text shares long phrases with an evaluation prompt (8-grams)"
            elif kind == "answer":
                if sim.jaccard(fp["code_sh5"], item["sh5"]) >= s.decontam_code_jaccard \
                        or sim.containment(fp["code_sh5"], item["sh5"]) >= 0.6:
                    return "solution overlaps an evaluation reference answer"
            elif kind == "test":
                if sim.jaccard(fp["tests_sh5"], item["sh5"]) >= s.decontam_code_jaccard:
                    return "tests overlap an evaluation unit test"
        return ""

    def check_vector(self, vector: list[float]) -> str:
        best = 0.0
        for item in self.items:
            if "vec" in item:
                best = max(best, sim.cosine(vector, item["vec"]))
        return "task text is semantically close to an evaluation prompt (embedding)" \
            if best >= self.s.decontam_cosine else ""

    def max_cosine(self, vector: list[float]) -> float:
        return max((sim.cosine(vector, it["vec"]) for it in self.items if "vec" in it), default=0.0)

    def self_check(self, suite_root: Path, extra_files: list[Path] | None = None) -> list[str]:
        """Feed every suite text back in as if it were a candidate; returns the ids that were NOT caught."""
        missed = []
        items, _ = collect_items(suite_root, extra_files)
        for item in items:
            if item["kind"] == "prompt":
                fp = sim.fingerprint(item["text"], "x = 1", "")
            elif item["kind"] == "answer":
                fp = sim.fingerprint("a task that is unrelated to anything else here", item["text"], "")
            else:
                fp = sim.fingerprint("a task that is unrelated to anything else here", "x = 1", item["text"])
            if not self.check_text(fp):
                missed.append(item["id"])
        return missed
