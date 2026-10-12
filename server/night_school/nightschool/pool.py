"""The practice pool: task files in the same JSON shape as the evaluation suites, validated one task at a time
with the repository's own loader. The evaluation suites themselves are never practice material."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import tempfile

FORBIDDEN_NAME = re.compile(r"golden|holdout", re.I)       # the measuring stick and the blind exam
GUARD_FILE = "forbidden-prompts.json"                       # hashes only, written by `guard`


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(" ".join(str(prompt).lower().split()).encode("utf-8")).hexdigest()


def is_validation(task_id: str, percent: int) -> bool:
    """A fixed share of the pool, chosen by the task id alone, so the choice never changes."""
    digest = hashlib.sha256(("night-school-validation:" + task_id).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100 < percent


def build_guard(suite_files: list[Path]) -> dict:
    """Hashes of the prompts and the ids of evaluation suites, so that a practice task copied from one is dropped.
    Only hashes and ids leave this function; no prompt, reference or test is kept."""
    hashes, ids = set(), set()
    for path in suite_files:
        if "holdout" in Path(path).name.lower():
            raise ValueError("the blind exam is never read")
        for row in json.loads(Path(path).read_text(encoding="utf-8")):
            if isinstance(row, dict) and isinstance(row.get("prompt"), str):
                hashes.add(prompt_hash(row["prompt"]))
                ids.add(str(row.get("id")))
    return {"prompt_sha256": sorted(hashes), "ids": sorted(ids)}


class Pool:
    def __init__(self, tasks: list[dict], dropped: dict[str, int], files: int, prelude: str):
        self.tasks, self.dropped, self.files, self.prelude = tasks, dropped, files, prelude

    def summary(self) -> str:
        why = ", ".join(f"{k} {v}" for k, v in sorted(self.dropped.items())) or "none"
        return (f"{len(self.tasks)} practice tasks loaded from {self.files} files; "
                f"{sum(self.dropped.values())} dropped ({why})")


def load_pool(folder: Path, *, extra: list[dict] | None = None) -> Pool:
    """Every automated task of every *.json file in `folder` that the repository's loader accepts."""
    from star.eval_runner import validate_tasks
    from star.evals import load_catalog
    folder = Path(folder)
    guard = {}
    guard_path = folder / GUARD_FILE
    if guard_path.is_file():
        guard = json.loads(guard_path.read_text(encoding="utf-8"))
    banned_prompts, banned_ids = set(guard.get("prompt_sha256") or []), set(guard.get("ids") or [])
    prelude_file = folder / "prelude.luau"
    prelude = prelude_file.read_text(encoding="utf-8").replace("\r\n", "\n") if prelude_file.is_file() else ""
    dropped: dict[str, int] = {}
    tasks, seen, files = [], set(), 0

    def drop(reason: str) -> None:
        dropped[reason] = dropped.get(reason, 0) + 1

    sources: list[tuple[Path, list]] = []
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        if path.name == GUARD_FILE:
            continue
        if FORBIDDEN_NAME.search(path.name):
            drop("evaluation file refused")
            continue
        files += 1
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            drop("file is not JSON")
            continue
        if not isinstance(rows, list):
            drop("file is not a task list")
            continue
        sources.append((path.parent, rows))
    if extra:
        sources.append((folder, list(extra)))
    with tempfile.TemporaryDirectory(prefix="ns-pool-") as scratch:
        probe = Path(scratch) / "one.json"
        for directory, rows in sources:
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get("id"), str):
                    drop("no id")
                    continue
                if row["id"] in seen:
                    drop("duplicate id")
                    continue
                try:
                    probe.write_text(json.dumps([row]), encoding="utf-8")
                    load_catalog(probe)                              # the loader's own rules
                    problems = validate_tasks([row], directory)
                except (ValueError, KeyError, TypeError, AttributeError) as exc:
                    problems = [str(exc) if isinstance(exc, ValueError) else type(exc).__name__]
                if problems:
                    # The loader's own words (without the task id), so whoever writes the tasks can fix them.
                    drop("loader refused: " + str(problems[0]).split(": ", 1)[-1][:70] if str(problems[0]).startswith(row["id"])
                         else "loader refused: " + str(problems[0])[:70])
                    continue
                if row.get("run_mode") != "automated":
                    drop("not automated")
                    continue
                copied = row["id"] in banned_ids or prompt_hash(row["prompt"]) in banned_prompts
                if copied or row["id"].upper().startswith("HO-"):
                    drop("copy of an evaluation task")
                    continue
                unit = (row.get("auto") or {}).get("unit_test")
                task = dict(row)
                task["_test_body"] = ((directory / unit["file"]).read_text(encoding="utf-8").replace("\r\n", "\n")
                                      if unit else "")
                seen.add(row["id"])
                tasks.append(task)
    return Pool(tasks, dropped, files, prelude)
