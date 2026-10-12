"""Offline evidence ledger and opt-in practice-task generator for stored STAR evaluation results.

Reads results already on disk. Never runs a model, calls a server, opens a holdout
suite, or changes the evaluation corpus.
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


@dataclass(frozen=True)
class Practice:
    task: dict
    test_body: str
    reference_answer: str  # For offline tests only; NEVER serialized to practice pool.


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


# Topic contexts come from catalog categories, never from golden prompt text.
CONTEXTS = (
    ("ui-", "a game menu's accessibility meter"),
    ("remote-", "a multiplayer ability's charge meter"),
    ("datastore-", "a persistent progression bar"),
    ("server-", "an inventory capacity indicator"),
    ("animation-", "a character movement blend meter"),
    ("rig-", "a character accessory's alignment meter"),
    ("tool-", "an equipped item's durability bar"),
    ("vfx-", "a visual effect's intensity meter"),
    ("performance", "a streaming zone's detail budget"),
    ("building-", "a modular construction budget"),
    ("engineering-", "a gameplay diagnostic's counter"),
    ("luau-", "a round-based scoreboard value"),
    ("economy-", "a shop's discount meter"),
    ("gameplay-", "a quest's progression meter"),
    ("npc-", "a pathfinding retry meter"),
)


def context_for(topic: str) -> str:
    return next((value for prefix, value in CONTEXTS if topic.startswith(prefix)),
                "a Roblox round's resource meter")


OPENINGS = {
    "wrong logic": "A boundary-case regression escaped the previous solution. Exercise the exact arithmetic.",
    "required feature missing": "A requested operation was omitted in the previous solution. Show every required step.",
    "self-check error left unrepaired": "A static-check failure was left unfixed. Submit a clean and complete module.",
    "answer cut off": "The prior reply was incomplete. Finish the full implementation and its module return.",
    "invented API name": "A nonexistent helper was used. Use only actual Luau math.floor and math.clamp functions.",
}

PRELUDE = """-- Self-contained practice harness; answer globals are restricted.
local emit = print
local function check(label, passed)
    emit("@@T\\t" .. (passed and "pass" or "fail") .. "\\t" .. label)
end
local function load_answer()
    local chunk, reason = loadstring(__SRC, "=practice")
    if not chunk then
        emit("@@LOADERR\\t" .. tostring(reason))
        error("answer did not load")
    end
    setfenv(chunk, { math = math, type = type, assert = assert })
    return chunk()
end
"""


def practice_for(source: Failure, index: int) -> Practice:
    """Create a new scenario from a bounded template and the failure's topic."""
    if source.cause not in OPENINGS:
        raise ValueError("unsupported failure cause")
    digest = hashlib.sha256((source.task_id + ":" + source.cause + ":" + source.topic).encode("utf-8")).hexdigest()
    task_id = "LEDGER-" + digest[:12].upper()
    name = f"boundResource{index + 1}"
    factor = 2 + index % 5
    minimum = index % 3
    maximum = 47 + index * 7
    prompt = (
        f"{OPENINGS[source.cause]} While working on {context_for(source.topic)}, "
        f"create a Luau ModuleScript returning a function named {name}(value: number): number. "
        f"Round value down with math.floor, multiply the integer by {factor}, then use math.clamp "
        f"to confine the output to [{minimum}, {maximum}]. Return the function itself. "
        "Provide exactly one finished fenced Luau code block."
    )
    task = {
        "id": task_id, "category": "targeted-practice", "difficulty": 1, "run_mode": "automated",
        "goal": f"Repair {source.cause} in {context_for(source.topic)}",
        "prompt": prompt,
        "required_evidence": ["one complete Luau function"],
        "pass_conditions": ["static Luau checking succeeds", "all four independent boundary checks pass",
                            "required arithmetic is present and nonexistent math helpers are absent"],
        "auto": {
            "compile_mode": "exact",
            "unit_test": {"file": f"tests/{task_id}.luau", "checks": 4},
            "require": [
                {"id": "round_down", "re": r"\bmath\s*\.\s*floor\s*\(", "why": "round using math.floor"},
                {"id": "limit_output", "re": r"\bmath\s*\.\s*clamp\s*\(", "why": "bound using math.clamp"},
            ],
            "forbid": [
                {"id": "no_imaginary_helper", "re": r"\bmath\s*\.\s*constrain\s*\(",
                 "why": "math.constrain is not a Luau API"},
            ],
        },
    }
    expected = f"math.clamp(4 * {factor}, {minimum}, {maximum})"
    body = (
        "local fn = load_answer()\n"
        'check("returns callable function", type(fn) == "function")\n'
        f'check("fractional input is floored", type(fn) == "function" and fn(4.9) == {expected})\n'
        f'check("lower bound", type(fn) == "function" and fn(-100) == {minimum})\n'
        f'check("upper bound", type(fn) == "function" and fn(1000) == {maximum})\n'
    )
    code = (f"local function {name}(value: number): number\n"
            f"    return math.clamp(math.floor(value) * {factor}, {minimum}, {maximum})\n"
            f"end\nreturn {name}")
    fence = chr(96) * 3
    return Practice(task, body, fence + "luau\n" + code + "\n" + fence)


def generate_practice(failures: list[Failure], count: int | None = None) -> tuple[str, list[Practice]]:
    """One new exercise per distinct failed task in the largest failure category."""
    cause = leading_cause(failures)
    sources = sorted((f for f in failures if f.cause == cause),
                     key=lambda f: (f.task_id, f.result_file))
    sources = list({f.task_id: f for f in reversed(sources)}.values())
    sources.sort(key=lambda f: f.task_id)
    if count is not None:
        if count < 1 or count > len(sources):
            raise ValueError(f"count must be between 1 and {len(sources)} distinct failures")
        sources = sources[:count]
    return cause, [practice_for(source, n) for n, source in enumerate(sources)]


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


def write_practice(items: list[Practice], out: Path, *, suites: Path = DEFAULT_SUITES) -> None:
    """Write opt-in night-school files, without modifying an evaluation file."""
    out = Path(out)
    if not items or out.suffix.lower() != ".json":
        raise ValueError("provide a nonempty practice list and a .json output filename")
    if any(part.casefold() == "evals" for part in out.parts) or re.search(r"golden|holdout", out.name, re.I):
        raise ValueError("refusing to write to the evaluation corpus")
    golden = _golden_prompts(Path(suites))
    for item in items:
        if any(overlaps_golden(item.task["prompt"], prompt) for prompt in golden):
            raise ValueError(f"practice prompt overlaps a golden task: {item.task['id']}")
    prelude = out.parent / "prelude.luau"
    test_files = [out.parent / item.task["auto"]["unit_test"]["file"] for item in items]
    if len(set(test_files)) != len(items) or len({x.task["id"] for x in items}) != len(items):
        raise ValueError("duplicate practice task identifier")
    for path in [out, *test_files]:
        if path.exists():
            raise FileExistsError(f"refusing to replace existing file: {path}")
    if prelude.exists() and prelude.read_text(encoding="utf-8") != PRELUDE:
        raise FileExistsError("existing practice prelude is different; use a new output folder")
    out.parent.mkdir(parents=True, exist_ok=True)
    (out.parent / "tests").mkdir(parents=True, exist_ok=True)
    if not prelude.exists():
        with prelude.open("x", encoding="utf-8") as stream:
            stream.write(PRELUDE)
    for path, item in zip(test_files, items):
        with path.open("x", encoding="utf-8") as stream:
            stream.write(item.test_body)
    with out.open("x", encoding="utf-8") as stream:
        json.dump([item.task for item in items], stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m star.evals ledger")
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--suites", type=Path, default=DEFAULT_SUITES)
    sub = parser.add_subparsers(dest="command")
    practice = sub.add_parser("practice", help="write exercises for the leading cause (opt-in)")
    practice.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    practice.add_argument("--suites", type=Path, default=DEFAULT_SUITES)
    practice.add_argument("--out", required=True, type=Path)
    practice.add_argument("--count", type=int, default=None)
    args = parser.parse_args(argv)
    try:
        failures = read_failures(args.results, args.suites)
        print(report_table(failures))
        if args.command == "practice":
            cause, items = generate_practice(failures, args.count)
            write_practice(items, args.out, suites=args.suites)
            print(f"\nWrote {len(items)} independent practice tasks for: {cause}")
            print(f"Night-school pool: {args.out.parent}")
        return 0
    except (ValueError, OSError, TypeError) as exc:
        print(f"ledger: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
