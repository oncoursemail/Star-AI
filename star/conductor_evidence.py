"""Default-off cross-provider evidence contracts for the STAR 2.0 Conductor pilot.

This module NEVER runs tools, connects models, grants permissions, accepts an
agent's own test claims as proof, writes learned facts or updates model weights.
A trusted host must construct host_tool receipts from actual allowlisted
tool invocations; NEVER trust a model-supplied JSON field that claims to be a
host receipt. Eligibility means ready for independent human/paired-eval
review, not reviewed, promoted, or correct.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_SHA = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_CHECK_TYPES = frozenset({"tests", "typecheck", "lint", "security", "native_studio", "visual"})
_TRANSPORTS = frozenset({"local", "lan", "cloud_api", "coding_agent", "remote_agent"})
_CHECK_STATUSES = frozenset({"passed", "failed", "skipped", "error"})
_PROVENANCE = frozenset({"host_tool", "model_claim"})
_TASK_STATUSES = frozenset({"completed", "failed", "cancelled", "incomplete"})


def _check_id(value: str, field: str) -> None:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise ValueError(f"Invalid {field} identifier")


def _check_sha(value: str, field: str, *, source: bool = False) -> None:
    pattern = _SOURCE_SHA if source else _SHA256
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise ValueError(f"Invalid {field} digest")


def _check_choice(value: str, choices: frozenset[str], field: str) -> None:
    if type(value) is not str or value not in choices:
        raise ValueError(f"Invalid {field} value")


@dataclass(frozen=True, slots=True)
class CheckEvidence:
    """A single report tied to a specific project, source revision and artifact.

    Provenance is assigned by the trusted application, NOT from model output.
    Report bytes stay in the authorized local store, under the report digest.
    """

    name: Literal["tests", "typecheck", "lint", "security", "native_studio", "visual"]
    status: Literal["passed", "failed", "skipped", "error"]
    provenance: Literal["host_tool", "model_claim"]
    verifier_id: str
    project_id: str
    source_sha: str
    artifact_sha256: str
    report_sha256: str

    def __post_init__(self) -> None:
        _check_choice(self.name, _CHECK_TYPES, "check name")
        _check_choice(self.status, _CHECK_STATUSES, "check status")
        _check_choice(self.provenance, _PROVENANCE, "check provenance")
        for field in ("verifier_id", "project_id"):
            _check_id(getattr(self, field), field)
        _check_sha(self.source_sha, "source", source=True)
        _check_sha(self.artifact_sha256, "artifact")
        _check_sha(self.report_sha256, "report")


@dataclass(frozen=True, slots=True)
class TaskEvidence:
    """No raw prompts, secrets, user content or third-party hidden reasoning."""

    mission_id: str
    project_id: str
    task_id: str
    worker_id: str
    provider_id: str
    transport: Literal["local", "lan", "cloud_api", "coding_agent", "remote_agent"]
    model_id: str
    status: Literal["completed", "failed", "cancelled", "incomplete"]
    source_sha: str
    artifact_sha256: str
    checks: tuple[CheckEvidence, ...] = ()

    def __post_init__(self) -> None:
        for field in ("mission_id", "project_id", "task_id", "worker_id", "provider_id"):
            _check_id(getattr(self, field), field)
        _check_choice(self.transport, _TRANSPORTS, "transport")
        _check_choice(self.status, _TASK_STATUSES, "task status")
        # A model ID is metadata, never a URL, command, key or execution instruction.
        if (type(self.model_id) is not str or not 1 <= len(self.model_id) <= 120
                or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/+\-]{0,119}", self.model_id) is None):
            raise ValueError("Invalid model identifier")
        _check_sha(self.source_sha, "source", source=True)
        _check_sha(self.artifact_sha256, "artifact")
        if type(self.checks) is not tuple or len(self.checks) > 24:
            raise ValueError("Check evidence must be a bounded tuple")
        if not all(isinstance(c, CheckEvidence) for c in self.checks):
            raise ValueError("Every check must use CheckEvidence")


@dataclass(frozen=True, slots=True)
class LearningReadiness:
    """A gate output; NEVER a command to import or activate a lesson."""

    eligible_for_review: bool
    reason: str
    verified_checks: tuple[str, ...] = ()


def assess_learning_readiness(
    task: TaskEvidence, *,
    expected_project: str,
    required_checks: tuple[str, ...] = ("tests",),
) -> LearningReadiness:
    """Check whether a completed artifact has host-observed evidence for review.

    This does not verify cryptographic provenance or trust arbitrary objects:
    trusted application code must collect independent checker results itself.
    A candidate must still pass STAR's separate sealed evaluation/owner gate.
    """
    _check_id(expected_project, "expected_project")
    if (type(required_checks) is not tuple or not required_checks
            or len(required_checks) > len(_CHECK_TYPES)
            or any(type(name) is not str or name not in _CHECK_TYPES for name in required_checks)
            or len(set(required_checks)) != len(required_checks)):
        raise ValueError("Choose unique known required checks")
    if not isinstance(task, TaskEvidence):
        raise TypeError("Expected TaskEvidence")
    if task.project_id != expected_project:
        return LearningReadiness(False, "Project scope mismatch")
    if task.status != "completed":
        return LearningReadiness(False, "Task is not completed")

    observed: set[str] = set()
    for check in task.checks:
        if (check.project_id != task.project_id or check.source_sha != task.source_sha
                or check.artifact_sha256 != task.artifact_sha256):
            return LearningReadiness(False, "Check source, artifact, or project mismatch")
        # Agent claims can be logged, but never become pass/fail verification.
        if check.provenance != "host_tool":
            continue
        if check.verifier_id == task.worker_id:
            return LearningReadiness(False, "Worker cannot independently verify itself")
        if check.status in ("failed", "error"):
            return LearningReadiness(False, "Independent check failed")
        if check.status == "passed":
            observed.add(check.name)

    if not set(required_checks).issubset(observed):
        return LearningReadiness(False, "Required independent check is missing")
    return LearningReadiness(True, "Host-observed candidate; independent owner/eval review still required",
                             tuple(sorted(observed)))
