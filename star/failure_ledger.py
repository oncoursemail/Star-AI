"""Offline evidence ledger and opt-in practice-task generator for stored STAR evaluation results.

Reads results already on disk. Never runs a model, opens a holdout suite, or changes the evaluation corpus.
Practice tasks come from one family per failure cause (star/practice_gen.py); only `ledger verify` contacts the STAR
server, and only its Luau checker and sandboxed Luau VM (no model call).
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import sys

from . import practice_gen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = ROOT / "evals" / "results"
DEFAULT_SUITES = ROOT / "evals" / "roblox"
CAUSES = (
    "wrong logic",
    "required feature missing",
    "self-check error left unrepaired",
    "answer cut off",
    "invented API name",
)


@dataclass(frozen=True)
class EvidenceRule:
    """Priority-ordered match on an actual failed check or a stored result field."""

    cause: str
    source: str
    expression: str


# The displayed evidence is always the recorded field/check that matched, not an
# inferred model intention. A missing code block is a proxy for an incomplete
# answer; an unknown global may be a typo rather than a fabricated API.
RULES = (
    EvidenceRule("answer cut off", "flag", r"^truncated=True$"),
    EvidenceRule("answer cut off", "product_failure", r"^product_failure: .+"),
    EvidenceRule("answer cut off", "check", r"^(?:answer|luau_block):"),
    EvidenceRule("invented API name", "check",
                 r"^luau_check\[\d+\]:.*(?:Unknown global '|Unknown type '[A-Za-z_]\w*\.[A-Za-z_]\w*)"),
    EvidenceRule("self-check error left unrepaired", "check",
                 r"^(?:luau_check\[\d+\]|typecheck_probe):"),
    EvidenceRule("self-check error left unrepaired", "check",
                 r"^unit_tests:.*(?:did not load|no assertions ran|harness did not finish)"),
    # A unit-test assertion named "required feature: X" checks that a requested function exists (practice tasks of
    # star/practice_gen.py); its failure is a missing feature, not wrong logic.
    EvidenceRule("required feature missing", "check", r"^unit_tests:.*failed:.*\brequired feature: "),
    EvidenceRule("wrong logic", "check", r"^unit_tests:"),
    EvidenceRule("required feature missing", "check", r"^(?:require:|forbid:|citation:)"),
)


@dataclass(frozen=True)
class Failure:
    result_file: str
    task_id: str
    topic: str
    cause: str
    evidence: str


def _signals(record: dict) -> list[tuple[str, str]]:
    signals = []
    if record.get("truncated") is True:
        signals.append(("flag", "truncated=True"))
    if isinstance(record.get("product_failure"), str) and record["product_failure"]:
        signals.append(("product_failure", "product_failure: " + record["product_failure"]))
    for check in record.get("checks") or []:
        if isinstance(check, dict) and check.get("ok") is False:
            signals.append(("check", str(check.get("id", "")) + ": " + str(check.get("detail") or "")))
    for reason in record.get("reasons") or []:
        if isinstance(reason, str) and reason:
            signals.append(("reason", reason))
    return signals


def label_failure(record: dict) -> tuple[str, str] | None:
    """One primary cause and an exact piece of recorded supporting evidence."""
    if record.get("status") != "fail":
        return None
    signals = _signals(record)
    for rule in RULES:
        for source, evidence in signals:
            if rule.source == source and re.search(rule.expression, evidence, re.I):
                return rule.cause, evidence
    # Older result files may have reasons without structured checks.
    return "wrong logic", next((e for _, e in signals), "status=fail; no check detail recorded")


def _topics(suite_name: str, suites: Path, cache: dict[str, dict[str, str]]) -> dict[str, str]:
    name = Path(suite_name).name  # Never follow a path supplied in a result file.
    if "holdout" in name.casefold():
        return {}
    if name not in cache:
        path = suites / name
        if not path.is_file():
            cache[name] = {}
        else:
            rows = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(rows, list):
                raise ValueError(f"invalid suite metadata: {name}")
            cache[name] = {row["id"]: row["category"] for row in rows
                           if isinstance(row, dict) and isinstance(row.get("id"), str)
                           and isinstance(row.get("category"), str)}
    return cache[name]


def read_failures(results: Path = DEFAULT_RESULTS, suites: Path = DEFAULT_SUITES) -> list[Failure]:
    """Keep each failed attempt; do not mistake infrastructure errors for model failures."""
    results, suites = Path(results), Path(suites)
    if not results.is_dir():
        raise ValueError(f"results folder does not exist: {results}")
    failures: list[Failure] = []
    cache: dict[str, dict[str, str]] = {}
    for path in sorted(results.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("tasks"), dict):
            raise ValueError(f"invalid result file: {path.name}")
        suite_name = str((data.get("suite") or {}).get("file") or "")
        if "holdout" in Path(suite_name).name.casefold():
            continue
        topics = _topics(suite_name, suites, cache) if suite_name else {}
        for task_id, record in sorted(data["tasks"].items()):
            if not isinstance(task_id, str) or not isinstance(record, dict):
                raise ValueError(f"invalid task record: {path.name}")
            labeled = label_failure(record)
            if labeled is not None:
                cause, evidence = labeled
                failures.append(Failure(path.name, task_id, topics.get(task_id, "roblox-gameplay"),
                                        cause, evidence))
    return failures


def counts(failures: list[Failure]) -> dict[str, tuple[int, int]]:
    return {
        cause: (sum(f.cause == cause for f in failures),
                len({f.task_id for f in failures if f.cause == cause}))
        for cause in CAUSES
    }


def leading_cause(failures: list[Failure]) -> str:
    if not failures:
        raise ValueError("no failed tasks were found")
    totals = Counter(f.cause for f in failures)
    return max(CAUSES, key=lambda cause: (totals[cause], -CAUSES.index(cause)))


def report_table(failures: list[Failure]) -> str:
    table = ["Cause                              Attempts  Unique tasks",
             "---------------------------------------------------------"]
    for cause, (attempts, unique) in counts(failures).items():
        table.append(f"{cause:<34} {attempts:>5}         {unique:>5}")
    table.append(f"TOTAL                              {len(failures):>5}         "
                 f"{len({f.task_id for f in failures}):>5}")
    table.extend(("", "Result file                         Task ID    Cause                          Recorded check evidence"))
    for failure in failures:
        table.append(f"{failure.result_file:<35} {failure.task_id:<10} {failure.cause:<30} "
                     + failure.evidence.replace("\n", " ")[:180])
    return "\n".join(table)


# --- targeted practice: one family of task specifications per cause (star/practice_gen.py) -----------------------

# The harness prelude of the evaluation suites: the generated unit tests run exactly like the suites' own tests.
PRELUDE = (ROOT / "evals" / "roblox" / "prelude.luau").read_text(encoding="utf-8").replace("\r\n", "\n")
Practice = practice_gen.Generated


def _digest(*parts: str) -> int:
    return int(hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()[:12], 16)


def practice_for(source: Failure, index: int = 0, taken: set[str] | None = None) -> Practice:
    """A task from the family of the failure's own cause, chosen by the failed task id (stable), skipping ids in
    `taken`. `index` asks for the index-th different task for the same failure."""
    family = practice_gen.specs_for(source.cause)
    if not family:
        raise ValueError("unsupported failure cause")
    slots = [(spec, v) for spec in family for v in range(spec.variants)]
    start = _digest(source.task_id, source.cause, source.topic) % len(slots)
    taken = taken if taken is not None else set()
    seen = 0
    for step in range(len(slots)):
        spec, v = slots[(start + step * 7) % len(slots)] if len(slots) % 7 else slots[(start + step) % len(slots)]
        if practice_gen.task_id(spec, v) in taken:
            continue
        if seen == index:
            return practice_gen.build(spec, v, source=f"{source.result_file}:{source.task_id}")
        seen += 1
    raise ValueError(f"no unused practice task left for cause: {source.cause}")


def generate_practice(failures: list[Failure], count: int | None = None, *, per_failure: int = 1,
                      leading_only: bool = False) -> tuple[dict[str, int], list[Practice]]:
    """`per_failure` new exercises per distinct failed (task, cause), each from that cause's own family.
    Returns ({cause: number of exercises}, exercises)."""
    if not failures:
        raise ValueError("no failed tasks were found")
    if per_failure < 1:
        raise ValueError("per-failure must be at least 1")
    wanted = {leading_cause(failures)} if leading_only else set(CAUSES)
    sources = {}
    for f in sorted(failures, key=lambda f: (f.task_id, f.cause, f.result_file)):
        if f.cause in wanted:
            sources.setdefault((f.task_id, f.cause), f)
    ordered = [sources[k] for k in sorted(sources, key=lambda k: (CAUSES.index(k[1]), k[0]))]
    if count is not None:
        if count < 1 or count > len(ordered):
            raise ValueError(f"count must be between 1 and {len(ordered)} distinct failures")
        ordered = ordered[:count]
    taken: set[str] = set()
    items: list[Practice] = []
    for source in ordered:
        for _ in range(per_failure):
            try:
                item = practice_for(source, 0, taken)
            except ValueError:
                break                      # the family is used up; never repeat a task
            taken.add(item.task["id"])
            items.append(item)
    by_cause = {c: sum(i.task["targets_cause"] == c for i in items) for c in CAUSES}
    return {c: n for c, n in by_cause.items() if n}, items


def _words(value: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", value.casefold())


def overlaps_golden(prompt: str, golden_prompt: str) -> bool:
    """Reject eight contiguous shared tokens or unusually heavy token overlap."""
    a, b = _words(prompt), _words(golden_prompt)
    if not a or not b:
        return False
    longest = SequenceMatcher(None, a, b, autojunk=False).find_longest_match().size
    common = len(set(a) & set(b)) / len(set(a) | set(b))
    return longest >= 8 or common >= 0.45


def _golden_prompts(suites: Path) -> list[str]:
    prompts = []
    for path in sorted(Path(suites).glob("golden-tasks-*.json")):
        rows = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError(f"invalid golden catalog: {path.name}")
        prompts.extend(row["prompt"] for row in rows if isinstance(row, dict)
                       and isinstance(row.get("prompt"), str))
    if not prompts:
        raise ValueError("no golden prompts available for the copy guard")
    return prompts


def _refuse_eval_target(path: Path) -> None:
    if any(part.casefold() == "evals" for part in Path(path).parts) or re.search(r"golden|holdout", str(path), re.I):
        raise ValueError("refusing to write to the evaluation corpus (practice never enters evals/ or the holdout)")


def write_practice(items: list[Practice], out: Path, *, suites: Path = DEFAULT_SUITES,
                   selftest_dir: Path | None = None) -> None:
    """Write an opt-in night-school pool file with its tests and the harness prelude. Never an evaluation file.

    Reference and bad answers are written only to `selftest_dir` (a complete suite layout for
    `python -m star.evals selftest` / `ledger verify`), never next to the pool."""
    out = Path(out)
    if not items or out.suffix.lower() != ".json":
        raise ValueError("provide a nonempty practice list and a .json output filename")
    _refuse_eval_target(out)
    targets = [out.parent]
    if selftest_dir is not None:
        selftest_dir = Path(selftest_dir)
        _refuse_eval_target(selftest_dir)
        if selftest_dir.resolve() == out.parent.resolve():
            raise ValueError("the self-test folder (with reference answers) must not be the practice pool folder")
        targets.append(selftest_dir)
    golden = _golden_prompts(Path(suites))
    for item in items:
        if any(overlaps_golden(item.task["prompt"], prompt) for prompt in golden):
            raise ValueError(f"practice prompt overlaps a golden task: {item.task['id']}")
        if item.task["id"].upper().startswith("HO-"):
            raise ValueError("practice ids never use the holdout prefix")
    if len({x.task["id"] for x in items}) != len(items):
        raise ValueError("duplicate practice task identifier")
    plan: list[tuple[Path, str]] = []
    for folder in targets:
        suite_file = out if folder == out.parent else folder / out.name
        plan.append((suite_file, json.dumps([item.task for item in items], ensure_ascii=False, indent=2) + "\n"))
        plan.extend((folder / item.task["auto"]["unit_test"]["file"], item.test_body) for item in items)
        if folder != out.parent:
            plan.extend((folder / "reference" / f"{item.task['id']}.md", item.reference_answer) for item in items)
            plan.extend((folder / "reference" / f"{item.task['id']}.bad.md", item.bad_answer) for item in items)
    for path, _ in plan:
        if path.exists():
            raise FileExistsError(f"refusing to replace existing file: {path}")
    for folder in targets:
        prelude = folder / "prelude.luau"
        if prelude.exists() and prelude.read_text(encoding="utf-8").replace("\r\n", "\n") != PRELUDE:
            raise FileExistsError(f"existing practice prelude is different; use a new output folder: {prelude}")
    for folder in targets:
        (folder / "tests").mkdir(parents=True, exist_ok=True)
        prelude = folder / "prelude.luau"
        if not prelude.exists():
            with prelude.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(PRELUDE)
    for path, text in plan:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)


def check_record(task: dict, answer: str, score) -> dict:
    """The result record eval_runner would store for this answer (status, checks, truncated)."""
    from .eval_checks import looks_truncated
    record = {"status": "pass" if score.passed else "fail", "passed": score.passed, "reasons": score.reasons,
              "checks": [c.record() for c in score.checks]}
    if looks_truncated(answer):
        record["truncated"] = True
    return record


def verify(items: list[Practice], scorer, *, log=print) -> int:
    """Reference answers must pass; bad answers must fail AND be labelled with the task's own cause by the ledger
    rules; empty answers must fail. Returns the number of problems."""
    problems = 0
    for item in items:
        task, cause = item.task, item.task["targets_cause"]
        good = scorer(task, item.reference_answer)
        bad = scorer(task, item.bad_answer)
        empty = scorer(task, "")
        label = label_failure(check_record(task, item.bad_answer, bad))
        ok = good.passed and not bad.passed and not empty.passed and label is not None and label[0] == cause
        problems += 0 if ok else 1
        detail = "" if ok else (f" reference={'pass' if good.passed else 'FAIL: ' + '; '.join(good.reasons)[:240]}"
                                f" bad={'PASSED' if bad.passed else 'fail'} label={label[0] if label else None}"
                                f" ({label[1][:160] if label else ''})")
        log(f"{'ok  ' if ok else 'FAIL'} {task['id']} [{cause}]" + detail)
    return problems


def _real_scorer(suite_file: Path, server: str, ssh: str, key_file):
    """The evaluation harness's own scorer (knowledge-service Luau check + the server's Luau VM). No model call."""
    from types import SimpleNamespace
    from .eval_runner import DEFAULT_KEY_FILE, build_real, load_suite
    suite = load_suite(suite_file)
    args = SimpleNamespace(server=server, ssh=ssh, key_file=str(key_file or DEFAULT_KEY_FILE), model="star-fast",
                           mode="auto", packs="off", _suite=suite)
    _, _, scorer, _, _ = build_real(args)
    return suite, scorer


def load_selftest(folder: Path) -> list[Practice]:
    """Re-read a self-test folder written by `--selftest-out`."""
    files = sorted(Path(folder).glob("*.json"))
    if len(files) != 1:
        raise ValueError("a self-test folder holds exactly one task file")

    def read(rel: str) -> str:
        return (Path(folder) / rel).read_text(encoding="utf-8").replace("\r\n", "\n")
    return [Practice(task, read(task["auto"]["unit_test"]["file"]), read(f"reference/{task['id']}.md"),
                     read(f"reference/{task['id']}.bad.md"), task.get("spec", ""))
            for task in json.loads(files[0].read_text(encoding="utf-8"))]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m star.evals ledger")
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--suites", type=Path, default=DEFAULT_SUITES)
    sub = parser.add_subparsers(dest="command")
    practice = sub.add_parser("practice", help="write exercises targeting each recorded failure's cause (opt-in)")
    practice.add_argument("--results", type=Path, default=argparse.SUPPRESS)
    practice.add_argument("--suites", type=Path, default=argparse.SUPPRESS)
    practice.add_argument("--out", required=True, type=Path)
    practice.add_argument("--count", type=int, default=None, help="only the first N distinct failures")
    practice.add_argument("--per-failure", type=int, default=1)
    practice.add_argument("--leading-only", action="store_true", help="only the most frequent cause")
    practice.add_argument("--selftest-out", type=Path, default=None,
                          help="also write a self-test suite (with reference and bad answers) to this other folder")
    grow = sub.add_parser("pool", help="write the whole per-cause practice catalogue (or --total N of it)")
    grow.add_argument("--suites", type=Path, default=argparse.SUPPRESS)
    grow.add_argument("--out", required=True, type=Path)
    grow.add_argument("--total", type=int, default=None)
    grow.add_argument("--selftest-out", type=Path, default=None)
    check = sub.add_parser("verify", help="score a self-test folder with the real harness (Luau check + server VM)")
    check.add_argument("--dir", required=True, type=Path)
    check.add_argument("--server", default="", help="STAR Server URL (or STAR_EVAL_SERVER)")
    check.add_argument("--ssh", default="", help="user@host of the server's LXD host (or STAR_EVAL_SSH)")
    check.add_argument("--key-file", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            import os
            items = load_selftest(args.dir)
            suite_file = next(Path(args.dir).glob("*.json"))
            _, scorer = _real_scorer(suite_file, args.server or os.environ.get("STAR_EVAL_SERVER", ""),
                                     # the Luau VM may run on brain 2 (STAR_EVAL_SANDBOX_SSH): it only needs the luau binary
                                     args.ssh or os.environ.get("STAR_EVAL_SANDBOX_SSH", "")
                                     or os.environ.get("STAR_EVAL_SSH", ""), args.key_file)
            problems = verify(items, scorer)
            print(f"verify: {len(items)} tasks, " + ("all good" if not problems else f"{problems} problem(s)"))
            return 1 if problems else 0
        if args.command == "pool":
            items = practice_gen.pool(args.total)
            write_practice(items, args.out, suites=args.suites, selftest_dir=args.selftest_out)
            by_cause = Counter(i.task["targets_cause"] for i in items)
            print(f"Wrote {len(items)} practice tasks with runtime unit tests: "
                  + ", ".join(f"{c} {by_cause[c]}" for c in CAUSES if by_cause[c]))
            print(f"Night-school pool: {args.out.parent}")
            return 0
        failures = read_failures(args.results, args.suites)
        print(report_table(failures))
        if args.command == "practice":
            by_cause, items = generate_practice(failures, args.count, per_failure=args.per_failure,
                                                leading_only=args.leading_only)
            write_practice(items, args.out, suites=args.suites, selftest_dir=args.selftest_out)
            print(f"\nWrote {len(items)} independent practice tasks: "
                  + ", ".join(f"{c} {n}" for c, n in by_cause.items()))
            print(f"Night-school pool: {args.out.parent}")
        return 0
    except (ValueError, OSError, TypeError, StopIteration) as exc:
        print(f"ledger: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
