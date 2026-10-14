"""Regression corpus of repository-authored, intended-correct Roblox Luau.

All sources are read in place; no Luau is executed and no models are called.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re

import pytest

from star.luau_lint import Finding, lint
from star.luau_safety import inspect_safety
from star.luau_server_security import lint_server_trust
from star.roblox_api_checker import check_luau_api, load_api_dump

ROOT = Path(__file__).resolve().parents[1]
PACKS = (
    "roblox-datastore-service-patterns",
    "roblox-remote-event-function-patterns",
    "roblox-tweenservice-easing",
)
API_DUMP = ROOT / "tests/fixtures/roblox_api_small.json"

# (checker, repo-relative file or markdown#block, rule_id):
#   (verdict, reason). Values are evidence-reviewed, not broad exemptions.
# A new rule id, or an existing rule in a new file, fails until reviewed.
ALLOWLIST: dict[tuple[str, str, str], tuple[str, str]] = {}


def corpus() -> list[tuple[str, str, str]]:
    sources: list[tuple[str, str, str]] = []
    for parent in (ROOT / "examples/roblox", ROOT / "examples/roblox-templates"):
        for path in sorted(parent.rglob("*.luau")):
            if path.name.endswith(".spec.luau") or path.name == "run.luau":
                continue
            source = path.read_text(encoding="utf-8")
            kind = "Script" if path.name.endswith(".server.luau") else (
                "LocalScript" if path.name.endswith(".client.luau") else "ModuleScript")
            sources.append((path.relative_to(ROOT).as_posix(), source, kind))
    for pack in PACKS:
        path = ROOT / "star/skill_packs" / pack / "SKILL.md"
        body = path.read_text(encoding="utf-8")
        examples = re.findall(r"^~~~luau\n(.*?)\n~~~$", body, re.M | re.S)
        assert len(examples) == 3, pack
        for index, snippet in enumerate(examples, 1):
            sources.append((path.relative_to(ROOT).as_posix() + f"#luau-{index}",
                            snippet, "Script"))
    assert len(sources) >= 40, f"Corpus shrank to {len(sources)} snippets"
    assert len({path for path, _, _ in sources}) == len(sources)
    return sources


def findings(source: str, kind: str, dump) -> dict[str, list]:
    """Audit each independent checker and all enabled lint modes, excluding native CLI."""
    return {
        "luau_lint_all_modes": lint(source, external=False, safety_checks=True,
                                   script_class=kind, server_security=True),
        "luau_safety": inspect_safety(source, script_class=kind),
        "luau_server_security": lint_server_trust(source),
        "roblox_api_checker": check_luau_api(source, dump),
    }


def report(sources, dump):
    counts: Counter[str] = Counter()
    unexpected: list[tuple[str, str, int, str, str]] = []
    accepted: list[tuple[str, str, int, str, str, str]] = []
    for path, source, kind in sources:
        for checker, results in findings(source, kind, dump).items():
            counts[checker] += len(results)
            for row in results:
                key = (checker, path, row.rule_id)
                if key in ALLOWLIST:
                    verdict, reason = ALLOWLIST[key]
                    assert verdict in ("true_positive", "accepted_noise")
                    assert reason and len(reason) >= 12
                    accepted.append((checker, path, row.line, row.rule_id, verdict, reason))
                else:
                    unexpected.append((checker, path, row.line, row.rule_id, "unclassified"))
    return counts, accepted, unexpected


def test_known_good_corpus_has_no_unclassified_findings():
    sources = corpus()
    dump = load_api_dump(API_DUMP)
    counts, accepted, unexpected = report(sources, dump)
    print(f"corpus_count={len(sources)}")
    print("corpus_files=" + repr([name for name, _, _ in sources]))
    print("checker_finding_counts=" + repr(dict(sorted(counts.items()))))
    print("accepted=" + repr(accepted))
    assert not unexpected, (
        f"{len(unexpected)} unclassified findings across {len(sources)} sources:\n"
        + "\n".join(repr(item) for item in unexpected[:150]))
    assert all(key in {(checker, path, rule) for checker, path, _, rule, _, _
                       in accepted} for key in ALLOWLIST), "Stale allowlist entry"


def test_new_checker_diagnostic_cannot_pass_corpus_without_review(monkeypatch):
    """Demonstrate the rejection path: a newly firing rule is not silently accepted."""
    from star import luau_safety
    original = luau_safety.inspect_safety

    def injected(source, *, script_class=None):
        return original(source, script_class=script_class) + [
            Finding("unreviewed-new-rule", 1, "Synthetic control", "Remove the defect.", "warning")]
    monkeypatch.setattr(luau_safety, "inspect_safety", injected)
    samples = corpus()[:1]
    counts, accepted, unexpected = report(samples, load_api_dump(API_DUMP))
    assert counts["luau_safety"] >= 1
    assert any(row[3] == "unreviewed-new-rule" for row in unexpected)
