"""OMEGA Futuresight v1: evidence-led *test prediction* for Roblox source preflight.

Futuresight recommends concrete failure scenarios BEFORE deployment; it does not
predict every future crash, execute Luau, run Studio, or certify an application.
Static findings are kept distinct from unverified risk signals. Existing
preflight checks remain authoritative for what was actually checked.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3
from typing import Any

from .roblox_api_checker import _tokens
from .omega_hyperindex import HyperIndex

MAX_CASES = 32
MAX_UNCHECKED = 32
PRIOR_LIMIT = 2

# Each trigger is a known reason to *test*, never proof the code is broken.
_SOURCE_SCENARIOS = (
    ("OnServerEvent", "remote-inputs", "high",
     "Attempt unauthorized, negative, oversized, duplicate, and rapid RemoteEvent inputs in an isolated test place.",
     "Server authority must validate identity, permissions, ranges, and rate limits; client data never directly grants rewards."),
    ("OnServerInvoke", "remote-inputs", "high",
     "Invoke the RemoteFunction with malformed data, unauthorized identity, timeouts, and repeated requests.",
     "Untrusted client arguments must not bypass server authorization or cause unbounded execution."),
    ("UpdateAsync", "data-persistence", "medium",
     "Inject DataStore failures, duplicate updates, throttling, and two competing saves in a disposable test environment.",
     "Updates remain retry-safe and do not double award or overwrite newer data."),
    ("SetAsync", "data-persistence", "medium",
     "Inject DataStore write failure and competing saves; simulate player exit during a save.",
     "Failed and concurrent persistence operations do not silently corrupt durable state."),
    ("GetAsync", "data-persistence", "medium",
     "Inject slow, unavailable, and throttled DataStore reads; check default and retry behavior.",
     "A failed read does not destroy good data or incorrectly treat an unavailable response as an empty account."),
    ("TeleportAsync", "external-service", "medium",
     "Simulate TeleportService failure and a player leaving before the teleport completes.",
     "Failed teleports leave the player with safe state and a recoverable user-facing outcome."),
    ("CharacterAdded", "character-lifecycle", "medium",
     "Respawn repeatedly, with overlapping callbacks and character removal during initialization.",
     "Connections, state, and avatar references are cleaned up correctly across respawns."),
    ("PlayerRemoving", "player-lifecycle", "medium",
     "Disconnect during outstanding operations; check cleanup and persistence deadlines.",
     "Player cleanup cannot leave stale subscriptions or overwrite newer state."),
)

_DIAGNOSTIC_ACTIONS = (
    ("SEC-", "server-trust-diagnostic", "high",
     "Review the identified client-to-server trust path; exercise the failing input against an isolated server test.",
     "Authority and validation must be established on the server before state changes."),
    ("loop-without-yield", "loop-liveness", "high",
     "Run the flagged loop under an execution limit; test cancellation and worst-case iteration count.",
     "Server and client event loops must yield or terminate without exhausting execution time."),
    ("api:unknown", "api-compatibility", "medium",
     "Compare the flagged class/member with the current Roblox API dump and, if needed, Studio Script Analysis.",
     "The code uses a documented compatible API with the correct receiver type."),
    ("native-luau", "luau-analysis", "medium",
     "Verify the exact native Luau diagnostic and run applicable pure-Luau regression tests.",
     "The modified module passes available syntax and type checks."),
)

_GRAPH_ACTIONS = {
    "missing": ("missing-require", "high",
                "Resolve this require in a test place and verify the ModuleScript identity.",
                "The required module exists at runtime and returns its expected interface."),
    "cycles": ("require-cycle", "high",
               "Load the modules in an isolated place and check for circular initialization failures.",
               "Module loading terminates and exposes initialized exports."),
    "unresolved": ("dynamic-require", "medium",
                   "Inspect the dynamic or shadowed require target and verify it in Studio.",
                   "The selected require resolves to the intended ModuleScript at runtime."),
}
_PRIORITY = {"high": 0, "medium": 1, "low": 2}


def _case(file: str, line: int, category: str, priority: str, evidence_type: str,
          evidence: str, test: str, invariant: str) -> dict:
    identity = hashlib.sha256(f"{file}\n{line}\n{category}\n{evidence_type}".encode()).hexdigest()[:16]
    return {
        "id": identity, "file": file, "line": line, "category": category,
        "priority": priority, "evidence_type": evidence_type,
        "evidence": evidence[:260], "proposed_test": test,
        "expected_invariant": invariant, "status": "proposed-not-run",
        "proof_of_failure": False,
    }


def predict_preflight(
    sources: dict[str, tuple[str, str]],
    report: dict[str, Any],
    *, knowledge_root: str | Path | None = None,
    project: str | None = None,
) -> dict:
    """Bounded, deterministic plan; sources come from the same admitted preflight snapshot.

    No network, writes, code execution, or Studio access. If an existing
    reviewed KnowledgeStore was explicitly supplied, relevant historical fixes
    may be attached as untrusted reference text, never as direct instructions.
    """
    cases: list[dict] = []
    unchecked: list[dict] = []
    for entry in report.get("files", []):
        path = entry["file"]
        for reason in entry.get("unverified", []):
            unchecked.append({"file": path, "reason": str(reason)[:220]})
        for finding in entry.get("findings", []):
            rule = str(finding.get("rule", ""))
            action = next((x for x in _DIAGNOSTIC_ACTIONS if rule.startswith(x[0])), None)
            if action is None:
                continue
            _, category, priority, test, invariant = action
            line = int(finding.get("line", 1))
            cases.append(_case(
                path, max(1, line), category, priority, "preflight-diagnostic",
                f"{rule}: {finding.get('message', '')}", test, invariant,
            ))
        admitted = sources.get(path)
        if admitted is None:
            continue
        text, script_class = admitted
        # The existing Roblox API lexer drops comments and opaque string bodies.
        # A literal mention in a comment is not evidence of actual API usage.
        words: dict[str, int] = {}
        for token in _tokens(text):
            if token.kind == "word" and token.value not in words:
                words[token.value] = token.line
        for symbol, category, priority, test, invariant in _SOURCE_SCENARIOS:
            if symbol not in words:
                continue
            if category == "remote-inputs" and script_class != "Script":
                continue
            cases.append(_case(
                path, words[symbol], category, priority, "source-api-use",
                f"{symbol} appears in checked {script_class} source; this is a test trigger, not a confirmed defect.",
                test, invariant,
            ))

    graph = report.get("module_require_graph")
    if isinstance(graph, dict):
        for kind, (category, priority, test, invariant) in _GRAPH_ACTIONS.items():
            for entry in graph.get(kind, []):
                modules = entry.get("modules", [])
                file = str(entry.get("file") or (modules[0] if modules else "unknown"))
                line = int(entry.get("line", 1))
                evidence = (
                    f"Static require graph {kind}: " +
                    (", ".join(str(p) for p in modules) if modules else
                     str(entry.get("target", entry.get("reason", "unverified"))))
                )
                cases.append(_case(
                    file, max(1, line), category, priority,
                    "static-require-graph", evidence, test, invariant,
                ))

    # Deduplicate repeated findings without hiding distinct lines or evidence.
    unique: dict[str, dict] = {item["id"]: item for item in cases}
    ordered = sorted(unique.values(), key=lambda c: (
        _PRIORITY.get(c["priority"], 3), c["file"], c["line"], c["category"], c["id"]))
    truncated = len(ordered) > MAX_CASES
    planned = ordered[:MAX_CASES]
    memory_status = "not-requested"
    if knowledge_root is not None:
        if project is None or not project:
            memory_status = "missing-project-scope"
        else:
            try:
                with HyperIndex(knowledge_root) as index:
                    for candidate in planned[:8]:
                        query = candidate["category"].replace("-", " ") + " " + candidate["evidence"][:110]
                        result = index.search(project, query, limit=4)
                        candidate["historical_evidence"] = [
                            {
                                "note_id": hit["note_id"], "source": hit["source"],
                                "revision": hit["revision"], "text": hit["text"][:360],
                                "reviewed": True, "untrusted_as_instructions": True,
                            }
                            for hit in result["hits"] if hit["kind"] in ("fix", "pitfall", "correction")
                        ][:PRIOR_LIMIT]
                    memory_status = "reviewed-project-evidence-only"
            except (OSError, ValueError, sqlite3.DatabaseError):
                memory_status = "existing-knowledge-index-unavailable"

    return {
        "schema_version": 1,
        "method": "bounded-evidence-guided-test-selection",
        "status": ("suggestions" if planned else "no-scenarios-detected"),
        "source_coverage": report.get("coverage", "none"),
        "cases": planned, "total_candidates": len(ordered),
        "truncated": truncated,
        "unchecked": unchecked[:MAX_UNCHECKED],
        "unchecked_truncated": len(unchecked) > MAX_UNCHECKED,
        "knowledge": memory_status,
        "tests_executed": 0, "failures_proven": 0,
        "limitations": [
            "A test suggestion is NOT a detected bug or a calibrated failure probability.",
            "Static evidence cannot prove runtime behavior; run Luau, Studio, and multiplayer tests separately.",
            "Unsupported files, oversized sources, dynamic requires and unknown engine behavior remain unverified.",
            "Historical notes are project-reviewed references, not executable instructions.",
        ],
    }
