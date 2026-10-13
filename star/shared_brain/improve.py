"""Measured, reversible proposals over existing read-only knowledge primitives.

The host owns fixtures, source adapters, evaluation, code registration and review
actions. The model protocol exposes active retrieval, alias/recipe proposals and
candidate status. No candidate code is imported or executed. Journal hashes detect
damage; they are not authorization or signatures. Keep this store outside the
model's writable candidate worktree.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import inspect
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
from statistics import median
from time import perf_counter
from typing import Callable, Mapping, Sequence
from uuid import uuid4

from ..selfbuild import skill_path
from ..tool_workshop import SOURCES, _validate_recipe


MAX_JOURNAL_BYTES = 32_000_000
JOURNAL_CONTROL_RESERVE = 8192


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value) -> str:
    return sha256(_json(value).encode("utf-8")).hexdigest()


def _no_links(path: Path):
    """Check every existing ancestor before resolving, including junctions."""
    for item in (path.absolute(), *path.absolute().parents):
        try:
            # lstat exposes Windows reparse points even before is_junction()
            # was added in Python 3.12, without following the target.
            reparse = getattr(item.lstat(), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        except FileNotFoundError:
            reparse = 0
        if reparse or item.is_symlink() or (getattr(item, "is_junction", lambda: False)()):
            raise PermissionError("Shared improvement paths cannot follow symlinks or junctions")


@dataclass(frozen=True)
class Evidence:
    identifier: str
    source: str
    text: str
    trust: str = "extracted"


@dataclass(frozen=True)
class Fixture:
    identifier: str
    question: str
    expected_sources: tuple[str, ...]
    forbidden_sources: tuple[str, ...] = ()
    expected_tool_sources: tuple[str, ...] = ()
    expected_identifiers: tuple[str, ...] = ()
    # Exact (source, identifier) pairs for fixtures spanning multiple modules.
    expected_evidence: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Limits:
    context_chars: int = 8000
    latency_ms: float = 1000.0
    latency_ratio: float = 2.0
    context_ratio: float = 1.25
    repeats: int = 3
    minimum_latency_gain_ms: float = 1.0
    minimum_latency_gain_ratio: float = .10
    minimum_context_gain_chars: int = 32


Source = Callable[[str, int], Sequence[Evidence]]


class ImprovementLoop:
    """Host-controlled evaluation plus explicit owner review and rollback.

    `sources` contains adapters of already authorized ToolWorkshop sources;
    adapters must return bounded Evidence and must not execute generated code.
    The loop never discovers new sources, edits fixtures or approves workshop
    recipes/lessons. Active configurations are reference retrieval settings.
    """

    def __init__(self, home: Path, *, source_root: Path, source_files: Sequence[str],
                 cases: Sequence[Fixture], sources: Mapping[str, Source],
                 vocabulary: Sequence[str], baseline_recipe: dict | None = None,
                 limits: Limits = Limits(), clock=perf_counter):
        _no_links(Path(home))
        _no_links(Path(source_root))
        self.home = Path(home).resolve()
        self.root = Path(source_root).resolve(strict=True)
        self.project_digest = _digest({"selected_root": os.path.normcase(str(self.root))})
        self.files = tuple(sorted(set(source_files)))
        if not self.root.is_dir() or not self.files or len(self.files) > 2000:
            raise ValueError("An explicit bounded source manifest is required")
        raw_cases = tuple(cases)
        if not raw_cases or len(raw_cases) > 200 or any(not isinstance(c, Fixture) for c in raw_cases):
            raise ValueError("A fixed independent fixture suite is required")
        self.cases = tuple(Fixture(c.identifier, c.question, tuple(c.expected_sources), tuple(c.forbidden_sources),
                                   tuple(c.expected_tool_sources), tuple(c.expected_identifiers),
                                   tuple(tuple(pair) for pair in c.expected_evidence)) for c in raw_cases)
        if len({c.identifier for c in self.cases}) != len(self.cases):
            raise ValueError("Fixture IDs must be unique")
        for c in self.cases:
            if (not isinstance(c.identifier, str) or not 1 <= len(c.identifier) <= 100
                    or not isinstance(c.question, str) or not c.question or len(c.question) > 500
                    or any(not isinstance(i, str) or not 1 <= len(i) <= 300 for i in c.expected_identifiers)
                    or any(len(pair) != 2 or pair[0] not in self.files or not isinstance(pair[1], str)
                           or not 1 <= len(pair[1]) <= 300 for pair in c.expected_evidence)
                    or set(c.expected_sources + c.forbidden_sources) - set(self.files)):
                raise ValueError("Invalid fixture or fixture source outside the manifest")
        self.sources = dict(sources)
        if not self.sources or set(self.sources) - set(SOURCES) or any(not callable(f) for f in self.sources.values()):
            raise ValueError("Only configured read-only ToolWorkshop sources may be used")
        if any(set(c.expected_tool_sources) - set(self.sources) for c in self.cases):
            raise ValueError("Fixture tool sources must already be configured")
        self.vocabulary = frozenset(vocabulary)
        if any(not isinstance(t, str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", t) for t in self.vocabulary):
            raise ValueError("Vocabulary must contain normalized source tokens")
        if (type(limits.context_chars) is not int or not 256 <= limits.context_chars <= 12000
                or not 1 <= limits.repeats <= 9 or limits.latency_ms <= 0
                or limits.latency_ratio < 1 or limits.context_ratio < 1
                or limits.minimum_latency_gain_ms < 0 or not 0 <= limits.minimum_latency_gain_ratio <= 1
                or limits.minimum_context_gain_chars < 1
                or not all(math.isfinite(n) for n in (limits.latency_ms, limits.latency_ratio,
                                                      limits.context_ratio, limits.minimum_latency_gain_ms,
                                                      limits.minimum_latency_gain_ratio))):
            raise ValueError("Invalid independent evaluation limits")
        self.limits, self.clock = limits, clock
        self._verifier_files = {"controller": Path(__file__), "selfbuild": Path(inspect.getfile(skill_path)),
                                "tool_workshop": Path(inspect.getfile(_validate_recipe))}
        import importlib.util
        gate_spec = importlib.util.find_spec("star.eval_gate")
        if gate_spec is not None and gate_spec.origin:
            self._verifier_files["existing_eval_gate"] = Path(gate_spec.origin)
        self.verifier_digest = self._current_verifier_digest()
        self.suite_digest = self._current_suite_digest()
        self.home.mkdir(parents=True, exist_ok=True)
        self.journal = self.home / "improvements.jsonl"
        recipe = baseline_recipe or {"name": "baseline-retrieval", "description": "Existing source-backed project retrieval",
                                     "steps": [{"source": "graphify", "limit": 5}]}
        recipe = self._recipe(recipe)
        with self._session():
            if not self.events:
                snapshot = self._snapshot()
                config = {"aliases": {}, "recipe": recipe}
                version = "baseline-" + _digest({"config": config, "snapshot": snapshot})[:24]
                self._append("baseline", {"version": version, "config": config,
                                          "source_snapshot": snapshot, "suite_digest": self.suite_digest})
            elif self.events[0]["data"]["suite_digest"] != self.suite_digest:
                raise ValueError("Existing journal belongs to a different fixture suite/limits/vocabulary")

    def _current_suite_digest(self):
        return _digest({"schema": 1, "fixtures": [asdict(c) for c in self.cases],
                        "limits": asdict(self.limits), "vocabulary": sorted(self.vocabulary),
                        "configured_sources": sorted(self.sources), "verifier_digest": self.verifier_digest,
                        "project_digest": self.project_digest})

    def _current_verifier_digest(self):
        for path in self._verifier_files.values():
            _no_links(path)
        return _digest({name: sha256(path.read_bytes()).hexdigest() for name, path in self._verifier_files.items()})

    def _assert_suite(self):
        if self._current_verifier_digest() != self.verifier_digest:
            raise ValueError("Independent verifier code changed; create a new baseline")
        if self._current_suite_digest() != self.suite_digest:
            raise ValueError("Independent fixtures, limits or configured sources changed; create a new baseline")

    def _recipe(self, value: dict) -> dict:
        if not isinstance(value, dict) or set(value) != {"name", "description", "steps"}:
            raise ValueError("A recipe has exactly name, description and steps")
        result = _validate_recipe(value["name"], value["description"], value["steps"])
        if {s["source"] for s in result["steps"]} - set(self.sources):
            raise PermissionError("A recipe cannot acquire an unconfigured source")
        return result

    def _snapshot(self) -> dict:
        manifest = {}
        for name in self.files:
            if (not isinstance(name, str) or "\\" in name or name != PurePosixPath(name).as_posix()
                    or PurePosixPath(name).is_absolute() or any(p in {".", ".."} or p.startswith(".") for p in PurePosixPath(name).parts)):
                raise ValueError("Source paths must be explicit relative project paths")
            path = self.root / name
            _no_links(path)
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(self.root) or not resolved.is_file() or path.is_symlink():
                raise PermissionError("Source path left the selected project")
            if resolved.stat().st_size > 2_000_000:
                raise ValueError("Source exceeds snapshot size limit")
            with resolved.open("rb") as handle:
                content = handle.read(2_000_001)
            if len(content) > 2_000_000:
                raise ValueError("Source exceeds snapshot size limit")
            manifest[name] = sha256(content).hexdigest()
        return {"files": manifest, "project_digest": self.project_digest,
                "digest": _digest({"files": manifest, "project": self.project_digest})}

    @contextmanager
    def _session(self):
        # Refuse a changed store ancestor before creating even a lock file.
        _no_links(self.home)
        lock = self.home / ".improvements.lock"
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise RuntimeError("Improvement journal is in use; retry after the host operation finishes") from None
        os.close(fd)
        try:
            self._reload()
            self._assert_suite()
            yield
        finally:
            lock.unlink(missing_ok=True)

    def _reload(self):
        _no_links(self.home)
        _no_links(self.journal)
        self.events, self.candidates, self.versions = [], {}, {}
        self.active_version = None
        previous = "0" * 64
        if self.journal.exists():
            with self.journal.open("rb") as handle:
                raw = handle.read(MAX_JOURNAL_BYTES + 1)
            if len(raw) > MAX_JOURNAL_BYTES:
                raise ValueError("Improvement journal exceeds its bounded size")
            lines = raw.decode("utf-8").splitlines()
        else:
            lines = []
        for number, line in enumerate(lines):
            event = json.loads(line)
            if not isinstance(event, dict) or set(event) != {"sequence", "kind", "data", "previous", "digest"}:
                raise ValueError("Invalid improvement journal event")
            core = {k: event[k] for k in ("sequence", "kind", "data", "previous")}
            if core["sequence"] != number or core["previous"] != previous or event["digest"] != _digest(core):
                raise ValueError("Improvement journal integrity check failed")
            self.events.append(event)
            self._apply(event)
            previous = event["digest"]

    def _apply(self, event):
        kind, data = event["kind"], event["data"]
        if kind == "baseline":
            if len(self.events) != 1:
                raise ValueError("Baseline may only initialize the journal")
            self.versions[data["version"]] = {**data, "previous_version": None}
            self.active_version = data["version"]
        elif kind == "candidate":
            if data["id"] in self.candidates:
                raise ValueError("Duplicate candidate record")
            self.candidates[data["id"]] = {**data, "state": "candidate"}
        elif kind in {"evaluated", "reviewed", "active", "rolled_back"}:
            record = self.candidates[data["id"]]
            required = {"evaluated": "candidate", "reviewed": "evaluated", "active": "reviewed", "rolled_back": "active"}[kind]
            if record["state"] != required:
                raise ValueError("Invalid candidate state transition")
            record.update(data)
            record["state"] = kind
            if kind == "active":
                self.versions[data["id"]] = {"config": record["config"], "source_snapshot": record["source_snapshot"],
                                             "suite_digest": record["suite_digest"], "previous_version": data["previous_version"]}
                self.active_version = data["id"]
            elif kind == "rolled_back":
                self.active_version = data["target_version"]
        else:
            raise ValueError("Unknown improvement journal event")

    def _append(self, kind, data):
        core = {"sequence": len(self.events), "kind": kind, "data": data,
                "previous": self.events[-1]["digest"] if self.events else "0" * 64}
        event = {**core, "digest": _digest(core)}
        _no_links(self.home)
        _no_links(self.journal)
        encoded = (_json(event) + "\n").encode("utf-8")
        size = self.journal.stat().st_size if self.journal.exists() else 0
        cap = MAX_JOURNAL_BYTES - (JOURNAL_CONTROL_RESERVE if kind in {"candidate", "evaluated"} else 0)
        if size + len(encoded) > cap:
            raise ValueError("Improvement journal budget exhausted; host must archive or start a new baseline")
        with self.journal.open("ab") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        self.events.append(event)
        self._apply(event)

    def _candidate(self, kind: str, config: dict, extra: dict | None = None) -> dict:
        record = {"id": uuid4().hex, "kind": kind, "config": config,
                  "config_digest": _digest(config), "base_version": self.active_version,
                  "source_snapshot": self._snapshot(), "suite_digest": self.suite_digest, **(extra or {})}
        self._append("candidate", record)
        return json.loads(_json(self.candidates[record["id"]]))

    def propose_aliases(self, aliases: dict[str, Sequence[str]]) -> dict:
        """Model-facing proposal; expansion targets must be source vocabulary."""
        if not isinstance(aliases, dict) or not 1 <= len(aliases) <= 12:
            raise ValueError("An alias proposal contains 1..12 bounded aliases")
        normalized = {}
        for key, terms in aliases.items():
            if (not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", key)
                    or not isinstance(terms, (tuple, list)) or not 1 <= len(terms) <= 3
                    or any(not isinstance(t, str) or t not in self.vocabulary for t in terms)):
                raise ValueError("Alias targets must be bounded tokens from the selected source vocabulary")
            normalized[key] = sorted(set(terms))
        with self._session():
            config = json.loads(_json(self.versions[self.active_version]["config"]))
            config["aliases"] = normalized
            return self._candidate("knowledge_alias", config)

    def propose_recipe(self, recipe: dict) -> dict:
        """Model-facing proposal of a validated read-only ToolWorkshop recipe."""
        recipe = self._recipe(recipe)
        with self._session():
            config = json.loads(_json(self.versions[self.active_version]["config"]))
            config["recipe"] = recipe
            return self._candidate("recipe", config)

    def register_code(self, *, path: str, source: str, commit: str) -> dict:
        """Record a scoped selfbuild candidate; never load or execute it."""
        if (not skill_path(path) or not isinstance(source, str) or len(source) > 40000
                or not isinstance(commit, str) or not re.fullmatch(r"[a-f0-9]{40}", commit)):
            raise ValueError("Code registration needs a scoped selfbuild path, bounded source and Git commit")
        if path.endswith(".py"):
            compile(source, path, "exec")
        with self._session():
            config = json.loads(_json(self.versions[self.active_version]["config"]))
            return self._candidate("code", config, {"path": path, "commit": commit,
                                                     "source_digest": sha256(source.encode("utf-8")).hexdigest(),
                                                     "verification": "syntax only; behavior not executed or verified"})

    def _retrieve_config(self, config: dict, question: str, version: str) -> dict:
        started = self.clock()
        if not isinstance(question, str) or not 1 <= len(question.strip()) <= 500:
            raise ValueError("Retrieval questions contain 1..500 characters")
        words = set(re.findall(r"[a-z0-9_]+", question.lower()))
        expansion = sorted({t for k, terms in config["aliases"].items() if k in words for t in terms})
        query = question + (" " + " ".join(expansion) if expansion else "")
        records, seen, errors = [], set(), []
        for step in config["recipe"]["steps"]:
            try:
                returned = self.sources[step["source"]](query, step["limit"])
                if not isinstance(returned, (tuple, list)) or len(returned) > 100:
                    raise ValueError("A read-only adapter must return bounded Evidence records")
                for evidence in returned[:step["limit"]]:
                    if (not isinstance(evidence, Evidence) or evidence.source not in self.files
                            or evidence.trust not in {"extracted", "reviewed_reference"}
                            or not all(isinstance(s, str) for s in (evidence.identifier, evidence.source, evidence.text))
                            or not evidence.identifier or len(evidence.identifier) > 300 or len(evidence.text) > 12000):
                        raise ValueError("An adapter returned unsupported, stale or unverified evidence")
                    key = (evidence.identifier, evidence.source)
                    if key not in seen:
                        seen.add(key)
                        item = asdict(evidence)
                        records.append(item)
            except Exception as exc:
                # No source contents, exception strings or credentials enter the journal.
                errors.append({"source": step["source"], "type": type(exc).__name__})
        response = {"query": query, "records": records, "errors": errors,
                    "active_version": version, "untrusted": True, "latency_ms": 0.0,
                    "context_chars": 0}
        # Bound the complete serialized interface response, including provenance,
        # errors and metadata. Omitted evidence cannot satisfy a fixture.
        while True:
            response["context_chars"] = len(_json(response))
            response["context_chars"] = len(_json(response))
            if response["context_chars"] <= self.limits.context_chars:
                break
            if records:
                records.pop()
            else:
                raise ValueError("Query/metadata exceeds the configured retrieval budget")
        elapsed = (self.clock() - started) * 1000
        if not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError("Invalid host benchmark clock")
        response["latency_ms"] = round(elapsed, 6)
        while True:
            response["context_chars"] = len(_json(response))
            response["context_chars"] = len(_json(response))
            if response["context_chars"] <= self.limits.context_chars:
                break
            if records:
                records.pop()
            else:
                raise ValueError("Query/metadata exceeds the configured retrieval budget")
        response["context_chars"] = len(_json(response))
        return response

    def _run_case(self, config: dict, fixture: Fixture, version: str) -> dict:
        response = self._retrieve_config(config, fixture.question, version)
        found = {r["source"] for r in response["records"]}
        found_ids = {r["identifier"] for r in response["records"]}
        found_evidence = {(r["source"], r["identifier"]) for r in response["records"]}
        # Independent sets allow a decoy on the expected source and the right
        # identifier on another source to falsely satisfy a fixture. When a
        # source is specified, its expected identifiers must come from it.
        scoped_ids = ({identifier for source, identifier in found_evidence if source in fixture.expected_sources}
                      if fixture.expected_sources else found_ids)
        errors = response["errors"]
        correct = (set(fixture.expected_sources) <= found and not set(fixture.forbidden_sources) & found
                   and set(fixture.expected_identifiers) <= scoped_ids
                   and set(fixture.expected_evidence) <= found_evidence
                   and (bool(fixture.expected_sources or fixture.expected_identifiers or fixture.expected_evidence)
                        or not found) and not errors)
        ran_sources = {step["source"] for step in config["recipe"]["steps"]}
        tool_success = not errors and (not fixture.expected_tool_sources or
                                       (set(fixture.expected_tool_sources) <= ran_sources and correct))
        return {"correct": correct, "tool_success": tool_success, "context_chars": response["context_chars"],
                "latency_ms": response["latency_ms"], "sources": sorted(found), "identifiers": sorted(found_ids),
                "evidence": [{"source": source, "identifier": identifier} for source, identifier in sorted(found_evidence)],
                "errors": errors}

    def retrieve(self, question: str) -> dict:
        """Public bounded retrieval uses only the currently active version."""
        with self._session():
            active = self.versions[self.active_version]
            if self._snapshot() != active["source_snapshot"]:
                raise RuntimeError("Active retrieval sources are stale; evaluate a fresh proposal")
            response = self._retrieve_config(active["config"], question, self.active_version)
            if self._snapshot() != active["source_snapshot"]:
                raise RuntimeError("Sources changed during retrieval")
            return response

    def evaluate(self, identifier: str) -> dict:
        """Run fixed independent fixtures; candidates cannot supply their scores."""
        with self._session():
            record = self.candidates[identifier]
            if record["state"] != "candidate" or record["kind"] == "code":
                raise PermissionError("Only unevaluated retrieval/recipe candidates may be benchmarked")
            if record["base_version"] != self.active_version or self._snapshot() != record["source_snapshot"]:
                raise RuntimeError("Candidate baseline or source snapshot changed; propose again")
            base = self.versions[self.active_version]["config"]
            before, after = {}, {}
            for fixture in self.cases:
                pair = [[], []]
                for iteration in range(self.limits.repeats):
                    order = (0, 1) if iteration % 2 == 0 else (1, 0)
                    for side in order:
                        pair[side].append(self._run_case(base if side == 0 else record["config"], fixture,
                                                        self.active_version if side == 0 else record["id"]))
                for target, samples in ((before, pair[0]), (after, pair[1])):
                    target[fixture.identifier] = {"correct": all(s["correct"] for s in samples),
                                                  "tool_success": all(s["tool_success"] for s in samples),
                                                  "context_chars": max(s["context_chars"] for s in samples),
                                                  "latency_ms": round(median(s["latency_ms"] for s in samples), 6),
                                                  "sources": samples[-1]["sources"],
                                                  "identifiers": samples[-1]["identifiers"],
                                                  "evidence": samples[-1]["evidence"],
                                                  "errors": [e for s in samples for e in s["errors"]]}
            if self._snapshot() != record["source_snapshot"]:
                raise RuntimeError("Sources changed during evaluation; no verdict recorded")
            self._assert_suite()
            reasons, wins = self._compare(before, after)
            # Claude owns this optional trusted comparison API. Reuse it when
            # integrated, then enforce the stricter local metrics below too.
            import importlib.util
            existing_gate = None
            if importlib.util.find_spec("star.eval_gate") is not None:
                from ..eval_gate import evaluate_change
                gate_input = lambda scores: {"suite": {"sha256": self.suite_digest},
                                              "tasks": {tid: {"status": "error" if s["errors"] else
                                                               "pass" if s["correct"] else "fail"}
                                                        for tid, s in scores.items()}}
                verdict = evaluate_change(gate_input(before), gate_input(after), allow_partial=False)
                existing_gate = verdict.to_dict()
                if not verdict.allowed:
                    reasons.append("Existing independent correctness gate refused this change")
            evaluation = {"candidate": identifier, "config_digest": record["config_digest"],
                          "base_version": self.active_version, "suite_digest": self.suite_digest,
                          "source_digest": record["source_snapshot"]["digest"], "baseline": before, "candidate_results": after,
                          "allowed": not reasons and bool(wins), "reasons": reasons, "wins": wins, "existing_gate": existing_gate,
                          "measurement": "median read-only adapters and context assembly time, excluding journal/snapshot overhead; context is serialized response characters, not tokenizer tokens"}
            if not reasons and not wins:
                evaluation["reasons"] = ["No measurable improvement"]
            self._append("evaluated", {"id": identifier, "evaluation": evaluation,
                                       "evaluation_digest": _digest(evaluation)})
            return json.loads(_json(self.candidates[identifier]))

    def _compare(self, before, after):
        reasons, wins = [], []
        ids = {f.identifier for f in self.cases}
        if set(before) != ids or set(after) != ids:
            return ["Incomplete or mismatched independent fixture IDs"], []
        for tid in sorted(ids):
            b, c = before[tid], after[tid]
            if b["errors"]:
                reasons.append(tid + ": baseline source failure makes comparison incomplete")
            if c["errors"]:
                reasons.append(tid + ": source failure makes evaluation incomplete")
            for metric in ("correct", "tool_success"):
                if b[metric] and not c[metric]:
                    reasons.append(tid + ": " + metric + " regressed")
                elif not b[metric] and c[metric]:
                    wins.append(tid + ": " + metric + " improved")
            if c["context_chars"] > self.limits.context_chars or c["context_chars"] > max(256, b["context_chars"]) * self.limits.context_ratio:
                reasons.append(tid + ": context cap exceeded")
            if c["latency_ms"] > self.limits.latency_ms or c["latency_ms"] > max(1., b["latency_ms"]) * self.limits.latency_ratio:
                reasons.append(tid + ": latency cap exceeded")
            # Returning less evidence quickly is useful only when the candidate
            # actually answers this independent fixture and its tool succeeds.
            if c["correct"] and c["tool_success"]:
                if b["context_chars"] - c["context_chars"] >= self.limits.minimum_context_gain_chars:
                    wins.append(tid + ": context reduced")
                if (b["latency_ms"] - c["latency_ms"] >= self.limits.minimum_latency_gain_ms
                        and c["latency_ms"] <= b["latency_ms"] * (1 - self.limits.minimum_latency_gain_ratio)):
                    wins.append(tid + ": retrieval latency reduced")
        return reasons, wins

    @staticmethod
    def _human(human_approved, reviewer):
        if human_approved is not True or not isinstance(reviewer, str) or not 1 <= len(reviewer.strip()) <= 100:
            raise PermissionError("Separate explicit owner-controlled review is required")

    def _promotion_record(self, identifier, evaluation_digest, state):
        record = self.candidates[identifier]
        if (record["state"] != state or not record.get("evaluation", {}).get("allowed")
                or record.get("evaluation_digest") != evaluation_digest
                or _digest(record["evaluation"]) != evaluation_digest
                or record["suite_digest"] != self.suite_digest
                or _digest(record["config"]) != record["config_digest"]
                or record["base_version"] != self.active_version
                or self._snapshot() != record["source_snapshot"]):
            raise PermissionError("Promotion needs matching verified evidence and unchanged sources/baseline")
        return record

    def review(self, identifier: str, *, evaluation_digest: str, human_approved: bool = False,
               reviewer: str = "") -> dict:
        self._human(human_approved, reviewer)
        with self._session():
            self._promotion_record(identifier, evaluation_digest, "evaluated")
            self._append("reviewed", {"id": identifier, "reviewer": reviewer.strip(), "reviewed_digest": evaluation_digest})
            return json.loads(_json(self.candidates[identifier]))

    def activate(self, identifier: str, *, evaluation_digest: str, human_approved: bool = False,
                 reviewer: str = "") -> dict:
        self._human(human_approved, reviewer)
        with self._session():
            record = self._promotion_record(identifier, evaluation_digest, "reviewed")
            if record["reviewed_digest"] != evaluation_digest:
                raise PermissionError("Reviewed evaluation changed")
            self._append("active", {"id": identifier, "previous_version": self.active_version,
                                     "activated_by": reviewer.strip()})
            return {"active_version": self.active_version, "previous_version": self.versions[identifier]["previous_version"]}

    def rollback(self, *, expected_version: str, human_approved: bool = False, reviewer: str = "") -> dict:
        self._human(human_approved, reviewer)
        with self._session():
            if expected_version != self.active_version or expected_version not in self.candidates:
                raise PermissionError("Rollback must name the currently active candidate version")
            target = self.versions[expected_version]["previous_version"]
            if (target not in self.versions or self._snapshot() != self.versions[target]["source_snapshot"]
                    or self.versions[target]["suite_digest"] != self.suite_digest):
                raise PermissionError("Prior version sources changed; evaluate a fresh proposal")
            self._append("rolled_back", {"id": expected_version, "target_version": target, "rolled_back_by": reviewer.strip()})
            return {"active_version": self.active_version, "rolled_back_version": expected_version}

    def status(self) -> dict:
        with self._session():
            return {"active_version": self.active_version,
                    "config": json.loads(_json(self.versions[self.active_version]["config"])),
                    "candidates": {k: v["state"] for k, v in self.candidates.items()},
                    "suite_digest": self.suite_digest, "journal_events": len(self.events)}
