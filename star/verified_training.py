"""Curate verified, rights-reviewed Luau learning examples for *optional* LoRA.

A model's text saying "tests passed" is never evidence. Test receipts must be
supplied by the independent, trusted application host, never by the candidate
model or user-supplied untrusted task JSON. No GPU training is launched here.
All output is a private, explicitly approved training candidate.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Mapping

MAX_EXAMPLES = 5000
MAX_TEXT = 8000
_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")
_ORIGINS = frozenset({"owner_original", "star_generated", "approved_open_source"})
_LICENSES = frozenset({"owned-original", "CC0-1.0", "MIT", "Apache-2.0", "BSD-3-Clause"})
_EXECUTORS = frozenset({"studio_lab", "roblox_cloud", "isolated_luau_sandbox"})
_SECRET = re.compile(r"(?i)(?:-----BEGIN .*?PRIVATE KEY-----|"
                     r"\b(?:api[_-]?key|password|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9_-]{12,}|"
                     r"sk-[A-Za-z0-9_-]{20,})")
_DENIED_PATH = re.compile(r"(?i)(?:^|/)(?:evals?|holdouts?|fixtures?|golden|\.git|\.env)(?:/|$)")


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Example:
    id: str
    project: str
    prompt: str
    answer: str
    origin: str
    license: str
    model: str
    source_path: str = ""
    rights_reviewed: bool = False
    owner_consented: bool = False

    def validate(self):
        if any(not isinstance(x, str) or not _ID.fullmatch(x) for x in (self.id, self.project)):
            raise ValueError("Invalid example identity")
        if (type(self.prompt) is not str or type(self.answer) is not str
                or not 12 <= len(self.prompt) <= MAX_TEXT
                or not 10 <= len(self.answer) <= MAX_TEXT):
            raise ValueError("Invalid example prompt/answer length")
        if (self.origin not in _ORIGINS or self.license not in _LICENSES
                or type(self.rights_reviewed) is not bool or not self.rights_reviewed
                or type(self.owner_consented) is not bool or not self.owner_consented):
            raise PermissionError("Training requires explicit owner consent and source-rights review")
        if not isinstance(self.model, str) or not 2 <= len(self.model) <= 180:
            raise ValueError("Model identity is required for provenance")
        if (type(self.source_path) is not str or len(self.source_path) > 240
                or _DENIED_PATH.search(self.source_path.replace("\\", "/"))):
            raise PermissionError("Evaluation, private or unknown source locations are excluded")
        if _SECRET.search(self.prompt) or _SECRET.search(self.answer):
            raise PermissionError("Potential credentials in example")
        return self


@dataclass(frozen=True)
class TestReceipt:
    id: str
    project: str
    answer_sha256: str
    runner: str
    run_id: str
    evidence_sha256: str
    test_suite_sha256: str
    executed: int
    failed: int
    status: str

    def validate(self):
        if (not isinstance(self.id, str) or not _ID.fullmatch(self.id)
                or not isinstance(self.project, str) or not _ID.fullmatch(self.project)
                or not isinstance(self.run_id, str) or not _ID.fullmatch(self.run_id)):
            raise ValueError("Invalid trusted test identity")
        if any(not isinstance(s, str) or not _DIGEST.fullmatch(s) for s in (
                self.answer_sha256, self.evidence_sha256, self.test_suite_sha256)):
            raise ValueError("Missing immutable test artifacts")
        if (self.runner not in _EXECUTORS or self.status != "passed"
                or type(self.executed) is not int or self.executed < 1
                or type(self.failed) is not int or self.failed != 0):
            raise ValueError("No independently executed passing test evidence")
        return self


@dataclass(frozen=True)
class HoldoutFence:
    """Frozen inputs owned by independent evaluator; not writable by training."""
    excluded_projects: frozenset[str]
    excluded_prompt_digests: frozenset[str]
    suite_sha256: str

    def validate(self):
        if (not isinstance(self.excluded_projects, frozenset)
                or not isinstance(self.excluded_prompt_digests, frozenset)
                or type(self.suite_sha256) is not str or not _DIGEST.fullmatch(self.suite_sha256)
                or not self.excluded_projects and not self.excluded_prompt_digests):
            raise ValueError("A nonempty frozen holdout fence is mandatory")
        if any(not isinstance(x, str) or not _ID.fullmatch(x) for x in self.excluded_projects):
            raise ValueError("Invalid held-out project")
        if any(not isinstance(x, str) or not _DIGEST.fullmatch(x) for x in self.excluded_prompt_digests):
            raise ValueError("Invalid held-out prompt fingerprint")
        return self


def curate(examples: list[Example], trusted_receipts: Mapping[str, TestReceipt],
           fence: HoldoutFence, *, model_license_reviewed: bool = False) -> dict:
    """Select only scope-matched, test-executed, rights-reviewed, nonleaking rows.

    trusted_receipts MUST be supplied from independent host-owned test stores,
    not from model replies. Even this function cannot cryptographically prove
    receipts without the host source; it refuses missing/invalid receipts.
    """
    fence.validate()
    if model_license_reviewed is not True:
        raise PermissionError("Model-weight license and training permissions must be reviewed")
    if (type(examples) is not list or len(examples) > MAX_EXAMPLES
            or not isinstance(trusted_receipts, Mapping)):
        raise ValueError("Invalid training inputs")
    rejected = Counter()
    seen_examples = set()
    seen_prompt_content = set()
    rows = []
    for item in examples:
        if type(item) is not Example:
            rejected["bad_example"] += 1
            continue
        try:
            item.validate()
            receipt = trusted_receipts.get(item.id)
            if type(receipt) is not TestReceipt:
                raise ValueError("missing trusted receipt")
            receipt.validate()
            if receipt.id != item.id or receipt.project != item.project:
                raise ValueError("test evidence does not match project")
            if receipt.answer_sha256 != sha(item.answer):
                raise ValueError("test evidence does not match answer bytes")
            if item.project in fence.excluded_projects or sha(item.prompt) in fence.excluded_prompt_digests:
                raise ValueError("holdout contamination")
            if receipt.test_suite_sha256 == fence.suite_sha256:
                raise ValueError("holdout test suite reused in training")
            if item.id in seen_examples:
                raise ValueError("duplicate example identity")
            # Dedup even across projects and model versions: identical prompts
            # should not land in both a train and validation/test split.
            semantic = sha(" ".join(item.prompt.casefold().split()))
            if semantic in seen_prompt_content:
                raise ValueError("duplicate or cross-group prompt")
        except (ValueError, PermissionError) as exc:
            reason = str(exc)
            if "holdout" in reason:
                rejected["holdout_contamination"] += 1
            elif "rights" in reason or "consent" in reason:
                rejected["rights_not_cleared"] += 1
            elif "duplicate" in reason:
                rejected["duplicate"] += 1
            elif "receipt" in reason or "evidence" in reason:
                rejected["not_verified"] += 1
            else:
                rejected["ineligible"] += 1
            continue
        seen_examples.add(item.id)
        seen_prompt_content.add(semantic)
        rows.append({
            "id": item.id, "project": item.project, "source": item.source_path,
            "origin": item.origin, "license": item.license, "model": item.model,
            "verification": receipt.runner, "run_id": receipt.run_id,
            "evidence_sha256": receipt.evidence_sha256,
            "answer_sha256": receipt.answer_sha256,
            "prompt": item.prompt, "answer": item.answer,
        })

    # Whole projects, not shuffled conversations, remain together. That
    # prevents a variant of one project leaking between train/val/test.
    projects = sorted({row["project"] for row in rows}, key=lambda p: (sha(p), p))
    split_for = {}
    if len(projects) >= 3:
        split_for[projects[-1]] = "test"
        split_for[projects[-2]] = "validation"
        split_for.update({project: "train" for project in projects[:-2]})
    else:
        split_for.update({project: "quarantine" for project in projects})
    by_split = {"train": [], "validation": [], "test": [], "quarantine": []}
    for row in rows:
        by_split[split_for[row["project"]]].append(row)
    return {
        "splits": by_split, "accepted": len(rows), "rejected": dict(rejected),
        "ready_for_owner_training_review": (
            len(by_split["train"]) >= 10 and bool(by_split["validation"]) and bool(by_split["test"])),
        "project_split": split_for, "holdout_suite_sha256": fence.suite_sha256,
        "model_license_reviewed": True, "trained": False,
        "notice": ("Curated candidates are not guaranteed copyright-clean or gameplay-correct. "
                   "No fine-tuning started; human inspection and a separate training approval are required."),
    }


def export_private(dataset: dict, home: Path, *, approved: bool = False) -> dict:
    """Owner-approved private JSONL export, no training, publishing or network."""
    if approved is not True:
        raise PermissionError("Owner must explicitly approve a private training export")
    if not isinstance(dataset, dict) or dataset.get("ready_for_owner_training_review") is not True:
        raise ValueError("A rights-cleared three-way project-disjoint dataset is required")
    home = Path(home).expanduser().resolve(strict=True)
    if not home.is_dir() or (home / "training").is_symlink():
        raise PermissionError("Training export requires a private local STAR profile")
    base = home / "training" / "verified"
    if base.is_symlink() or base.exists():
        raise FileExistsError("Private training export already exists; do not overwrite without review")
    base.mkdir(parents=True, mode=0o700)
    manifest = {
        "format": "star-verified-luau-sft-v1", "accepted": dataset["accepted"],
        "rejected": dataset["rejected"], "project_split": dataset["project_split"],
        "holdout_suite_sha256": dataset["holdout_suite_sha256"],
        "rights_review_required_before_train": True, "training_started": False,
        "files": {},
    }
    for split in ("train", "validation", "test"):
        # The approved export has no shell fragments, scripts, or credentials
        # in filename decisions. Separate test files are never fed to training.
        rows = dataset["splits"][split]
        file = base / f"{split}.jsonl"
        content = "".join(
            json.dumps({"messages": [
                {"role": "user", "content": row["prompt"]},
                {"role": "assistant", "content": row["answer"]},
            ]}, ensure_ascii=False) + "\n" for row in rows)
        file.write_text(content, encoding="utf-8")
        os.chmod(file, 0o600)
        manifest["files"][split] = {"sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                                    "examples": len(rows)}
    file = base / "manifest.json"
    file.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    os.chmod(file, 0o600)
    return {"exported": True, "folder": str(base), "examples": dataset["accepted"],
            "training_started": False, "model_weights_changed": False,
            "next": "Owner review, independent holdout check, then a separately approved LoRA job."}
