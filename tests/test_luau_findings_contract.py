"""Dynamic, real-checker contract for every offline Luau rule ID."""
from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from star.luau_lint import lint
from star.luau_safety import inspect_safety
from star.luau_server_security import lint_server_trust
from star.roblox_api_checker import check_luau_api, load_api_dump

ROOT = Path(__file__).resolve().parents[1]
CHECKERS = {
    "lint": ROOT / "star/luau_lint.py",
    "safety": ROOT / "star/luau_safety.py",
    "security": ROOT / "star/luau_server_security.py",
    "api": ROOT / "star/roblox_api_checker.py",
}
KNOWN_LEGACY_ALIASES = {
    "loop-without-yield", "instance-parent-argument", "deprecated-task-global",
}
RULE_FORMAT = re.compile(r"(?:[a-z][a-z0-9]*(?:-[a-z0-9]+)+|SEC-[A-Z]+(?:-[A-Z]+)+)\Z")
DOC_PATH = ROOT / "docs/agents/luau-findings-contract.md"


def source_tree(path: Path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def extracted_ids(path: Path) -> set[str]:
    """Read rule declarations, never a manually maintained registry."""
    rules: set[str] = set()
    for node in ast.walk(source_tree(path)):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", None)
            if name in {"add", "Finding", "ApiFinding"} and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    rules.add(arg.value)
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Tuple):
            for target in node.targets:
                if isinstance(target, ast.Tuple):
                    for index, member in enumerate(target.elts):
                        if (isinstance(member, ast.Name) and member.id == "rule"
                                and index < len(node.value.elts)):
                            item = node.value.elts[index]
                            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                                rules.add(item.value)
    return rules


def annotated_rows() -> set[str]:
    body = DOC_PATH.read_text(encoding="utf-8")
    return set(re.findall(r"^\| `([^\x60]+)` \|", body, re.M))


def _assignment(path: Path, name: str):
    for node in source_tree(path).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == name
                for target in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"Missing static fixture {name} in {path.name}")


def _cases(path: Path, fn: str):
    for node in source_tree(path).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == fn:
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call) and decorator.args and (
                        isinstance(decorator.func, ast.Attribute)
                        and decorator.func.attr == "parametrize"):
                    return ast.literal_eval(decorator.args[1])
    raise AssertionError(f"Missing parametrize fixture in {path.name}")


def real_observations():
    """Exercise the actual analyzers with their original positive test cases."""
    results = defaultdict(list)
    for rule, bad, good in _cases(ROOT / "tests/test_luau_lint.py", "test_positive_and_negative"):
        rows = [f for f in lint(bad, external=False) if f.rule_id == rule]
        assert rows, f"Lint positive fixture stopped firing: {rule}"
        results[("lint", rule)].extend(rows)
    safety = _assignment(ROOT / "tests/test_luau_safety.py", "CASES")
    for rule, group in safety.items():
        kind = "Script" if rule == "server-waitforchild-chain" else None
        rows = [f for f in inspect_safety(group["bad"][0], script_class=kind)
                if f.rule_id == rule]
        assert rows, f"Safety positive fixture stopped firing: {rule}"
        results[("safety", rule)].extend(rows)
    security = _assignment(ROOT / "tests/test_luau_server_security.py", "CASES")
    for rule, bad, safe in security:
        rows = [f for f in lint_server_trust(bad) if f.rule_id == rule]
        assert rows, f"Server security positive fixture stopped firing: {rule}"
        results[("security", rule)].extend(rows)
    api = load_api_dump(ROOT / "tests/fixtures/roblox_api_small.json")
    for source, rule, name, suggestion, line in _cases(
            ROOT / "tests/test_roblox_api_checker.py",
            "test_wrong_names_produce_exact_diagnostics"):
        rows = [f for f in check_luau_api(source, api) if f.rule_id == rule]
        assert rows, f"API positive fixture stopped firing: {rule}"
        results[("api", rule)].extend(rows)
    return results


def violations(row):
    problems = []
    if row.severity not in {"error", "warning", "review"}:
        problems.append("severity")
    if not isinstance(row.message, str) or not 1 <= len(row.message) <= 160:
        problems.append("message")
    if not isinstance(row.suggested_fix, str) or not row.suggested_fix.strip():
        problems.append("fix")
    if type(row.line) is not int or row.line < 1:
        problems.append("line")
    return problems


def test_source_derived_ids_docs_firing_tests_and_finding_contract():
    extracted = {name: extracted_ids(path) for name, path in CHECKERS.items()}
    assert all(extracted.values()), extracted
    all_ids = set.union(*extracted.values())
    assert all(RULE_FORMAT.fullmatch(rule) for rule in all_ids)
    seen = defaultdict(set)
    for owner, ids in extracted.items():
        for rule in ids:
            seen[rule].add(owner)
    duplicated = {rule for rule, owners in seen.items() if len(owners) > 1}
    assert duplicated == KNOWN_LEGACY_ALIASES, duplicated
    assert annotated_rows() == all_ids, {
        "undocumented": sorted(all_ids - annotated_rows()),
        "stale_docs": sorted(annotated_rows() - all_ids),
    }
    results = real_observations()
    assert set(results) == {(owner, rule) for owner, ids in extracted.items()
                            for rule in ids}, {
        "unfired": sorted({(owner, rule) for owner, ids in extracted.items()
                           for rule in ids} - set(results)),
    }
    for (owner, rule), findings in results.items():
        for row in findings:
            assert row.rule_id == rule
            assert not violations(row), (owner, rule, violations(row))
    print("module_rule_counts=" + repr({k: len(v) for k, v in extracted.items()}))
    print(f"unique_rules={len(all_ids)}; documented={len(annotated_rows())}; "
          f"firing_module_rule_pairs={len(results)}; contract_gaps=0")


@pytest.mark.parametrize("defect", ["severity", "message", "fix", "line"])
def test_contract_rejects_broken_finding_metadata(defect):
    record = dict(severity="warning", message="An actionable diagnostic.",
                  suggested_fix="Review the rule and adjust the source.", line=1)
    if defect == "severity":
        record["severity"] = "unknown"
    elif defect == "message":
        record["message"] = "x" * 161
    elif defect == "fix":
        record["suggested_fix"] = " "
    else:
        record["line"] = 0
    assert defect in violations(SimpleNamespace(**record))


def test_new_rule_id_without_docs_or_a_firing_fixture_is_rejected():
    ids = set().union(*(extracted_ids(p) for p in CHECKERS.values()))
    hypothetical = "new-rule-needs-evidence"
    assert hypothetical not in ids
    assert hypothetical not in annotated_rows()
    assert hypothetical not in {rule for _, rule in real_observations()}
